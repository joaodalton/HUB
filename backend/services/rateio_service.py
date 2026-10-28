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
import uuid
from decimal import Decimal

from flask import g

from extensions import db
from models.plant import Plant
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.rateio_historico import RateioHistorico
from services.log_service import LogService
from services import rateio_math as rm
from services.rateio_calculo import (
    _calcular_usina,
    _checar_qualificacao,
    _conexoes_por_uc,
    _global_buffer_config,
    _percentual_sugerido_uc,
    _producao_disponivel_usina,
    _validar_competencia,
)


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
            'apelido': uc.apelido,
            'clienteNome': uc.client.nome if uc.client else None,
            'consumo': rm.to_float(uc.consumo),
            'diaEmissaoFatura': uc.dia_emissao_fatura,
            'percentualSugerido': rm.to_float(percentual_sugerido) if percentual_sugerido is not None else 0.0,
            'qualificado': qualificado,
            'motivo': motivo
        })

    return {
        'plantId': plant.id,
        'diaEmissaoUsina': plant.dia_emissao_usina,
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
    lote = str(uuid.uuid4())

    # Valida TODAS as usinas antes de escrever qualquer coisa (tudo ou nada,
    # mesma politica de confirmar_selecao/atualizar_distribuicao) -- sem isso,
    # aplicar_rateio recalculava e gravava percentual mesmo quando a soma dos
    # calculados ficava acima de 100% (o preview so devolvia 'excedeLimite'
    # como aviso, nada bloqueava a escrita de fato).
    atualizacoes = []
    for resultado in resultados:
        plant = _plant(resultado['plantId'])
        total_projetado = rm.ZERO

        for uc_resultado in resultado['ucs']:
            connection = PlantConnection.query.filter_by(
                plant_id=plant.id,
                consumer_unit_id=uc_resultado['ucId']
            ).first()

            if not connection:
                continue  # aplicar_rateio nao cria conexao nova -- isso e papel do confirmar_selecao

            novo_percentual = connection.percentual if connection.percentual_manual else rm.to_decimal(uc_resultado['percentualCalculado'])
            total_projetado += novo_percentual
            atualizacoes.append((plant, connection, uc_resultado, novo_percentual))

        total_projetado = rm.q2(total_projetado)
        if rm.excede_limite(total_projetado):
            raise ValueError(f'Rateio da usina "{plant.nome}" ficaria em {total_projetado}% -- excede 100%. Ajuste antes de aplicar.')

    for plant, connection, uc_resultado, novo_percentual in atualizacoes:
        if not connection.percentual_manual:
            connection.percentual = novo_percentual

        db.session.add(RateioHistorico(
            empresa_id=g.current_empresa_id,
            competencia=competencia,
            plant_id=plant.id,
            consumer_unit_id=uc_resultado['ucId'],
            percentual=rm.to_decimal(connection.percentual),
            consumo_considerado=rm.to_decimal(uc_resultado['consumoConsiderado']) if uc_resultado['consumoConsiderado'] is not None else None,
            producao_considerada=rm.to_decimal(uc_resultado['producaoConsiderada']) if uc_resultado['producaoConsiderada'] is not None else None,
            manual=connection.percentual_manual,
            lote=lote
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
    lote = str(uuid.uuid4())

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
            manual=True,
            lote=lote
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


def _agrupar_por_lote(registros: list['RateioHistorico']) -> dict[str, list['RateioHistorico']]:
    """Agrupa linhas de RateioHistorico pela execucao que as gravou.
    Linha antiga (de antes do campo lote existir) vira um grupo so dela --
    nao tem como juntar com outras retroativamente."""
    grupos: dict[str, list[RateioHistorico]] = {}
    for registro in registros:
        chave = registro.lote or f'legado-{registro.id}'
        grupos.setdefault(chave, []).append(registro)
    return grupos


def list_historico_execucoes(plant_id: int | None = None) -> list[dict]:
    """Tela de Historico (aba na pagina de Rateio): uma linha por EXECUCAO
    (aplicar_rateio ou confirmar_selecao), nao por UC -- mostra quando rodou
    e em qual usina. Clicar numa linha chama get_historico_execucao()."""
    query = RateioHistorico.query
    if plant_id:
        query = query.filter(RateioHistorico.plant_id == plant_id)

    registros = query.order_by(RateioHistorico.created_at.desc()).all()
    grupos = _agrupar_por_lote(registros)

    execucoes = []
    for lote, linhas in grupos.items():
        primeira = linhas[0]
        execucoes.append({
            'lote': lote,
            'plantId': primeira.plant_id,
            'usinaNome': primeira.plant.nome if primeira.plant else None,
            'competencia': primeira.competencia,
            'criadoEm': max(linha.created_at for linha in linhas).isoformat() if primeira.created_at else None,
            'quantidadeUcs': len(linhas)
        })

    execucoes.sort(key=lambda item: item['criadoEm'] or '', reverse=True)
    return execucoes


def get_historico_execucao(lote: str) -> dict:
    """Detalhe de uma execucao: percentual de cada UC NESSA execucao,
    comparado com a execucao anterior da MESMA usina (se existir), pra
    marcar cada UC como 'novo' (nao existia antes), 'alterado' (percentual
    mudou) ou 'igual' (mesma usina, mesmo percentual)."""
    linhas = RateioHistorico.query.filter(RateioHistorico.lote == lote).all()
    if not linhas:
        # fallback pro formato legado 'legado-<id>' (lote null, id da linha)
        if lote.startswith('legado-'):
            linha = RateioHistorico.query.filter_by(id=int(lote.removeprefix('legado-'))).first()
            linhas = [linha] if linha else []

    if not linhas:
        raise ValueError('Execucao de rateio nao encontrada.')

    plant_id = linhas[0].plant_id
    criado_em = max(linha.created_at for linha in linhas)

    # Acha a execucao anterior pelo LOTE, nao por created_at exato -- linhas
    # da mesma execucao podem ter microssegundos diferentes entre si (uma
    # chamada a datetime.utcnow() por linha), entao comparar timestamp
    # perdia UCs da propria execucao anterior.
    todas_da_usina = RateioHistorico.query.filter(RateioHistorico.plant_id == plant_id).all()
    grupos_da_usina = _agrupar_por_lote(todas_da_usina)
    grupos_ordenados = sorted(
        grupos_da_usina.items(),
        key=lambda item: max(linha.created_at for linha in item[1]),
        reverse=True
    )

    percentual_anterior_por_uc: dict[int, Decimal] = {}
    anterior_criado_em = None
    for grupo_lote, grupo_linhas in grupos_ordenados:
        if grupo_lote == lote or max(linha.created_at for linha in grupo_linhas) >= criado_em:
            continue
        anterior_criado_em = max(linha.created_at for linha in grupo_linhas)
        percentual_anterior_por_uc = {linha.consumer_unit_id: linha.percentual for linha in grupo_linhas}
        break

    ucs = []
    for linha in sorted(linhas, key=lambda item: (item.consumer_unit.codigo if item.consumer_unit else '')):
        anterior = percentual_anterior_por_uc.get(linha.consumer_unit_id)
        if anterior is None:
            status = 'novo'
        elif rm.to_decimal(anterior) == rm.to_decimal(linha.percentual):
            status = 'igual'
        else:
            status = 'alterado'

        uc_dict = linha.to_dict()
        uc_dict['percentualAnterior'] = rm.to_float(anterior) if anterior is not None else None
        uc_dict['status'] = status
        ucs.append(uc_dict)

    return {
        'lote': lote,
        'plantId': plant_id,
        'usinaNome': linhas[0].plant.nome if linhas[0].plant else None,
        'competencia': linhas[0].competencia,
        'criadoEm': criado_em.isoformat() if criado_em else None,
        'temExecucaoAnterior': anterior_criado_em is not None,
        'ucs': ucs
    }
