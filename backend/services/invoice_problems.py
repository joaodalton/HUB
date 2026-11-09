"""Motivos de falha e totais GD por fatura, lidos do que o pipeline de extração já persistiu."""
from decimal import Decimal

_EXTRACTION = {
    'recebida': ('NOT_PROCESSED', 'Fatura ainda não processada.'),
    'erro': ('EXTRACTION_FAILED', 'Não foi possível ler o PDF.'),
    'layout_nao_reconhecido': (
        'LAYOUT_NOT_RECOGNIZED', 'Layout de fatura não reconhecido (suportado: Copel DANF3E V1.06).'),
}


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
    """Soma kWh por classe GD; TE/TUSD do mesmo evento já vêm agrupados em `compensacoes`."""
    energy = ((invoice.dados_normalizados or {}).get('invoice') or {}).get('billing_energy_input') or {}
    totals = {'GD_I': None, 'GD_II': None}
    for event in energy.get('compensacoes') or []:
        gd, quantity = event.get('classificacao_gd'), event.get('quantidade_kwh')
        if gd in totals and quantity is not None:
            totals[gd] = (totals[gd] or Decimal(0)) + abs(Decimal(quantity))
    return {'gdIKwh': None if totals['GD_I'] is None else str(totals['GD_I']),
            'gdIIKwh': None if totals['GD_II'] is None else str(totals['GD_II'])}
