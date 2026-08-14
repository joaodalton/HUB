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
from services.settings_service import get_all_settings


def preview_rateio(plant_id: int | None = None) -> list[dict]:
    plants = [Plant.query.get(plant_id)] if plant_id else Plant.query.all()
    plants = [p for p in plants if p]
    return [_calcular_usina(plant) for plant in plants]


def elegibilidade_funil(plant_id: int) -> dict:
    """Funil pra Tela 3 (Elegibilidade). Candidatas = todas as UCs que ainda
    NÃO estão conectadas a esta usina (não faz sentido re-filtrar quem já
    está dentro). Cada etapa é um AND acumulado com a anterior -- se a regra
    mudar (você avisou que ainda vai mexer bastante aqui), é só editar essa
    função, o resto do motor não depende dela."""
    plant = Plant.query.get(plant_id)
    if not plant:
        raise ValueError('Usina nao encontrada.')

    ja_conectadas_ids = {c.consumer_unit_id for c in PlantConnection.query.filter_by(plant_id=plant.id).all()}
    candidatas = [uc for uc in ConsumerUnit.query.all() if uc.id not in ja_conectadas_ids]

    janela_valida = [uc for uc in candidatas if _checar_elegibilidade(plant, uc)[0]]
    documentacao_ok = [uc for uc in janela_valida if uc.documentacao_completa and uc.sem_pendencia_financeira]
    elegiveis = documentacao_ok  # ponto único de ajuste quando a regra final mudar

    return {
        'plantId': plant.id,
        'totalClientes': len(candidatas),
        'janelaValida': len(janela_valida),
        'documentacaoOk': len(documentacao_ok),
        'elegiveis': len(elegiveis),
        'ucs': [
            {
                'ucId': uc.id,
                'ucCodigo': uc.codigo,
                'clienteNome': uc.client.nome if uc.client else None,
                'janelaValida': uc in janela_valida,
                'documentacaoCompleta': uc.documentacao_completa,
                'semPendenciaFinanceira': uc.sem_pendencia_financeira,
                'clienteEstrategico': uc.cliente_estrategico,
                'elegivel': uc in elegiveis,
                'motivo': _checar_elegibilidade(plant, uc)[1]
            }
            for uc in candidatas
        ]
    }


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
        warnings.append('Usina sem produção cadastrada (nem manual, nem mensal) -- preencha ao menos a produção média antes de calcular.')
        producao_media = 0.0

    reserva = float(plant.reserva_percentual or 0)
    producao_disponivel = round(producao_media * (1 - reserva / 100), 2)

    buffer_global_habilitado, buffer_global_percentual = _global_buffer_config()

    connections = PlantConnection.query.filter_by(plant_id=plant.id).all()

    resultado_ucs = []
    percentual_total_alocado = 0.0

    for connection in connections:
        uc = connection.consumer_unit
        if not uc:
            continue

        consumo_total = float(uc.consumo) if uc.consumo is not None else None

        if consumo_total is None:
            warnings.append(f'UC {uc.codigo} sem consumo cadastrado -- ignorada no cálculo.')
            continue

        # Consumo dividido entre as usinas ÀS QUAIS ESTA UC está conectada
        # (não tem relação com as outras UCs da usina) -- só entra em cena
        # quando a mesma UC atende de mais de uma usina ao mesmo tempo.
        n_usinas_da_uc = PlantConnection.query.filter_by(consumer_unit_id=uc.id).count() or 1
        consumo_considerado = round(consumo_total / n_usinas_da_uc, 2)

        # Buffer: override da UC ganha do valor global, se preenchido.
        # Sem override, só aplica se o toggle global estiver ligado.
        if uc.buffer_percentual is not None:
            buffer_percentual = float(uc.buffer_percentual)
        elif buffer_global_habilitado:
            buffer_percentual = buffer_global_percentual
        else:
            buffer_percentual = 0.0

        consumo_ajustado = round(consumo_considerado * (1 + buffer_percentual / 100), 2)

        if producao_disponivel <= 0:
            percentual_calculado = 0.0
        else:
            percentual_calculado = round((consumo_ajustado / producao_disponivel) * 100, 2)

        elegivel, motivo_elegibilidade = _checar_elegibilidade(plant, uc)

        resultado_ucs.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'clienteNome': uc.client.nome if uc.client else None,
            'clienteCpfCnpj': uc.documento or (uc.client.cpf if uc.client else None),
            'consumoTotal': consumo_total,
            'consumoConsiderado': consumo_considerado,
            'bufferPercentualAplicado': buffer_percentual,
            'consumoAjustado': consumo_ajustado,
            'producaoConsiderada': consumo_ajustado,
            'percentualCalculado': percentual_calculado,
            'elegivel': elegivel,
            'motivoElegibilidade': motivo_elegibilidade
        })
        percentual_total_alocado += percentual_calculado

    percentual_total_alocado = round(percentual_total_alocado, 2)
    excede_limite = percentual_total_alocado > 100.0

    if excede_limite:
        warnings.append(f'Soma dos percentuais ({percentual_total_alocado}%) excede 100% -- ajuste antes de aplicar.')

    return {
        'plantId': plant.id,
        'plantNome': plant.nome,
        'producaoMedia': round(producao_media, 2),
        'reservaPercentual': reserva,
        'producaoDisponivel': producao_disponivel,
        'isCoringa': plant.is_coringa,
        'percentualTotalAlocado': percentual_total_alocado,
        'excedeLimite': excede_limite,
        'ucs': resultado_ucs,
        'warnings': warnings
    }


def _global_buffer_config() -> tuple[bool, float]:
    """Valor padrão do buffer de consumo, configurado em Configurações >
    Geral (Setting key/value, mesma tabela usada por Aparência). Cada UC
    pode ter um valor próprio (ConsumerUnit.buffer_percentual) que ignora
    este padrão -- ver uso em _calcular_usina."""
    settings = get_all_settings()
    habilitado = settings.get('rateioBufferHabilitado') == 'true'

    try:
        percentual = float(settings.get('rateioBufferPercentual') or 15)
    except (TypeError, ValueError):
        percentual = 15.0

    return habilitado, percentual


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