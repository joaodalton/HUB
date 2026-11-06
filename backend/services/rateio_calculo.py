# backend/services/rateio_calculo.py
"""
Motor de calculo puro do rateio -- extraido de rateio_service.py (split por
limite de linhas do projeto, sem mudanca de comportamento). Funcoes
privadas, consumidas apenas por services/rateio_service.py.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from extensions import db
from models.plant import Plant
from models.consumer_unit import ConsumerUnit, PlantConnection
from services import rateio_math as rm
from services.settings_service import get_all_settings


def _calcular_usina(plant: Plant) -> dict:
    warnings: list[str] = []

    producao_media, reserva, producao_disponivel = _producao_disponivel_usina(plant)
    if plant.producao_media() is None:
        warnings.append('Usina sem produção cadastrada (nem manual, nem mensal) -- preencha ao menos a produção média antes de calcular.')

    buffer_global_habilitado, buffer_global_percentual = _global_buffer_config()

    connections = PlantConnection.query.filter_by(plant_id=plant.id).all()
    n_usinas_por_uc = _conexoes_por_uc()

    resultado_ucs = []
    percentual_total_alocado = rm.ZERO

    for connection in connections:
        uc = connection.consumer_unit
        if not uc:
            continue

        # n_usinas_extra=0 -- a conexão JÁ existe (é essa mesma que estamos
        # percorrendo), então já está contada na query de dentro da função.
        consumo_considerado, consumo_ajustado, percentual_calculado = _percentual_sugerido_uc(
            uc, producao_disponivel, buffer_global_habilitado, buffer_global_percentual,
            n_usinas_extra=0, n_usinas_por_uc=n_usinas_por_uc,
        )

        if consumo_considerado is None:
            warnings.append(f'UC {uc.codigo} sem consumo cadastrado -- ignorada no cálculo.')
            continue

        qualificado, motivo_qualificacao = _checar_qualificacao(plant, uc)
        buffer_percentual_aplicado = _buffer_percentual_uc(uc, buffer_global_habilitado, buffer_global_percentual)

        resultado_ucs.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'clienteNome': uc.client.nome if uc.client else None,
            'clienteCpfCnpj': uc.documento or (uc.client.cpf if uc.client else None),
            'consumoTotal': rm.to_float(uc.consumo),
            'consumoConsiderado': rm.to_float(consumo_considerado),
            'bufferPercentualAplicado': rm.to_float(buffer_percentual_aplicado),
            'consumoAjustado': rm.to_float(consumo_ajustado),
            'producaoConsiderada': rm.to_float(consumo_ajustado),
            'percentualCalculado': rm.to_float(percentual_calculado),
            'qualificado': qualificado,
            'motivoQualificacao': motivo_qualificacao
        })
        percentual_total_alocado += percentual_calculado

    percentual_total_alocado = rm.q2(percentual_total_alocado)
    excede_limite = rm.excede_limite(percentual_total_alocado)

    if excede_limite:
        warnings.append(f'Soma dos percentuais ({percentual_total_alocado}%) excede 100% -- ajuste antes de aplicar.')

    return {
        'plantId': plant.id,
        'plantNome': plant.nome,
        'producaoMedia': rm.to_float(rm.q2(producao_media)),
        'reservaPercentual': rm.to_float(reserva),
        'producaoDisponivel': rm.to_float(producao_disponivel),
        'isCoringa': plant.is_coringa,
        'percentualTotalAlocado': rm.to_float(percentual_total_alocado),
        'excedeLimite': excede_limite,
        'ucs': resultado_ucs,
        'warnings': warnings
    }


def _conexoes_por_uc() -> dict[int, int]:
    """Numero de usinas por UC (da empresa atual), em UMA query -- antes era
    um count() por UC dentro do loop (N+1 no funil e no preview)."""
    rows = db.session.query(
        PlantConnection.consumer_unit_id, func.count(PlantConnection.id)
    ).group_by(PlantConnection.consumer_unit_id).all()
    return {uc_id: int(total) for uc_id, total in rows}


def _producao_disponivel_usina(plant: Plant) -> tuple[Decimal, Decimal, Decimal]:
    """Retorna (producao_media, reserva_percentual, producao_disponivel).
    producao_media() já resolve sozinho manual vs. média dos 12 meses
    (ver models/plant.py)."""
    producao_media = rm.to_decimal(plant.producao_media() or 0, campo='producao_media')
    reserva = rm.to_decimal(plant.reserva_percentual or 0, campo='reserva_percentual')
    return producao_media, reserva, rm.producao_disponivel(producao_media, reserva)


def _buffer_percentual_uc(uc: ConsumerUnit, buffer_global_habilitado: bool, buffer_global_percentual: Decimal) -> Decimal:
    """Override da UC ganha do valor global, se preenchido. Sem override,
    só aplica se o toggle global (Configurações > Geral) estiver ligado."""
    if uc.buffer_percentual is not None:
        return rm.to_decimal(uc.buffer_percentual, campo='buffer_percentual')
    if buffer_global_habilitado:
        return buffer_global_percentual
    return rm.ZERO


def _percentual_sugerido_uc(
    uc: ConsumerUnit,
    producao_disponivel: Decimal,
    buffer_global_habilitado: bool,
    buffer_global_percentual: Decimal,
    n_usinas_extra: int = 0,
    n_usinas_por_uc: dict[int, int] | None = None,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Conta central do motor: consumo -> ajustado pelo buffer -> percentual
    da produção disponível. Reutilizada tanto pro cálculo final (UC já
    conectada) quanto pra pré-visualização de qualificação (UC candidata,
    ainda não conectada -- por isso o n_usinas_extra).
    Retorna (consumoConsiderado, consumoAjustado, percentual), todos None se
    a UC não tiver consumo cadastrado."""
    if uc.consumo is None:
        return None, None, None

    if n_usinas_por_uc is None:
        n_usinas_existentes = PlantConnection.query.filter_by(consumer_unit_id=uc.id).count()
    else:
        n_usinas_existentes = n_usinas_por_uc.get(uc.id, 0)
    n_usinas_da_uc = (n_usinas_existentes + n_usinas_extra) or 1

    buffer_percentual = _buffer_percentual_uc(uc, buffer_global_habilitado, buffer_global_percentual)
    return rm.percentual_sugerido(uc.consumo, n_usinas_da_uc, buffer_percentual, producao_disponivel)


def _checar_qualificacao(plant: Plant, uc: ConsumerUnit) -> tuple[bool, str]:
    """Único critério ativo hoje: dia de emissão da usina precisa ser igual
    ou anterior ao dia de emissão da UC (senão a UC entraria tarde demais
    no ciclo de leitura). Sem dado suficiente, não bloqueia -- fica como
    'qualificado, mas sem dado pra confirmar'."""
    if not plant.dia_emissao_usina or not uc.dia_emissao_fatura:
        return True, 'Sem dado de dia de emissão suficiente para avaliar -- considerado qualificado.'

    if plant.dia_emissao_usina <= uc.dia_emissao_fatura:
        return True, 'Dia de emissão da usina é igual ou anterior ao da UC.'

    return False, 'Dia de emissão da UC é anterior ao da usina -- não qualificada para esta competência.'


def _global_buffer_config() -> tuple[bool, Decimal]:
    """Valor padrão do buffer de consumo, configurado em Configurações >
    Geral (Setting key/value, mesma tabela usada por Aparência). Cada UC
    pode ter um valor próprio (ConsumerUnit.buffer_percentual) que ignora
    este padrão -- ver _buffer_percentual_uc."""
    settings = get_all_settings()
    habilitado = settings.get('rateioBufferHabilitado') == 'true'

    try:
        percentual = rm.to_decimal(settings.get('rateioBufferPercentual') or 15)
    except ValueError:
        percentual = Decimal('15')

    return habilitado, percentual


def _validar_competencia(competencia: str) -> None:
    try:
        datetime.strptime(competencia, '%Y-%m')
    except ValueError:
        raise ValueError('Competencia deve estar no formato YYYY-MM (ex.: 2026-08).')
