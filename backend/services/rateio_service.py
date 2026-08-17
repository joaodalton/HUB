# backend/services/rateio_service.py
"""
Motor de cálculo do rateio -- Sprint 1-4: só porcentagem (sem modelo de
prioridade), sem geração de formulário/documento (isso vem depois).

Fluxo:
  preview_rateio()       -> calcula tudo, NÃO grava nada.
  funil_qualificacao()   -> lista candidatas (UCs ainda não conectadas a
                             esta usina) com o percentual que CONSUMIRIAM se
                             fossem conectadas -- usado pela Tela 3.
  aplicar_rateio()       -> calcula, atualiza PlantConnection.percentual
                             (respeitando percentual_manual) e grava uma
                             linha em RateioHistorico por UC x Usina.

Regra de divisão quando uma UC está em mais de uma usina: consumo dividido
IGUALMENTE entre as usinas conectadas (simplificação deliberada -- João
confirmou que hoje quase nenhuma UC tem mais de uma usina).

Qualificação (Sprint 4, simplificada a pedido do João): só considera a
janela de leitura (dia de emissão da UC vs. da usina). Documentação e
pendência financeira continuam existindo como campos no cadastro da UC, mas
NÃO bloqueiam mais o funil -- não tem automação real por trás delas ainda.
"""
from datetime import datetime

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


def funil_qualificacao(plant_id: int) -> dict:
    """Funil da Tela 3. Candidatas = UCs ainda NÃO conectadas a esta usina.
    'Qualificado' = passou na checagem de janela de leitura. Cada UC também
    já vem com o percentual que ela CONSUMIRIA se fosse conectada agora,
    pra montar a lista de seleção sem precisar de uma segunda chamada."""
    plant = Plant.query.get(plant_id)
    if not plant:
        raise ValueError('Usina nao encontrada.')

    _, _, producao_disponivel = _producao_disponivel_usina(plant)
    buffer_global_habilitado, buffer_global_percentual = _global_buffer_config()

    ja_conectadas_ids = {c.consumer_unit_id for c in PlantConnection.query.filter_by(plant_id=plant.id).all()}
    candidatas = [uc for uc in ConsumerUnit.query.all() if uc.id not in ja_conectadas_ids]

    ucs_resultado = []
    qualificados = 0

    for uc in candidatas:
        qualificado, motivo = _checar_qualificacao(plant, uc)

        # n_usinas_extra=1 -- essa UC ainda não tem conexão com ESTA usina,
        # então o cálculo simula "e se ela entrasse aqui também", somando 1
        # às conexões que ela já tem com outras usinas (se houver).
        _, _, percentual_sugerido = _percentual_sugerido_uc(
            uc, producao_disponivel, buffer_global_habilitado, buffer_global_percentual, n_usinas_extra=1
        )

        if qualificado:
            qualificados += 1

        ucs_resultado.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'clienteNome': uc.client.nome if uc.client else None,
            'consumo': float(uc.consumo) if uc.consumo is not None else None,
            'percentualSugerido': percentual_sugerido if percentual_sugerido is not None else 0.0,
            'qualificado': qualificado,
            'motivo': motivo
        })

    return {
        'plantId': plant.id,
        'totalClientes': len(candidatas),
        'qualificados': qualificados,
        'ucs': ucs_resultado
    }

def aplicar_rateio(competencia: str, plant_id: int | None = None) -> list[dict]:
    """Recalcula e GRAVA o rateio de conexoes que JA EXISTEM (diferente de
    confirmar_selecao, que cria conexao nova a partir da selecao do wizard).
    Usado pra "rodar de novo" o calculo numa competencia nova sem passar
    pelo wizard inteiro -- ex.: mes seguinte, produção/consumo mudaram,
    quer atualizar os percentuais das UCs que ja estao conectadas.
    Respeita percentual_manual: conexao marcada como manual (lapis, ou
    confirmada pelo wizard) NUNCA e sobrescrita aqui -- so grava historico
    do valor que ja estava."""
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
                continue  # aplicar_rateio nao cria conexao nova -- isso e papel do confirmar_selecao

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
        mensagem=f'Rateio recalculado para competencia {competencia}' + (f' (usina {plant_id})' if plant_id else ' (todas as usinas)'),
        entidade='RateioHistorico',
        metadados={'competencia': competencia, 'plantId': plant_id}
    )

    return resultados


def confirmar_selecao(plant_id: int, competencia: str, selecoes: list[dict]) -> dict:
    """Passo que faltava no wizard (Tela 3 → Tela 4 → 'Aprovar proposta').
    Recebe as UCs escolhidas + o % REAL definido/ajustado na Tela 4 e:
      1) cria a PlantConnection (se ainda não existir) com percentual_manual=True
         -- decisão humana explícita, aplicar_rateio() nunca sobrescreve sozinho;
      2) atualiza o percentual se a UC já tinha conexão com esta usina (não duplica);
      3) valida que a soma de TODAS as conexões da usina (as que já existiam fora
         da seleção + as que estão sendo confirmadas agora) não passa de 100% --
         se passar, nada é gravado (tudo ou nada);
      4) registra uma linha em RateioHistorico por UC, na competência informada,
         pro painel de histórico já mostrar a decisão tomada agora.
    """
    _validar_competencia(competencia)

    plant = Plant.query.get(plant_id)
    if not plant:
        raise ValueError('Usina nao encontrada.')

    if not selecoes:
        raise ValueError('Nenhum cliente selecionado.')

    selecoes_por_uc: dict[int, float] = {}
    for selecao in selecoes:
        uc_id = selecao.get('ucId')
        percentual = selecao.get('percentual')
        if uc_id and percentual is not None:
            try:
                selecoes_por_uc[int(uc_id)] = round(float(percentual), 2)
            except (TypeError, ValueError):
                raise ValueError(f'Percentual invalido para a UC id={uc_id}.')

    if not selecoes_por_uc:
        raise ValueError('Nenhuma UC valida na selecao.')

    conexoes_existentes = PlantConnection.query.filter_by(plant_id=plant.id).all()
    conexoes_por_uc_id = {c.consumer_unit_id: c for c in conexoes_existentes}

    soma_outras_conexoes = sum(
        float(c.percentual) for c in conexoes_existentes if c.consumer_unit_id not in selecoes_por_uc
    )
    soma_total = round(soma_outras_conexoes + sum(selecoes_por_uc.values()), 2)

    if soma_total > 100.0:
        raise ValueError(f'Soma dos percentuais desta usina ficaria em {soma_total}% -- excede 100%. Ajuste antes de confirmar.')

    _, _, producao_disponivel = _producao_disponivel_usina(plant)

    criadas = 0
    atualizadas = 0
    resultado_ucs = []

    for uc_id, percentual in selecoes_por_uc.items():
        uc = ConsumerUnit.query.get(uc_id)

        if not uc:
            raise ValueError(f'UC id={uc_id} nao encontrada.')

        connection = conexoes_por_uc_id.get(uc_id)

        if connection:
            connection.percentual = percentual
            connection.percentual_manual = True
            atualizadas += 1
        else:
            connection = PlantConnection(
                plant_id=plant.id,
                consumer_unit_id=uc.id,
                percentual=percentual,
                percentual_manual=True
            )
            db.session.add(connection)
            criadas += 1

        db.session.flush()

        producao_considerada = round((percentual / 100) * producao_disponivel, 2) if producao_disponivel else 0.0

        db.session.add(RateioHistorico(
            competencia=competencia,
            plant_id=plant.id,
            consumer_unit_id=uc.id,
            percentual=percentual,
            consumo_considerado=float(uc.consumo) if uc.consumo is not None else None,
            producao_considerada=producao_considerada,
            manual=True
        ))

        resultado_ucs.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'clienteNome': uc.client.nome if uc.client else None,
            'percentual': percentual
        })

    db.session.commit()

    LogService.info(
        acao='confirmar_rateio',
        mensagem=f'Selecao de rateio confirmada para "{plant.nome}" ({competencia}): {criadas} nova(s), {atualizadas} atualizada(s)',
        entidade='PlantConnection',
        metadados={'plantId': plant.id, 'competencia': competencia}
    )

    return {
        'plantId': plant.id,
        'competencia': competencia,
        'conexoesCriadas': criadas,
        'conexoesAtualizadas': atualizadas,
        'ucs': resultado_ucs
    }

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

    producao_media, reserva, producao_disponivel = _producao_disponivel_usina(plant)
    if plant.producao_media() is None:
        warnings.append('Usina sem produção cadastrada (nem manual, nem mensal) -- preencha ao menos a produção média antes de calcular.')

    buffer_global_habilitado, buffer_global_percentual = _global_buffer_config()

    connections = PlantConnection.query.filter_by(plant_id=plant.id).all()

    resultado_ucs = []
    percentual_total_alocado = 0.0

    for connection in connections:
        uc = connection.consumer_unit
        if not uc:
            continue

        # n_usinas_extra=0 -- a conexão JÁ existe (é essa mesma que estamos
        # percorrendo), então já está contada na query de dentro da função.
        consumo_considerado, consumo_ajustado, percentual_calculado = _percentual_sugerido_uc(
            uc, producao_disponivel, buffer_global_habilitado, buffer_global_percentual, n_usinas_extra=0
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
            'consumoTotal': float(uc.consumo),
            'consumoConsiderado': consumo_considerado,
            'bufferPercentualAplicado': buffer_percentual_aplicado,
            'consumoAjustado': consumo_ajustado,
            'producaoConsiderada': consumo_ajustado,
            'percentualCalculado': percentual_calculado,
            'qualificado': qualificado,
            'motivoQualificacao': motivo_qualificacao
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


def _producao_disponivel_usina(plant: Plant) -> tuple[float, float, float]:
    """Retorna (producao_media, reserva_percentual, producao_disponivel).
    producao_media() já resolve sozinho manual vs. média dos 12 meses
    (ver models/plant.py)."""
    producao_media = plant.producao_media()
    if producao_media is None:
        producao_media = 0.0

    reserva = float(plant.reserva_percentual or 0)
    producao_disponivel = round(producao_media * (1 - reserva / 100), 2)
    return producao_media, reserva, producao_disponivel


def _buffer_percentual_uc(uc: ConsumerUnit, buffer_global_habilitado: bool, buffer_global_percentual: float) -> float:
    """Override da UC ganha do valor global, se preenchido. Sem override,
    só aplica se o toggle global (Configurações > Geral) estiver ligado."""
    if uc.buffer_percentual is not None:
        return float(uc.buffer_percentual)
    if buffer_global_habilitado:
        return buffer_global_percentual
    return 0.0


def _percentual_sugerido_uc(
    uc: ConsumerUnit,
    producao_disponivel: float,
    buffer_global_habilitado: bool,
    buffer_global_percentual: float,
    n_usinas_extra: int = 0
) -> tuple[float | None, float | None, float | None]:
    """Conta central do motor: consumo -> ajustado pelo buffer -> percentual
    da produção disponível. Reutilizada tanto pro cálculo final (UC já
    conectada) quanto pra pré-visualização de qualificação (UC candidata,
    ainda não conectada -- por isso o n_usinas_extra).
    Retorna (consumoConsiderado, consumoAjustado, percentual), todos None se
    a UC não tiver consumo cadastrado."""
    consumo_total = float(uc.consumo) if uc.consumo is not None else None
    if consumo_total is None:
        return None, None, None

    n_usinas_da_uc = (PlantConnection.query.filter_by(consumer_unit_id=uc.id).count() + n_usinas_extra) or 1
    consumo_considerado = round(consumo_total / n_usinas_da_uc, 2)

    buffer_percentual = _buffer_percentual_uc(uc, buffer_global_habilitado, buffer_global_percentual)
    consumo_ajustado = round(consumo_considerado * (1 + buffer_percentual / 100), 2)

    if producao_disponivel <= 0:
        percentual = 0.0
    else:
        percentual = round((consumo_ajustado / producao_disponivel) * 100, 2)

    return consumo_considerado, consumo_ajustado, percentual


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


def _global_buffer_config() -> tuple[bool, float]:
    """Valor padrão do buffer de consumo, configurado em Configurações >
    Geral (Setting key/value, mesma tabela usada por Aparência). Cada UC
    pode ter um valor próprio (ConsumerUnit.buffer_percentual) que ignora
    este padrão -- ver _buffer_percentual_uc."""
    settings = get_all_settings()
    habilitado = settings.get('rateioBufferHabilitado') == 'true'

    try:
        percentual = float(settings.get('rateioBufferPercentual') or 15)
    except (TypeError, ValueError):
        percentual = 15.0

    return habilitado, percentual


def _validar_competencia(competencia: str) -> None:
    try:
        datetime.strptime(competencia, '%Y-%m')
    except ValueError:
        raise ValueError('Competencia deve estar no formato YYYY-MM (ex.: 2026-08).')