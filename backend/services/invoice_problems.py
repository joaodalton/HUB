"""Motivos de falha e totais GD por fatura, lidos do que o pipeline de extração já persistiu."""
from decimal import Decimal

_EXTRACTION = {
    'recebida': ('NOT_PROCESSED', 'Fatura ainda não processada.'),
    'erro': ('EXTRACTION_FAILED', 'Não foi possível ler o PDF.'),
    'layout_nao_reconhecido': (
        'LAYOUT_NOT_RECOGNIZED', 'Layout de fatura não reconhecido (suportado: Copel DANF3E V1.06).'),
}


EXTRACTION_PROBLEM_STATUSES = tuple(_EXTRACTION)
VALIDATION_PROBLEM_STATUSES = ('uc_nao_encontrada', 'uc_pertence_outro_cliente', 'revisao_necessaria')


def invoice_problems(invoice) -> list[dict]:
    if invoice.status_extracao in _EXTRACTION:
        code, message = _EXTRACTION[invoice.status_extracao]
        return [{'code': code, 'message': message, 'fields': []}]
    uc = invoice.codigo_uc_extraido
    if invoice.status_validacao == 'uc_nao_encontrada':
        return [{'code': 'UC_NOT_FOUND', 'message': f'UC {uc} não está cadastrada em nenhum cliente.', 'fields': []}]
    if invoice.status_validacao == 'uc_pertence_outro_cliente':
        return [{'code': 'UC_OTHER_CLIENT', 'message': f'UC {uc} pertence a outro cliente.', 'fields': []}]
    if invoice.status_validacao == 'revisao_necessaria':
        issues = ((invoice.dados_normalizados or {}).get('validation') or {}).get('issues') or []
        critical = [i for i in issues if i.get('severity') == 'critical']
        fields = list(dict.fromkeys(i['field'] for i in critical if i.get('field')))
        if fields:
            return [{'code': 'MISSING_FIELDS', 'message': f'Faltou ler: {", ".join(fields)}.', 'fields': fields}]
        return [{'code': 'REVIEW_REQUIRED', 'message': '; '.join(i.get('message', '') for i in critical),
                 'fields': []}]
    return []


def gd_totals(invoice) -> dict:
    """kWh de GD I / GD II na fatura (injeção própria + compensação OUC), por evento.

    Evento = (classe GD, mês, contexto); TE/TUSD do mesmo evento são uma só quantidade.
    Classe com evento não contável (quantidade ausente ou TE/TUSD divergentes) vira None:
    nunca devolve soma parcial.
    """
    rows = ((invoice.dados_normalizados or {}).get('invoice') or {}).get('energy_components') or []
    events, broken = {}, set()

    def value(row, name):
        field = row.get(name) or {}
        return field.get('value') if field.get('status') == 'found' else None

    for row in rows:
        gd = value(row, 'gd_classification')
        if gd not in ('GD_I', 'GD_II') or value(row, 'category') not in ('injected', 'compensated'):
            continue
        events.setdefault((gd, value(row, 'credit_month'), value(row, 'compensation_context')), []).append(row)
    totals = {'GD_I': None, 'GD_II': None}
    for (gd, _, _), event in events.items():
        try:
            amounts = {abs(Decimal(value(r, 'amount_kwh'))) for r in event}
        except (TypeError, ArithmeticError):
            amounts = set()
        pair = sorted(str(value(r, 'tariff_component')) for r in event) == ['TE', 'TUSD']
        if not pair or len(amounts) != 1 or any(value(r, 'unit') != 'kWh' for r in event):
            broken.add(gd)
        else:
            totals[gd] = (totals[gd] or Decimal(0)) + next(iter(amounts))
    return {'gdIKwh': None if 'GD_I' in broken or totals['GD_I'] is None else str(totals['GD_I']),
            'gdIIKwh': None if 'GD_II' in broken or totals['GD_II'] is None else str(totals['GD_II'])}
