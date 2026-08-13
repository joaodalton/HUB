# backend/services/rateio_service.py
"""
Motor de cálculo do rateio -- Sprint 1: só porcentagem (sem modelo de
prioridade), sem geração de formulário/documento (isso vem depois).

Fluxo:
  preview_rateio()  -> calcula tudo, NÃO grava nada (usado por uma tela de
                        conferência antes de aplicar, quando ela existir).
  aplicar_rateio()   -> calcula, atualiza PlantConnection.percentual
                        (respeitando percentual_manual) e grava uma linha
                        em RateioHistorico por UC x Usina.

Regra de divisão quando uma UC está em mais de uma usina: Sprint 1 divide o
consumo IGUALMENTE entre as usinas conectadas (ex.: UC em 2 usinas = 50% do
consumo considerado em cada uma). Isso é uma simplificação deliberada --
João confirmou que hoje quase nenhuma UC tem mais de uma usina; quando a
tela de Rateio for desenhada, provavelmente vai dar pra escolher a divisão
manualmente por conexão em vez dessa divisão igual automática.
"""
from datetime import datetime, date

from extensions import db
from models.plant import Plant
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.rateio_historico import RateioHistorico
from services.log_service import LogService


def preview_rateio(plant_id: int | None = None) -> list[dict]:
    plants = [Plant.query.get(plant_id)] if plant_id else Plant.query.all()
    plants = [p for p in plants if p]
    return [_calcular_usina(plant) for plant in plants]


def aplicar_rateio(competencia: str, plant_id: int | None = None) -> list[dict]:
    _validar_competencia(competencia)
    resultados = preview_rateio(plant_id)

    for resultado in resultados:
        plant = Plant.query.get(resultado['plantId'])

        for uc_resultado in resultado['ucs']:
            connection = PlantConnection.query.filter_by(
                plant_id=plant.id,
                consumer_unit_id=uc_resultado['ucId']
            ).first()

            if not connection:
                connection = PlantConnection(
                    plant_id=plant.id,
                    consumer_unit_id=uc_resultado['ucId'],
                    percentual=0
                )
                db.session.add(connection)
                db.session.flush()

            # Conexão marcada como manual (lápis) -- motor não mexe no
            # percentual dela, mas ainda registra no histórico pra manter o
            # panorama completo daquela competência.
            if not connection.percentual_manual:
                connection.percentual = uc_resultado['percentualCalculado']

            db.session.add(RateioHistorico(
                competencia=competencia,
                plant_id=plant.id,
                consumer_unit_id=uc_resultado['ucId'],
                percentual=connection.percentual,
                consumo_considerado=uc_resultado['consumoConsiderado'],
                producao_considerada=uc_resultado['producaoConsiderada'],
                manual=connection.percentual_manual
            ))

    db.session.commit()

    LogService.info(
        acao='aplicar_rateio',
        mensagem=f'Rateio aplicado para competencia {competencia}' + (f' (usina {plant_id})' if plant_id else ' (todas as usinas)'),
        entidade='RateioHistorico',
        metadados={'competencia': competencia, 'plantId': plant_id}
    )

    return resultados


def list_historico(competencia: str | None = None, plant_id: int | None = None, uc_id: int | None = None) -> list[dict]:
    query = RateioHistorico.query

    if competencia:
        query = query.filter(RateioHistorico.competencia == competencia)
    if plant_id:
        query = query.filter(RateioHistorico.plant_id == plant_id)
    if uc_id:
        query = query.filter(RateioHistorico.consumer_unit_id == uc_id)

    registros = query.order_by(RateioHistorico.created_at.desc()).all()
    return [registro.to_dict() for registro in registros]


def _calcular_usina(plant: Plant) -> dict:
    warnings: list[str] = []

    producao_media = plant.producao_media()
    if producao_media is None:
        warnings.append('Usina sem produção mensal cadastrada -- cadastre ao menos 1 mês antes de calcular o rateio.')
        producao_media = 0.0

    reserva = float(plant.reserva_percentual or 0)
    producao_disponivel = round(producao_media * (1 - reserva / 100), 2)

    connections = PlantConnection.query.filter_by(plant_id=plant.id).all()
    ucs_conectadas = [c.consumer_unit for c in connections if c.consumer_unit]

    linhas_uc = []
    soma_consumo_considerado = 0.0

    for uc in ucs_conectadas:
        consumo_total = float(uc.consumo) if uc.consumo is not None else None

        if consumo_total is None:
            warnings.append(f'UC {uc.codigo} sem consumo cadastrado -- ignorada no cálculo.')
            continue

        n_usinas_da_uc = PlantConnection.query.filter_by(consumer_unit_id=uc.id).count() or 1
        consumo_considerado = round(consumo_total / n_usinas_da_uc, 2)

        elegivel, motivo_elegibilidade = _checar_elegibilidade(plant, uc)

        linhas_uc.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'consumoTotal': consumo_total,
            'consumoConsiderado': consumo_considerado,
            'elegivel': elegivel,
            'motivoElegibilidade': motivo_elegibilidade
        })
        soma_consumo_considerado += consumo_considerado

    # Rateio proporcional ao consumo. Se a soma pedida for maior que o
    # disponível, ninguém recebe 100% do que precisa -- normaliza pra caber.
    fator_normalizacao = 1.0
    if soma_consumo_considerado > producao_disponivel and producao_disponivel > 0:
        fator_normalizacao = producao_disponivel / soma_consumo_considerado
        warnings.append('Produção disponível é menor que o consumo somado das UCs conectadas -- percentuais foram normalizados proporcionalmente.')

    resultado_ucs = []
    for linha in linhas_uc:
        if producao_disponivel <= 0:
            percentual_calculado = 0.0
            producao_considerada = 0.0
        else:
            producao_considerada = round(linha['consumoConsiderado'] * fator_normalizacao, 2)
            percentual_calculado = round((producao_considerada / producao_disponivel) * 100, 2)

        resultado_ucs.append({
            **linha,
            'producaoConsiderada': producao_considerada,
            'percentualCalculado': percentual_calculado
        })

    return {
        'plantId': plant.id,
        'plantNome': plant.nome,
        'producaoMedia': round(producao_media, 2),
        'reservaPercentual': reserva,
        'producaoDisponivel': producao_disponivel,
        'isCoringa': plant.is_coringa,
        'ucs': resultado_ucs,
        'warnings': warnings
    }


def _checar_elegibilidade(plant: Plant, uc: ConsumerUnit) -> tuple[bool, str]:
    """Sugestão, não trava o cálculo -- é orientação pra quem for montar o
    rateio manualmente, o documento do João descreve isso como 'forte
    candidato' vs 'não recomendada', não como regra dura."""
    if not plant.dia_emissao_usina or not uc.dia_emissao_fatura:
        return True, 'Sem dado de dia de emissão suficiente para avaliar.'

    if plant.dia_emissao_usina <= uc.dia_emissao_fatura:
        return True, 'Dia de emissão da usina é igual ou anterior ao da UC -- forte candidata.'

    return False, 'Dia de emissão da UC é anterior ao da usina -- não recomendada para esta competência.'


def _validar_competencia(competencia: str) -> None:
    try:
        datetime.strptime(competencia, '%Y-%m')
    except ValueError:
        raise ValueError('Competencia deve estar no formato YYYY-MM (ex.: 2026-08).')