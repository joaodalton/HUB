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
from decimal import Decimal

from flask import g
from sqlalchemy import func

from extensions import db
from models.plant import Plant
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.rateio_historico import RateioHistorico
from services.log_service import LogService
from services import rateio_math as rm
from services.settings_service import get_all_settings


def _plant(plant_id: int):
    return Plant.query.filter_by(id=plant_id, empresa_id=g.current_empresa_id).first()


def _uc(uc_id: int):
    return ConsumerUnit.query.filter_by(id=uc_id, empresa_id=g.current_empresa_id).first()


def preview_rateio(plant_id: int | None = None) -> list[dict]:
    plants = [_plant(plant_id)] if plant_id else Plant.query.all()
    plants = [p for p in plants if p]
    return [_calcular_usina(plant) for plant in plants]


def funil_qualificacao(plant_id: int) -> dict:
    """Funil da Tela 3. Candidatas = UCs ainda NÃO conectadas a esta usina.
    'Qualificado' = passou na checagem de janela de leitura. Cada UC também
    já vem com o percentual que ela CONSUMIRIA se fosse conectada agora,
    pra montar a lista de seleção sem precisar de uma segunda chamada."""
    plant = _plant(plant_id)
    if not plant:
        raise ValueError('Usina nao encontrada.')

    _, _, producao_disponivel = _producao_disponivel_usina(plant)
    buffer_global_habilitado, buffer_global_percentual = _global_buffer_config()

    ja_conectadas_ids = {c.consumer_unit_id for c in PlantConnection.query.filter_by(plant_id=plant.id).all()}
    candidatas = [uc for uc in ConsumerUnit.query.all() if uc.id not in ja_conectadas_ids]
    n_usinas_por_uc = _conexoes_por_uc()

    ucs_resultado = []
    qualificados = 0

    for uc in candidatas:
        qualificado, motivo = _checar_qualificacao(plant, uc)

        # n_usinas_extra=1 -- essa UC ainda não tem conexão com ESTA usina,
        # então o cálculo simula "e se ela entrasse aqui também", somando 1
        # às conexões que ela já tem com outras usinas (se houver).
        _, _, percentual_sugerido = _percentual_sugerido_uc(
            uc, producao_disponivel, buffer_global_habilitado, buffer_global_percentual,
            n_usinas_extra=1, n_usinas_por_uc=n_usinas_por_uc,
        )

        if qualificado:
            qualificados += 1

        ucs_resultado.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'clienteNome': uc.client.nome if uc.client else None,
            'consumo': rm.to_float(uc.consumo),
            'percentualSugerido': rm.to_float(percentual_sugerido) if percentual_sugerido is not None else 0.0,
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
        plant = _plant(resultado['plantId'])

        for uc_resultado in resultado['ucs']:
            connection = PlantConnection.query.filter_by(
                plant_id=plant.id,
                consumer_unit_id=uc_resultado['ucId']
            ).first()

            if not connection:
                continue  # aplicar_rateio nao cria conexao nova -- isso e papel do confirmar_selecao

            if not connection.percentual_manual:
                connection.percentual = rm.to_decimal(uc_resultado['percentualCalculado'])

            db.session.add(RateioHistorico(
                empresa_id=g.current_empresa_id,
                competencia=competencia,
                plant_id=plant.id,
                consumer_unit_id=uc_resultado['ucId'],
                percentual=rm.to_decimal(connection.percentual),
                consumo_considerado=rm.to_decimal(uc_resultado['consumoConsiderado']) if uc_resultado['consumoConsiderado'] is not None else None,
                producao_considerada=rm.to_decimal(uc_resultado['producaoConsiderada']) if uc_resultado['producaoConsiderada'] is not None else None,
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

    plant = _plant(plant_id)
    if not plant:
        raise ValueError('Usina nao encontrada.')

    if not selecoes:
        raise ValueError('Nenhum cliente selecionado.')

    selecoes_por_uc: dict[int, Decimal] = {}
    for selecao in selecoes:
        uc_id = selecao.get('ucId')
        percentual = selecao.get('percentual')
        if uc_id and percentual is not None:
            try:
                selecoes_por_uc[int(uc_id)] = rm.validar_percentual(percentual, campo=f'Percentual da UC id={uc_id}')
            except (TypeError, ValueError) as exc:
                raise ValueError(str(exc) if isinstance(exc, ValueError) and 'UC id=' in str(exc) else f'Percentual invalido para a UC id={uc_id}.')

    if not selecoes_por_uc:
        raise ValueError('Nenhuma UC valida na selecao.')

    # Checa qualificacao de cada UC antes de criar/atualizar qualquer conexao.
    # Reusa _checar_qualificacao() que o funil e o preview_rateio ja usam --
    # se uma UC nao for qualificada para esta competencia, aborta com a lista
    # de motivos (mesma assinatura de erro que o aplicar_rateio usa para outros
    # validations, pra nao introduzir um segundo formato de erro).
    ucs_nao_qualificadas = []
    for uc_id in selecoes_por_uc:
        uc = _uc(uc_id)
        if not uc:
            raise ValueError(f'UC id={uc_id} nao encontrada.')

        qualificado, motivo = _checar_qualificacao(plant, uc)
        if not qualificado:
            ucs_nao_qualificadas.append({
                'ucId': uc_id,
                'codigo': uc.codigo,
                'clienteNome': uc.client.nome if uc.client else None,
                'motivo': motivo
            })

    if ucs_nao_qualificadas:
        motivos = '; '.join(
            f"UC {u['codigo']} ({u['clienteNome'] or 'cliente nao encontrado'}): {u['motivo']}"
            for u in ucs_nao_qualificadas
        )
        raise ValueError(
            'Nenhuma das UCs informadas esta qualificada para esta competencia '
            f'(motivos: {motivos}).'
        )

    conexoes_existentes = PlantConnection.query.filter_by(plant_id=plant.id).all()
    conexoes_por_uc_id = {c.consumer_unit_id: c for c in conexoes_existentes}

    soma_total = rm.soma_percentuais(
        [c.percentual for c in conexoes_existentes if c.consumer_unit_id not in selecoes_por_uc]
        + list(selecoes_por_uc.values())
    )

    if rm.excede_limite(soma_total):
        raise ValueError(f'Soma dos percentuais desta usina ficaria em {soma_total}% -- excede 100%. Ajuste antes de confirmar.')

    _, _, producao_disponivel = _producao_disponivel_usina(plant)

    criadas = 0
    atualizadas = 0
    resultado_ucs = []

    for uc_id, percentual in selecoes_por_uc.items():
        uc = _uc(uc_id)

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
                empresa_id=g.current_empresa_id,
                percentual=percentual,
                percentual_manual=True
            )
            db.session.add(connection)
            criadas += 1

        db.session.flush()

        producao_considerada = rm.producao_considerada(percentual, producao_disponivel)

        db.session.add(RateioHistorico(
            empresa_id=g.current_empresa_id,
            competencia=competencia,
            plant_id=plant.id,
            consumer_unit_id=uc.id,
            percentual=percentual,
            consumo_considerado=uc.consumo,
            producao_considerada=producao_considerada,
            manual=True
        ))

        resultado_ucs.append({
            'ucId': uc.id,
            'ucCodigo': uc.codigo,
            'clienteNome': uc.client.nome if uc.client else None,
            'percentual': rm.to_float(percentual)
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

def atualizar_distribuicao(plant_id: int, atualizacoes: list[dict]) -> dict:
    """Edita o percentual de conexões QUE JÁ EXISTEM nesta usina -- usado
    pelo botão 'Editar distribuição' na tela de Usina (diferente de
    confirmar_selecao, que só roda dentro do wizard e pode CRIAR conexão
    nova). Marca percentual_manual=True em cada uma editada (decisão
    humana explícita). Valida que a soma de TODAS as conexões da usina
    depois do update (as editadas + as que não foram tocadas) não passa de
    100% -- se passar, nada é gravado (tudo ou nada)."""
    plant = _plant(plant_id)
    if not plant:
        raise ValueError('Usina nao encontrada.')

    if not atualizacoes:
        raise ValueError('Nenhuma atualizacao informada.')

    percentual_por_connection_id: dict[int, Decimal] = {}
    for item in atualizacoes:
        connection_id = item.get('connectionId')
        percentual = item.get('percentual')

        if connection_id is None or percentual is None:
            continue

        try:
            percentual_por_connection_id[int(connection_id)] = rm.validar_percentual(percentual, campo=f'Percentual da conexao id={connection_id}')
        except (TypeError, ValueError) as exc:
            raise ValueError(str(exc) if 'conexao id=' in str(exc) else f'Percentual invalido para a conexao id={connection_id}.')

    if not percentual_por_connection_id:
        raise ValueError('Nenhuma atualizacao valida.')

    conexoes = PlantConnection.query.filter_by(plant_id=plant.id).all()
    conexoes_por_id = {c.id: c for c in conexoes}

    for connection_id in percentual_por_connection_id:
        if connection_id not in conexoes_por_id:
            raise ValueError(f'Conexao id={connection_id} nao pertence a esta usina.')

    soma_total = rm.soma_percentuais(
        percentual_por_connection_id.get(c.id, c.percentual) for c in conexoes
    )

    if rm.excede_limite(soma_total):
        raise ValueError(f'Soma dos percentuais desta usina ficaria em {soma_total}% -- excede 100%. Ajuste antes de salvar.')

    for connection_id, percentual in percentual_por_connection_id.items():
        connection = conexoes_por_id[connection_id]
        connection.percentual = percentual
        connection.percentual_manual = True

    db.session.commit()

    LogService.info(
        acao='atualizar_distribuicao',
        mensagem=f'{len(percentual_por_connection_id)} percentual(is) atualizado(s) manualmente na usina "{plant.nome}"',
        entidade='PlantConnection',
        metadados={'plantId': plant.id}
    )

    return {
        'plantId': plant.id,
        'conexoes': [c.to_dict() for c in conexoes]
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
