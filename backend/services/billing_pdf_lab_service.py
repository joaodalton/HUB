"""Diagnóstico documental Copel em memória, sem contexto ou persistência tenant."""
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from services.billing_calculation_service import BillingCalculationService
from services.invoice_compensation import EnergyStatus
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_parsers.extraction import MinimalExtractor
from services.invoice_parsers.registry import default_registry


STAGES = BillingCalculationService.STAGES


def analyze_pdf(document: bytes, *, sha256: str, filename: str, size: int,
                upload_duration_ms: str | None = None) -> dict:
    started = perf_counter()
    stages = {}
    result = {
        'executionId': str(uuid4()), 'status': 'REVIEW_REQUIRED',
        'pdf': {'name': filename, 'sizeBytes': size, 'sha256': sha256},
        'extracted': None, 'normalized': None, 'compensations': [],
        'missingFields': [], 'warnings': [], 'blockers': [], 'stages': [],
        'durationMs': None, 'error': None,
        'extractionStatus': 'NOT_EXECUTED', 'normalizationStatus': 'NOT_EXECUTED',
        'billingEligibility': {'status': 'NOT_EXECUTED', 'eligible': False, 'reason': None},
    }

    def stage(name, status, *, begin=None, duration_ms=None, component=None, version=None,
              inputs=None, outputs=None, warnings=(), blockers=()):
        stages[name] = {
            'stage': name, 'status': status, 'component': component, 'version': version,
            'timestamp': datetime.now(timezone.utc).isoformat() if status != 'NOT_EXECUTED' else None,
            'durationMs': (duration_ms if duration_ms is not None else
                           f'{(perf_counter() - begin) * 1000:.3f}' if begin is not None else None),
            'inputs': inputs or {}, 'outputs': outputs or {},
            'warnings': list(warnings), 'blockers': list(blockers),
        }

    stage('UPLOAD', 'SUCCESS', duration_ms=upload_duration_ms, component='PdfValidator',
          outputs={'sizeBytes': size, 'sha256': sha256})
    stage('UC_MATCHING', 'SKIPPED', component='InvoiceValidator',
          blockers=['Sem consulta a cadastros operacionais.'])
    stage('RULE_RESOLUTION', 'NOT_EXECUTED', component='RuleResolver',
          blockers=['Nenhuma regra comercial foi informada.'])
    try:
        step_started = perf_counter()
        raw = MinimalExtractor().extract(document)
        selection = default_registry().select(raw)
        if selection.parser is None:
            issues = raw.warnings + selection.issues
            result['warnings'] = [json_safe(issue) for issue in issues if issue.severity != 'critical']
            result['blockers'] = [json_safe(issue) for issue in issues if issue.severity == 'critical']
            if not result['blockers']:
                result['blockers'] = [json_safe(issue) for issue in selection.issues]
            result['extractionStatus'] = 'BLOCKED'
            stage('EXTRACTION', 'BLOCKED', begin=step_started, component='ParserRegistry',
                  outputs={'pageCount': raw.page_count},
                  warnings=[issue.code for issue in issues if issue.severity != 'critical'],
                  blockers=[issue.code for issue in selection.issues])
            return result
        parsed = selection.parser.parse(document)
        if parsed.identity != selection.parser.identity:
            raise ValueError('Identidade do parser incompatível.')
        result['extracted'] = json_safe(parsed)
        result['extractionStatus'] = 'SUCCESS'
        stage('EXTRACTION', 'SUCCESS', begin=step_started, component=parsed.identity.parser_name,
              version=parsed.identity.parser_version,
              outputs={'pageCount': raw.page_count, 'layout': parsed.identity.layout_name},
              warnings=[issue.code for issue in raw.warnings + parsed.issues])

        step_started = perf_counter()
        normalized = InvoiceNormalizer().normalize(parsed)
        result['normalized'] = json_safe(normalized)
        result['normalizationStatus'] = ('NORMALIZED' if normalized.status_normalizacao == 'normalizada'
                                          else 'REVIEW_REQUIRED')
        result['missingFields'] = [name for name, field in normalized.campos.items()
                                   if field.status != 'found']
        result['warnings'] = [json_safe(issue) for issue in raw.warnings + normalized.issues
                              if issue.severity != 'critical']
        result['blockers'] = [json_safe(issue) for issue in normalized.issues
                              if issue.severity == 'critical']
        stage('NORMALIZATION', 'SUCCESS' if normalized.status_normalizacao == 'normalizada' else 'BLOCKED',
              begin=step_started, component='InvoiceNormalizer',
              outputs={'status': normalized.status_normalizacao,
                       'missingFieldCount': len(result['missingFields'])},
              warnings=[issue.code for issue in normalized.issues if issue.severity == 'warning'])

        energy = normalized.billing_energy_input
        if energy is not None:
            result['compensations'] = json_safe(energy.compensacoes)
            result['billingEligibility'] = {
                'status': energy.status.value,
                'eligible': energy.status == EnergyStatus.VALID,
                'reason': None if energy.status == EnergyStatus.VALID else 'Energia compensada confiável não comprovada.',
            }
            stage('ENERGY_RESOLUTION', 'SUCCESS' if energy.status == 'VALID' else 'BLOCKED',
                  component='normalize_compensations',
                  outputs={'status': energy.status,
                           'eligibleKwh': json_safe(energy.energia_compensada_cobravel_kwh)},
                  blockers=[issue.code for issue in energy.issues] if energy.status != 'VALID' else ())
            if energy.status != 'VALID':
                result['blockers'].extend(json_safe(issue) for issue in energy.issues)
        result['status'] = ('NORMALIZED' if normalized.status_normalizacao == 'normalizada'
                            else 'REVIEW_REQUIRED')
        return result
    except Exception:
        # Não devolver conteúdo do PDF, paths nem detalhes de exceções do parser.
        result['status'] = 'ERROR'
        result['extractionStatus'] = 'FAILED' if 'EXTRACTION' not in stages else result['extractionStatus']
        result['error'] = {'code': 'PDF_DIAGNOSTIC_FAILED',
                           'message': 'Falha técnica no diagnóstico do PDF.'}
        if 'EXTRACTION' not in stages:
            stage('EXTRACTION', 'FAILED', begin=step_started, component='CopelDANF3EParser',
                  blockers=['PDF_DIAGNOSTIC_FAILED'])
        elif 'NORMALIZATION' not in stages:
            stage('NORMALIZATION', 'FAILED', begin=step_started, component='InvoiceNormalizer',
                  blockers=['PDF_DIAGNOSTIC_FAILED'])
        return result
    finally:
        for name in STAGES:
            if name not in stages:
                stage(name, 'NOT_EXECUTED')
        result['stages'] = [stages[name] for name in STAGES]
        result['durationMs'] = f'{(perf_counter() - started) * 1000:.3f}'
