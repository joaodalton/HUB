"""Validação pura: candidatos são fornecidos pelo serviço tenant-scoped."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re

from services.invoice_parsers.schemas import ExtractionIssue


@dataclass(frozen=True)
class UCMatchCandidate:
    id: int
    empresa_id: int
    client_id: int
    codigo: str


@dataclass(frozen=True)
class InvoiceValidationResult:
    status: str
    issues: tuple[ExtractionIssue, ...]
    consumer_unit_id: int | None = None
    uc_numero: str | None = None

    @property
    def warnings(self):
        return tuple(i for i in self.issues if i.severity == 'warning')

    @property
    def critical_errors(self):
        return tuple(i for i in self.issues if i.severity == 'critical')


class InvoiceValidator:
    # Núcleo obrigatório deriva dos campos critical do Core F4, mais emissor.
    REQUIRED = ('concessionaria', 'codigo_uc_documental', 'mes_referencia',
                'numero_nota_fiscal', 'serie_nota_fiscal', 'chave_acesso',
                'data_vencimento', 'consumo_kwh', 'valor_total_concessionaria')

    def validate(self, invoice, *, candidates=None, fiscal_conflict=False):
        issues = list(invoice.issues)
        for name in self.REQUIRED:
            field = invoice.campos.get(name)
            if field is None or field.status != 'found' or not self._valid(name, field.value):
                issues.append(ExtractionIssue('REQUIRED_FIELD_INVALID', 'critical',
                                              'Campo obrigatório ausente, ambíguo ou inválido.', name))
        if fiscal_conflict:
            issues.append(ExtractionIssue('FISCAL_KEY_DIFFERENT_HASH', 'critical',
                                          'Chave fiscal já registrada em outro arquivo; revisar reemissão/retificação.', 'chave_acesso'))
        review = any(i.severity == 'critical' for i in issues)
        code = invoice.campos.get('codigo_uc_documental')
        if code is None or code.status != 'found':
            return InvoiceValidationResult('revisao_necessaria', tuple(issues))
        if candidates is None or invoice.empresa_id is None or invoice.client_id is None:
            issues.append(ExtractionIssue('MATCH_CONTEXT_REQUIRED', 'warning', 'Matching não executado.'))
            return InvoiceValidationResult('revisao_necessaria', tuple(issues))
        if any(c.empresa_id != invoice.empresa_id for c in candidates):
            issues.append(ExtractionIssue('MATCH_TENANT_MISMATCH', 'critical', 'Contexto de matching inválido.'))
            return InvoiceValidationResult('revisao_necessaria', tuple(issues))
        if not candidates:
            return InvoiceValidationResult('uc_nao_encontrada', tuple(issues) + (
                ExtractionIssue('UC_NOT_FOUND', 'warning', 'UC não encontrada na empresa.'),))
        if len(candidates) != 1:
            return InvoiceValidationResult('revisao_necessaria', tuple(issues) + (
                ExtractionIssue('UC_MATCH_AMBIGUOUS', 'critical', 'Mais de uma UC candidata; nenhum vínculo aplicado.'),))
        candidate = candidates[0]
        if candidate.client_id != invoice.client_id:
            return InvoiceValidationResult('uc_pertence_outro_cliente', tuple(issues) + (
                ExtractionIssue('UC_OTHER_CLIENT', 'critical', 'UC pertence a outro cliente; contexto original preservado.'),))
        return InvoiceValidationResult('revisao_necessaria' if review else 'valida', tuple(issues),
                                       candidate.id, candidate.codigo)

    @staticmethod
    def _valid(name, value):
        if name in ('consumo_kwh', 'valor_total_concessionaria'):
            return isinstance(value, Decimal) and value.is_finite() and value >= 0
        if name == 'data_vencimento':
            return isinstance(value, date)
        if not isinstance(value, str) or not value.strip():
            return False
        if name == 'chave_acesso':
            return bool(re.fullmatch(r'[0-9]{44}', value))
        if name == 'mes_referencia':
            return bool(re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', value))
        return True
