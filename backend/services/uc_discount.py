"""Percentual comercial da UC, sem coerção de valores legados inválidos."""
from decimal import Decimal, InvalidOperation


def parse_uc_discount(value: str | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('Desconto da UC deve ser texto percentual.')
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith('%'):
        raw = raw[:-1].strip()
    try:
        percentage = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError('Desconto da UC deve ser percentual entre 0 e 100.') from exc
    if not percentage.is_finite() or not 0 <= percentage <= 100:
        raise ValueError('Desconto da UC deve ser percentual entre 0 e 100.')
    return percentage
