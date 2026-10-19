"""Identidade cadastral e documental de UC, sem alterar registros legados."""
from sqlalchemy import func, or_

from models.client import Client
from models.consumer_unit import ConsumerUnit


def normalize_uc_code(code: str, concessionaria: str | None) -> str:
    if not isinstance(code, str):
        raise ValueError('Codigo da UC e obrigatorio.')
    raw = code
    value = raw.strip()
    if not value:
        raise ValueError('Codigo da UC e obrigatorio.')
    if (concessionaria or '').strip().casefold() != 'copel':
        return raw
    if not value.isascii() or not value.isdigit() or len(value) not in (12, 15):
        raise ValueError('Codigo da UC Copel deve conter 12 ou 15 digitos.')
    return '000' + value if len(value) == 12 else value


def find_document_ucs(empresa_id: int, code: str, concessionaria: str | None):
    """Inclui codigo Copel legado de 12 digitos sem regravar o cadastro."""
    canonical = normalize_uc_code(code, concessionaria)
    condition = ConsumerUnit.codigo == canonical
    if (concessionaria or '').strip().casefold() == 'copel':
        copel = or_(
            func.lower(func.trim(ConsumerUnit.concessionaria)) == 'copel',
            ConsumerUnit.concessionaria.is_(None) & ConsumerUnit.client.has(
                (Client.empresa_id == empresa_id)
                & (func.lower(func.trim(Client.concessionaria)) == 'copel')
            ),
        )
        if canonical.startswith('000'):
            condition = or_(condition, ConsumerUnit.codigo == canonical[3:])
        condition = condition & copel
    return ConsumerUnit.query.filter(ConsumerUnit.empresa_id == empresa_id, condition)
