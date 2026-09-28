"""Contrato documental canônico. Sem banco, matching ou cálculo financeiro."""
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import re

from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue, FieldMap, ParsedInvoice, ParserIdentity
from services.invoice_compensation import BillingEnergyInput, EnergyStatus, normalize_compensations
from services.uc_code import normalize_uc_code


def json_safe(value):
    """Snapshots JSON: Decimal textual exato, datas ISO; float é rejeitado."""
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('Decimal não finito.')
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: json_safe(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise TypeError('Chaves JSON devem ser strings.')
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError('Tipo não permitido no snapshot JSON.')


@dataclass(frozen=True)
class InvoiceNormalized:
    identity: ParserIdentity
    empresa_id: int | None
    client_id: int | None
    consumer_unit_id: int | None
    campos: FieldMap
    itens_documentais: tuple[FieldMap, ...]
    tariffs_documented: tuple[FieldMap, ...]
    tributos: tuple[FieldMap, ...]
    historico_consumo: tuple[FieldMap, ...]
    medidor: FieldMap
    energy_components: tuple[FieldMap, ...]
    avisos: tuple[ExtractedField, ...]
    source_metadata: dict[str, str]
    status_normalizacao: str
    issues: tuple[ExtractionIssue, ...]
    billing_energy_input: BillingEnergyInput | None = None


class InvoiceNormalizer:
    # Equivalências documentais, não categorias de cobrança. GD-I/GD-II não
    # equivalem automaticamente a injeção: só aliases explícitos são aceitos.
    MAPPINGS = {
        'classificacao': {key: key for key in (
            'grupo_tarifario', 'subgrupo_tarifario', 'modalidade_tarifaria',
            'classe_tarifaria', 'subclasse_tarifaria')},
        'identificacao_fiscal': {
            'concessionaria': 'concessionaria', 'codigo_uc_documental': 'codigo_uc',
            'numero_nota_fiscal': 'numero_nota_fiscal', 'serie_nota_fiscal': 'serie',
            'chave_acesso': 'chave_acesso', 'mes_referencia': 'competencia',
        },
        'resumo': {
            'data_emissao': 'data_emissao', 'data_vencimento': 'data_vencimento',
            'consumo_kwh': 'consumo_kwh', 'valor_total_concessionaria': 'valor_total_concessionaria',
            'saldo_credito_valor': 'saldo_credito_valor', 'multa': 'multa', 'juros': 'juros',
            'tarifa_base': 'tarifa_base', 'descontos_aplicados': 'descontos_aplicados',
        },
        'energia': {
            'gd1_kwh': 'gd1_kwh', 'gd2_kwh': 'gd2_kwh',
            'injecao_gdi_kwh': 'injecao_gd1_kwh', 'injecao_gdii_kwh': 'injecao_gd2_kwh',
            'energia_injetada_kwh': 'energia_injetada_kwh',
            'energia_compensada_kwh': 'energia_compensada_kwh', 'saldo_credito_kwh': 'saldo_creditos_kwh',
        },
        'titular': {key: key for key in ('nome', 'cpf_cnpj', 'logradouro', 'numero', 'complemento',
                                        'bairro', 'cidade', 'uf', 'cep')},
    }
    DECIMALS = {'consumo_kwh', 'valor_total_concessionaria', 'saldo_credito_valor', 'multa',
                'juros', 'tarifa_base', 'descontos_aplicados', 'gd1_kwh', 'gd2_kwh',
                'injecao_gdi_kwh', 'injecao_gdii_kwh', 'energia_injetada_kwh',
                'energia_compensada_kwh', 'saldo_credito_kwh'}

    def normalize(self, parsed: ParsedInvoice, *, empresa_id=None, client_id=None, fatura_concessionaria_id=None):
        parsed = deepcopy(parsed)  # consumidor não pode modificar ParsedInvoice via alias mutável
        canonical, issues = {}, list(parsed.issues)
        for section, mapping in self.MAPPINGS.items():
            for target, source in mapping.items():
                canonical[target] = self._normalize_field(target, getattr(parsed, section).get(source))
        code = canonical['codigo_uc_documental']
        concessionaria = canonical['concessionaria']
        if code.status == 'found' and concessionaria.status == 'found':
            try:
                canonical['codigo_uc_documental'] = replace(code, value=normalize_uc_code(code.value, concessionaria.value))
            except ValueError:
                canonical['codigo_uc_documental'] = replace(code, status='failed', value=None)
        for target, source in (('data_leitura', 'data_leitura_atual'),
                               ('data_leitura_anterior', 'data_leitura_anterior'),
                               ('data_proxima_leitura', 'data_proxima_leitura')):
            candidates = [r[source] for r in parsed.leituras if source in r]
            if len(candidates) > 1:
                issue = ExtractionIssue('NORMALIZATION_AMBIGUOUS_READINGS', 'warning',
                                        'Múltiplas leituras; nenhum candidato escolhido.', target)
                canonical[target] = ExtractedField('ambiguous', warnings=(issue,))
            else:
                canonical[target] = self._normalize_field(target, candidates[0] if candidates else None)
        # O identificador cadastral so e confirmado no matching com a UC.
        canonical['uc_numero'] = self._normalize_field('uc_numero', None)
        for value in canonical.values():
            issues.extend(i for i in value.warnings if i not in issues)
        tariffs = tuple({
            'item_index': ExtractedField('found', index, source='itens_documentais'),
            **{key: value for key, value in row.items() if key in ('tarifa_unitaria', 'preco_unitario_com_tributos')},
        } for index, row in enumerate(parsed.itens)
            if any(key in row for key in ('tarifa_unitaria', 'preco_unitario_com_tributos')))
        month = canonical['mes_referencia']
        energy_input = normalize_compensations(parsed, month.value if month.status == 'found' else None,
                                              fatura_concessionaria_id)
        review_energy = parsed.compensation_supported and energy_input.status != EnergyStatus.VALID
        if review_energy:
            issues.extend(energy_input.issues)
        return InvoiceNormalized(
            parsed.identity, empresa_id, client_id, None, canonical,
            parsed.itens, tariffs, parsed.tributos, parsed.historico_consumo,
            parsed.medidor, parsed.energy_components, parsed.avisos, parsed.source_metadata,
            'revisao_necessaria' if review_energy or any(v.status in ('failed', 'ambiguous') for v in canonical.values()) else 'normalizada',
            tuple(issues), energy_input,
        )

    def _normalize_field(self, name, value):
        if value is None:
            issue = ExtractionIssue('FIELD_NOT_EXAMINED', 'info',
                                    'Campo não fornecido pelo parser; não significa zero.', name)
            return ExtractedField('not_present', warnings=(issue,))
        if value.status != 'found':
            return value
        try:
            result = value.value
            if name in self.DECIMALS:
                if not isinstance(result, Decimal):
                    raise ValueError('Esperado Decimal documental.')
            elif name.startswith('data_'):
                if isinstance(result, datetime):
                    result = result.date()
                elif not isinstance(result, date):
                    result = date.fromisoformat(result)
            elif name == 'mes_referencia':
                result = datetime.strptime(result, '%m/%Y').strftime('%Y-%m')
            elif name in ('cep', 'cpf_cnpj'):
                result = re.sub(r'[ .\-/]', '', result)
                if not result.isascii() or not result.isdigit() or len(result) not in ((8,) if name == 'cep' else (11, 14)):
                    raise ValueError('Identificador ilegível.')
            elif name == 'uf':
                result = result.strip().upper()
                if result not in ('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()):
                    raise ValueError('UF inválida.')
            elif isinstance(result, str):
                result = result.strip()
                if not result:
                    raise ValueError('Texto vazio.')
            else:
                raise ValueError('Esperado texto documental.')
            return replace(value, value=result)
        except (ValueError, TypeError, AttributeError):
            issue = ExtractionIssue('NORMALIZATION_FAILED', 'warning', 'Formato documental incompatível.', name)
            return ExtractedField('failed', source=value.source, warnings=value.warnings + (issue,))
