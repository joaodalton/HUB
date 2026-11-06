"""Coordena cálculo C5 com a extração persistida, sem abrir PDF nem emitir cobrança."""
from datetime import date, datetime, timezone
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from time import perf_counter

from flask import g
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
from models.consumer_unit import ConsumerUnit
from models.fatura_concessionaria import FaturaConcessionaria
from services.billing_calculation_contracts import BillingCalculationContext, BillingRuleSnapshot, DiscountType
from services.billing_calculation_engine import BillingCalculationEngine, BillingCalculationError
from services.billing_rule_resolver import RuleResolver, RuleResolutionError
from services.commercial_tariff_selector import CommercialTariffSelector
from services.document_tariff_resolver import DocumentTariffResolver
from services.invoice_compensation import BillingEnergyInput, CompensacaoNormalizada, ComponenteCompensacao, EnergyStatus
from services.invoice_normalization_service import InvoiceNormalized, InvoiceNormalizer, json_safe
from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue, ParserIdentity
from services.invoice_validation_service import InvoiceValidator
from services.regulatory_tariff_repository import RegulatoryTariffRepository
from services.uc_discount import parse_uc_discount
from services.uc_code import find_document_ucs, normalize_uc_code


_DECIMALS = InvoiceNormalizer.DECIMALS | {
    'confidence', 'quantidade', 'quantidade_kwh', 'amount_kwh', 'tarifa_unitaria',
    'preco_unitario_com_tributos', 'valor', 'pis_cofins_valor', 'icms_valor',
    'base_calculo', 'aliquota', 'tusd_fio_b_unit_tariff', 'leitura_anterior',
    'leitura_atual', 'constante', 'dias_faturados',
}


class _Blocked(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def _decimal(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('Decimal persistido inválido.')
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError('Decimal persistido inválido.')
    return number


def _issue(value):
    if not isinstance(value, dict):
        raise ValueError('Issue persistida inválida.')
    return ExtractionIssue(**value)


def _field(name, value):
    if not isinstance(value, dict):
        raise ValueError('Campo persistido inválido.')
    raw = value['value']
    if raw is not None:
        if name in _DECIMALS:
            raw = _decimal(raw)
        elif name.startswith('data_'):
            raw = date.fromisoformat(raw)
        elif name == 'item_index':
            if type(raw) is not int:
                raise ValueError('Índice documental inválido.')
        elif not isinstance(raw, (str, int, bool)):
            raise ValueError('Valor documental inválido.')
    confidence = _decimal(value.get('confidence'))
    return ExtractedField(value['status'], raw, confidence, value.get('source'),
                          tuple(_issue(row) for row in value.get('warnings', ())))


def _fields(value):
    if not isinstance(value, dict):
        raise ValueError('Seção documental inválida.')
    return {name: _field(name, field) for name, field in value.items()}


def _identity(value):
    if not isinstance(value, dict):
        raise ValueError('Parser persistido inválido.')
    return ParserIdentity(**value)


def _energy(value):
    if value is None:
        return None
    events = []
    for row in value['compensacoes']:
        components = tuple(ComponenteCompensacao(
            item['tipo'], _decimal(item['quantidade_original_kwh']),
            _field('tarifa_unitaria', item['tarifa_r_kwh']) if item['tarifa_r_kwh'] is not None else None,
            _field('valor', item['valor_r']) if item['valor_r'] is not None else None,
            _fields(item['documento']), item['source'], _fields(item['energy_evidence']),
        ) for item in row['componentes'])
        events.append(CompensacaoNormalizada(
            row['origem'], row['posto'], row['classificacao_gd'], row['mes_origem'],
            row['contexto_documental'], _decimal(row['quantidade_kwh']), components,
            tuple(row['source']), _decimal(row['confidence']), row['status'],
            tuple(_issue(issue) for issue in row['issues']),
        ))
    return BillingEnergyInput(
        _decimal(value['energia_compensada_cobravel_kwh']), tuple(events), value['status'],
        tuple(_issue(issue) for issue in value['issues']), _identity(value['source']),
        value['competencia'], value['fatura_concessionaria_id'],
    )


def _normalized(value):
    if not isinstance(value, dict):
        raise ValueError('Extração persistida inválida.')
    return InvoiceNormalized(
        _identity(value['identity']), value['empresa_id'], value['client_id'],
        value['consumer_unit_id'], _fields(value['campos']),
        tuple(_fields(row) for row in value['itens_documentais']),
        tuple(_fields(row) for row in value['tariffs_documented']),
        tuple(_fields(row) for row in value['tributos']),
        tuple(_fields(row) for row in value['historico_consumo']), _fields(value['medidor']),
        tuple(_fields(row) for row in value['energy_components']),
        tuple(_field('aviso', row) for row in value['avisos']), value['source_metadata'],
        value['status_normalizacao'], tuple(_issue(row) for row in value['issues']),
        _energy(value['billing_energy_input']),
    )


class BillingCalculationService:
    STAGES = ('UPLOAD', 'EXTRACTION', 'NORMALIZATION', 'UC_MATCHING',
              'RULE_RESOLUTION', 'TARIFF_RESOLUTION', 'ENERGY_RESOLUTION',
              'COMMERCIAL_DEDUCTIONS', 'FIO_B', 'FINAL_CALCULATION', 'SNAPSHOT')
    COMPONENTS = ('FaturaConcessionaria', 'CopelDANF3EParser', 'InvoiceNormalizer',
                  'InvoiceValidator', 'RuleResolver', 'DocumentTariffResolver',
                  'BillingEnergyInput', 'CommercialDeductionResolver', 'FioBResolver',
                  'BillingCalculationEngine', 'BillingCalculationSnapshot')

    def execute(self, invoice_id: int) -> BillingCalculationExecution:
        total_started = perf_counter()
        empresa_id = getattr(g, 'current_empresa_id', None)
        if type(empresa_id) is not int or empresa_id <= 0 or type(invoice_id) is not int or invoice_id <= 0:
            raise LookupError('Fatura não encontrada.')
        if db.session.new or db.session.dirty or db.session.deleted:
            raise ValueError('Execução exige sessão limpa.')
        invoice = FaturaConcessionaria.query.filter_by(id=invoice_id, empresa_id=empresa_id).populate_existing().first()
        if invoice is None:
            raise LookupError('Fatura não encontrada.')

        stages, started = {}, {}
        current_stage = 'EXTRACTION'

        def begin(name):
            nonlocal current_stage
            current_stage = name
            started[name] = perf_counter()

        def stage(name, status='OK', *, version=None, inputs=None, outputs=None,
                  warnings=(), blockers=()):
            stages[name] = {
                'stage': name, 'status': status,
                'component': self.COMPONENTS[self.STAGES.index(name)], 'version': version,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'duration_ms': f'{(perf_counter() - started[name]) * 1000:.3f}'
                               if name in started else None,
                'inputs': inputs or {}, 'outputs': outputs or {},
                'warnings': list(warnings), 'blockers': list(blockers),
            }

        status, snapshot = 'ERROR', None
        try:
            stage('UPLOAD', 'PERSISTED', outputs={'invoice_id': invoice.id})
            if invoice.status_extracao != 'extraida' or not isinstance(invoice.dados_normalizados, dict):
                raise _Blocked('MISSING_DATA', 'EXTRACTION_UNAVAILABLE')
            payload = invoice.dados_normalizados
            try:
                normalized = _normalized(payload['invoice'])
            except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError) as exc:
                raise _Blocked('MISSING_DATA', 'NORMALIZED_CONTRACT_INVALID') from exc
            stage('EXTRACTION', 'PERSISTED', version=normalized.identity.parser_version,
                  outputs={'parser': normalized.identity.parser_name})
            current_stage = 'NORMALIZATION'
            if (normalized.empresa_id != empresa_id or normalized.client_id != invoice.client_id
                    or normalized.consumer_unit_id != invoice.consumer_unit_id
                    or any(getattr(invoice, name) is not None
                           and getattr(normalized.identity, name) != getattr(invoice, name)
                           for name in ('parser_name', 'parser_version', 'layout_name', 'layout_version'))
                    or normalized.billing_energy_input is not None
                    and normalized.billing_energy_input.source != normalized.identity):
                raise _Blocked('REVIEW_REQUIRED', 'NORMALIZED_CONTEXT_MISMATCH')

            validation = payload.get('validation')
            if (invoice.status_validacao != 'valida' or not isinstance(validation, dict)
                    or validation.get('status') != 'valida'
                    or validation.get('consumer_unit_id') != invoice.consumer_unit_id):
                raise _Blocked('REVIEW_REQUIRED', 'EXTRACTION_NOT_VALIDATED')
            if any(not InvoiceValidator._valid(name, normalized.campos[name].value)
                   or normalized.campos[name].status != 'found'
                   for name in InvoiceValidator.REQUIRED if name in normalized.campos) or any(
                   name not in normalized.campos for name in InvoiceValidator.REQUIRED):
                raise _Blocked('MISSING_DATA', 'REQUIRED_EXTRACTION_FIELD_MISSING')
            if any(issue.severity == 'critical' for issue in normalized.issues):
                raise _Blocked('REVIEW_REQUIRED', 'EXTRACTION_CRITICAL_ISSUE')
            stage('NORMALIZATION', 'PERSISTED', outputs={'status': normalized.status_normalizacao},
                  warnings=(issue.code for issue in normalized.issues if issue.severity == 'warning'))

            begin('UC_MATCHING')
            uc = ConsumerUnit.query.filter_by(id=invoice.consumer_unit_id, empresa_id=empresa_id,
                                              client_id=invoice.client_id).populate_existing().first()
            code = normalized.campos.get('codigo_uc_documental')
            matches = (find_document_ucs(empresa_id, code.value, normalized.campos['concessionaria'].value).all()
                if code is not None and code.status == 'found' else ())
            if (uc is None or code is None or code.status != 'found'
                    or len(matches) != 1 or matches[0].id != uc.id
                    or normalize_uc_code(code.value, normalized.campos['concessionaria'].value) != normalize_uc_code(uc.codigo, normalized.campos['concessionaria'].value)
                    or validation.get('uc_numero') != uc.codigo):
                raise _Blocked('REVIEW_REQUIRED', 'UC_MATCH_INVALID')
            stage('UC_MATCHING', outputs={'consumer_unit_id': uc.id})

            begin('RULE_RESOLUTION')
            try:
                rule = RuleResolver().resolve(client_id=invoice.client_id, consumer_unit_id=uc.id)
            except RuleResolutionError as exc:
                mapped = 'MISSING_DATA' if exc.code == 'no_rule_configured' else 'REVIEW_REQUIRED'
                raise _Blocked(mapped, exc.code.upper()) from exc
            try:
                percentage = parse_uc_discount(uc.desconto)
            except ValueError as exc:
                raise _Blocked('REVIEW_REQUIRED', 'UC_DISCOUNT_INVALID') from exc
            rule = replace(rule,
                discount_type=DiscountType.PERCENTAGE if percentage is not None else DiscountType.NONE,
                discount_value=percentage,
                metadata={**rule.metadata, 'discount_source': 'consumer_unit',
                          'configured_discount_type': rule.discount_type.value,
                          'configured_discount_value': str(rule.discount_value) if rule.discount_value is not None else ''})
            rule_snapshot = BillingRuleSnapshot(rule).to_dict()
            stage('RULE_RESOLUTION', version=rule.rule_version,
                  outputs={'rule_id': rule.rule_id})

            begin('ENERGY_RESOLUTION')
            energy = normalized.billing_energy_input
            if energy is None or energy.fatura_concessionaria_id != invoice.id or energy.competencia != invoice.competencia:
                raise _Blocked('MISSING_DATA', 'ENERGY_CONTEXT_INVALID')
            if energy.status != EnergyStatus.VALID:
                raise _Blocked({'AMBIGUOUS': 'REVIEW_REQUIRED', 'MISSING': 'MISSING_DATA',
                                'UNSUPPORTED': 'UNSUPPORTED'}[energy.status.value], 'ENERGY_' + energy.status.value)
            stage('ENERGY_RESOLUTION', outputs={'status': energy.status.value,
                                                'kwh': str(energy.energia_compensada_cobravel_kwh)})

            begin('TARIFF_RESOLUTION')
            tariffs = DocumentTariffResolver().resolve(normalized)
            selections = CommercialTariffSelector().select(tariffs, rule)
            if not selections:
                raise _Blocked('MISSING_DATA', 'TARIFF_EVENTS_MISSING')
            invalid = next((selection for selection in selections if selection.status != EnergyStatus.VALID), None)
            if invalid:
                raise _Blocked({'AMBIGUOUS': 'REVIEW_REQUIRED', 'MISSING': 'MISSING_DATA',
                                'UNSUPPORTED': 'UNSUPPORTED'}[invalid.status.value],
                               invalid.issues[0].code.upper() if invalid.issues else 'TARIFF_UNAVAILABLE')
            stage('TARIFF_RESOLUTION', outputs={'events': len(selections),
                                                'source': selections[0].source_kind.value},
                  warnings=(issue.code for issue in tariffs.issues if issue.severity == 'warning'))

            concessionaria = normalized.campos['concessionaria'].value
            regulatory = tuple(row for row in RegulatoryTariffRepository().fio_b_tariffs()
                               if row.distributor == concessionaria
                               and row.valid_from <= invoice.competencia <= row.valid_to)
            begin('FINAL_CALCULATION')
            context = BillingCalculationContext(empresa_id, invoice.client_id, uc.id, invoice.id, invoice.competencia)
            result = BillingCalculationEngine().calculate(
                invoice=normalized, rule=rule, context=context, selected_tariffs=selections,
                fio_b_tariffs=regulatory)
            memory = result.calculation_memory
            deduction = memory.deduction_resolution if not isinstance(memory, dict) else memory.get('deduction_resolution')
            tax_statuses = [row['status'] for row in deduction['deductions']] if deduction else []
            if tax_statuses and any(value != 'VALID' for value in tax_statuses):
                current_stage = 'COMMERCIAL_DEDUCTIONS'
                raise _Blocked({'AMBIGUOUS': 'REVIEW_REQUIRED', 'MISSING': 'MISSING_DATA',
                                'UNSUPPORTED': 'UNSUPPORTED'}[next(value for value in tax_statuses if value != 'VALID')],
                               result.issues[0].code if result.issues else 'DEDUCTION_BLOCKED')
            stage('COMMERCIAL_DEDUCTIONS', outputs={'status': 'VALID',
                  'deductions': len(tax_statuses)})
            fio_rows = memory.fio_b_components if not isinstance(memory, dict) else memory.get('fio_b_components', ())
            if rule.billing_modifiers.exclude_gdii_fio_b is True:
                invalid_fio = next((row for row in fio_rows if row['status'] not in ('RESOLVED', 'NOT_APPLICABLE')), None)
                if invalid_fio:
                    current_stage = 'FIO_B'
                    raise _Blocked({'AMBIGUOUS': 'REVIEW_REQUIRED', 'MISSING_DATA': 'MISSING_DATA',
                                    'UNSUPPORTED': 'UNSUPPORTED'}[invalid_fio['status']],
                                   'FIO_B_' + invalid_fio['status'])
            stage('FIO_B', 'OK' if rule.billing_modifiers.exclude_gdii_fio_b is True else 'NOT_APPLICABLE',
                  outputs={'regulatory_versions': sorted({row.version for row in regulatory})})
            if result.resolution_status != EnergyStatus.VALID or result.hub_amount is None:
                mapped = {'AMBIGUOUS': 'REVIEW_REQUIRED', 'MISSING': 'MISSING_DATA',
                          'UNSUPPORTED': 'UNSUPPORTED'}[result.resolution_status.value]
                raise _Blocked(mapped, result.issues[0].code if result.issues else 'CALCULATION_BLOCKED')
            stage('FINAL_CALCULATION', version=result.calculation_version,
                  warnings=(issue.code for issue in result.warnings))

            begin('SNAPSHOT')
            source = {'invoice_hash': invoice.arquivo_hash, 'normalized': payload['invoice'],
                      'rule': rule_snapshot, 'regulatory': json_safe(regulatory),
                      'calculation_version': result.calculation_version}
            fingerprint = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False,
                allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()
            snapshot = BillingCalculationSnapshot.query.filter_by(empresa_id=empresa_id,
                                                                   fingerprint=fingerprint).first()
            if snapshot is not None and snapshot.fatura_concessionaria_id != invoice.id:
                raise _Blocked('ERROR', 'SNAPSHOT_INVOICE_MISMATCH')
            reused = snapshot is not None
            if snapshot is None:
                try:
                    with db.session.begin_nested():
                        snapshot = BillingCalculationSnapshot(
                            empresa_id=empresa_id, fatura_concessionaria_id=invoice.id,
                            fingerprint=fingerprint, regra_snapshot=rule_snapshot,
                            entrada_normalizada=payload['invoice'], resultado=result.to_dict(),
                            valor_final=result.hub_amount)
                        db.session.add(snapshot)
                        db.session.flush()
                except IntegrityError:
                    snapshot = BillingCalculationSnapshot.query.filter_by(
                        empresa_id=empresa_id, fingerprint=fingerprint).first()
                    if snapshot is None or snapshot.fatura_concessionaria_id != invoice.id:
                        raise _Blocked('ERROR', 'SNAPSHOT_CONFLICT')
                    reused = True
            stage('SNAPSHOT', version=result.calculation_version,
                  outputs={'snapshot_id': snapshot.id, 'reused': reused})
            status = 'CALCULATED'
        except _Blocked as exc:
            status = exc.status
            stage(current_stage, status, blockers=(exc.code,))
        except BillingCalculationError as exc:
            status = ('UNSUPPORTED' if exc.code.startswith('unsupported_') else
                      'MISSING_DATA' if 'missing' in exc.code else 'REVIEW_REQUIRED')
            stage(current_stage, status, blockers=(exc.code.upper(),))
        except Exception:
            db.session.rollback()
            status, snapshot = 'ERROR', None
            stage(current_stage, status,
                  blockers=('CALCULATION_ERROR',))

        for name in self.STAGES:
            if name not in stages:
                stages[name] = {'stage': name, 'status': 'NOT_REACHED', 'timestamp': None,
                                'component': self.COMPONENTS[self.STAGES.index(name)], 'version': None,
                                'duration_ms': None, 'inputs': {}, 'outputs': {},
                                'warnings': [], 'blockers': []}

        execution = BillingCalculationExecution(
            empresa_id=empresa_id, fatura_concessionaria_id=invoice.id,
            snapshot_id=snapshot.id if status == 'CALCULATED' else None,
            status=status, auditoria={
                'duration_ms': f'{(perf_counter() - total_started) * 1000:.3f}',
                'stages': [stages[name] for name in self.STAGES],
            },
        )
        db.session.add(execution)
        db.session.commit()
        return execution
