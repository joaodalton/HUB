# backend/services/rateio_math.py
"""Aritmetica do rateio em Decimal, sem banco e sem Flask.

Mesma politica numerica do motor de cobranca (billing_calculation_engine):
Decimal em todo o caminho, arredondamento ROUND_HALF_UP e quantize so no
resultado que sera persistido/exibido. Antes, rateio_service usava float e
round() nativo (half-even): round(2.675, 2) == 2.67, enquanto a cobranca
arredondava 2.68 -- duas respostas para o mesmo percentual.

Tudo aqui e funcao pura: recebe numeros, devolve numeros. E o que a suite
de testes de calculo exercita.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

CEM = Decimal('100')
ZERO = Decimal('0')
DUAS_CASAS = Decimal('0.01')
LIMITE_PERCENTUAL = CEM
_PRECISAO = 28


def to_decimal(value, *, campo: str = 'valor') -> Decimal:
    """Converte int/float/str/Decimal em Decimal. float passa por str() para
    nao herdar o ruido binario (0.1 -> '0.1', nao 0.1000000000000000055...)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError(f'{campo} invalido.')
    try:
        if isinstance(value, float):
            return Decimal(str(value))
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise ValueError(f'{campo} invalido.')


def q2(value: Decimal) -> Decimal:
    return value.quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


def to_float(value: Decimal | None) -> float | None:
    """Fronteira JSON: so aqui Decimal vira float, ja quantizado."""
    return None if value is None else float(value)


def validar_percentual(value, *, campo: str = 'percentual') -> Decimal:
    """Percentual informado por humano (wizard / edicao manual): numero,
    nao negativo, no maximo 100, com 2 casas."""
    percentual = to_decimal(value, campo=campo)
    if not percentual.is_finite():
        raise ValueError(f'{campo} invalido.')
    if percentual < ZERO:
        raise ValueError(f'{campo} nao pode ser negativo.')
    if percentual > LIMITE_PERCENTUAL:
        raise ValueError(f'{campo} nao pode exceder 100%.')
    return q2(percentual)


def producao_disponivel(producao_media, reserva_percentual) -> Decimal:
    """producao_media * (1 - reserva/100), 2 casas."""
    media = to_decimal(producao_media or 0, campo='producao_media')
    reserva = to_decimal(reserva_percentual or 0, campo='reserva_percentual')
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return q2(media * (CEM - reserva) / CEM)


def consumo_considerado(consumo_total, n_usinas: int) -> Decimal:
    """Consumo da UC dividido igualmente entre as usinas a que esta conectada."""
    consumo = to_decimal(consumo_total, campo='consumo')
    divisor = max(int(n_usinas or 0), 1)
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return q2(consumo / divisor)


def consumo_ajustado(consumo_considerado_valor, buffer_percentual) -> Decimal:
    buffer_pct = to_decimal(buffer_percentual or 0, campo='buffer_percentual')
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return q2(to_decimal(consumo_considerado_valor) * (CEM + buffer_pct) / CEM)


def percentual_da_producao(consumo_ajustado_valor, producao_disponivel_valor) -> Decimal:
    """(consumo_ajustado / producao_disponivel) * 100; 0 quando nao ha producao."""
    producao = to_decimal(producao_disponivel_valor or 0)
    if producao <= ZERO:
        return ZERO
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return q2(to_decimal(consumo_ajustado_valor) * CEM / producao)


def percentual_sugerido(consumo_total, n_usinas: int, buffer_percentual, producao_disponivel_valor) -> tuple[Decimal, Decimal, Decimal]:
    """Conta central do motor. Retorna (consumoConsiderado, consumoAjustado, percentual)."""
    considerado = consumo_considerado(consumo_total, n_usinas)
    ajustado = consumo_ajustado(considerado, buffer_percentual)
    return considerado, ajustado, percentual_da_producao(ajustado, producao_disponivel_valor)


def producao_considerada(percentual, producao_disponivel_valor) -> Decimal:
    """Quanto da producao disponivel um percentual representa (kWh), 2 casas."""
    producao = to_decimal(producao_disponivel_valor or 0)
    if producao <= ZERO:
        return ZERO
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return q2(to_decimal(percentual) * producao / CEM)


def soma_percentuais(valores) -> Decimal:
    total = ZERO
    for valor in valores:
        total += to_decimal(valor or 0)
    return q2(total)


def excede_limite(total: Decimal) -> bool:
    return to_decimal(total) > LIMITE_PERCENTUAL
