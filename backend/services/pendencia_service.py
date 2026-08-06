# backend/services/pendencia_service.py
from datetime import datetime

from extensions import db
from models.pendencia import CATEGORIAS_POR_TIPO, Pendencia, PendenciaComentario, PRIORIDADES
from services.log_service import LogService


def list_pendencias(filtros: dict) -> list[dict]:
    query = Pendencia.query

    if filtros.get('tipo'):
        query = query.filter(Pendencia.tipo == filtros['tipo'])
    if filtros.get('categoria'):
        query = query.filter(Pendencia.categoria == filtros['categoria'])
    if filtros.get('origem'):
        query = query.filter(Pendencia.origem == filtros['origem'])
    if filtros.get('status'):
        query = query.filter(Pendencia.status == filtros['status'])
    if filtros.get('prioridade'):
        query = query.filter(Pendencia.prioridade == filtros['prioridade'])
    if filtros.get('responsavelId'):
        query = query.filter(Pendencia.responsavel_id == filtros['responsavelId'])
    if filtros.get('clienteId'):
        query = query.filter(Pendencia.client_id == filtros['clienteId'])

    pendencias = query.order_by(Pendencia.created_at.desc()).all()
    return [pendencia.to_dict() for pendencia in pendencias]


def get_pendencia(pendencia_id: int) -> dict | None:
    pendencia = Pendencia.query.get(pendencia_id)
    return pendencia.to_dict() if pendencia else None


def get_resumo() -> dict:
    abertas = Pendencia.query.filter(Pendencia.status == 'aberta')
    return {
        'pendencias': abertas.filter(Pendencia.tipo == 'pendencia').count(),
        'alertas': abertas.filter(Pendencia.tipo == 'alerta').count(),
        'erros': abertas.filter(Pendencia.tipo == 'erro').count()
    }


def criar_pendencia_manual(data: dict) -> dict:
    return _criar(tipo='pendencia', origem=data.get('origem') or 'Manual', data=data)


def criar_alerta(data: dict) -> dict:
    return _criar(tipo='alerta', origem=data.get('origem') or 'Sistema', data=data)


def criar_erro(data: dict) -> dict:
    return _criar(tipo='erro', origem=data.get('origem') or 'Sistema', data=data)


def _criar(tipo: str, origem: str, data: dict) -> dict:
    categoria = data.get('categoria')
    categorias_validas = CATEGORIAS_POR_TIPO.get(tipo, ())

    if categoria not in categorias_validas:
        raise ValueError(f'Categoria invalida para o tipo "{tipo}". Use uma de: {", ".join(categorias_validas)}.')

    prioridade = data.get('prioridade', 'media')
    if prioridade not in PRIORIDADES:
        raise ValueError(f'Prioridade invalida. Use uma de: {", ".join(PRIORIDADES)}.')

    pendencia = Pendencia(
        tipo=tipo,
        categoria=categoria,
        origem=origem,
        titulo=data.get('titulo', '').strip(),
        descricao=data.get('descricao'),
        client_id=data.get('clienteId'),
        consumer_unit_id=data.get('ucId'),
        plant_id=data.get('usinaId'),
        document_id=data.get('documentoId'),
        prazo=_parse_datetime(data.get('prazo')),
        prioridade=prioridade,
        responsavel_id=data.get('responsavelId'),
        metadados=data.get('metadados')
    )
    db.session.add(pendencia)
    db.session.commit()

    LogService.info(acao='create', mensagem=f'{tipo.capitalize()} "{pendencia.titulo}" criada ({origem})', entidade='Pendencia', entidade_id=pendencia.id)
    return pendencia.to_dict()


def update_pendencia(pendencia_id: int, data: dict) -> dict | None:
    pendencia = Pendencia.query.get(pendencia_id)
    if not pendencia:
        return None

    if 'categoria' in data:
        categorias_validas = CATEGORIAS_POR_TIPO.get(pendencia.tipo, ())
        if data['categoria'] not in categorias_validas:
            raise ValueError(f'Categoria invalida para o tipo "{pendencia.tipo}".')
        pendencia.categoria = data['categoria']

    if 'prioridade' in data:
        if data['prioridade'] not in PRIORIDADES:
            raise ValueError('Prioridade invalida.')
        pendencia.prioridade = data['prioridade']

    pendencia.titulo = data.get('titulo', pendencia.titulo).strip()
    pendencia.descricao = data.get('descricao', pendencia.descricao)
    pendencia.client_id = data.get('clienteId', pendencia.client_id)
    pendencia.consumer_unit_id = data.get('ucId', pendencia.consumer_unit_id)
    pendencia.plant_id = data.get('usinaId', pendencia.plant_id)
    pendencia.document_id = data.get('documentoId', pendencia.document_id)
    pendencia.prazo = _parse_datetime(data['prazo']) if 'prazo' in data else pendencia.prazo
    pendencia.responsavel_id = data.get('responsavelId', pendencia.responsavel_id)

    db.session.commit()
    LogService.info(acao='update', mensagem=f'"{pendencia.titulo}" atualizada', entidade='Pendencia', entidade_id=pendencia.id)
    return pendencia.to_dict()


def resolver_pendencia(pendencia_id: int) -> dict | None:
    pendencia = Pendencia.query.get(pendencia_id)
    if not pendencia:
        return None
    pendencia.status = 'resolvida'
    pendencia.resolved_at = datetime.utcnow()
    db.session.commit()
    LogService.info(acao='resolver', mensagem=f'"{pendencia.titulo}" resolvida', entidade='Pendencia', entidade_id=pendencia.id)
    return pendencia.to_dict()


def cancelar_pendencia(pendencia_id: int) -> dict | None:
    pendencia = Pendencia.query.get(pendencia_id)
    if not pendencia:
        return None
    pendencia.status = 'cancelada'
    db.session.commit()
    LogService.info(acao='cancelar', mensagem=f'"{pendencia.titulo}" cancelada', entidade='Pendencia', entidade_id=pendencia.id)
    return pendencia.to_dict()


def reabrir_pendencia(pendencia_id: int) -> dict | None:
    pendencia = Pendencia.query.get(pendencia_id)
    if not pendencia:
        return None
    pendencia.status = 'aberta'
    pendencia.resolved_at = None
    db.session.commit()
    LogService.info(acao='reabrir', mensagem=f'"{pendencia.titulo}" reaberta', entidade='Pendencia', entidade_id=pendencia.id)
    return pendencia.to_dict()


def delete_pendencia(pendencia_id: int) -> bool:
    pendencia = Pendencia.query.get(pendencia_id)
    if not pendencia:
        return False
    db.session.delete(pendencia)
    db.session.commit()
    return True


def adicionar_comentario(pendencia_id: int, texto: str, autor_id: int | None) -> dict | None:
    pendencia = Pendencia.query.get(pendencia_id)
    if not pendencia:
        return None
    comentario = PendenciaComentario(pendencia_id=pendencia_id, autor_id=autor_id, texto=texto.strip())
    db.session.add(comentario)
    db.session.commit()
    LogService.info(acao='comentario', mensagem='Comentario adicionado', entidade='Pendencia', entidade_id=pendencia.id)
    return pendencia.to_dict()


def _parse_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, '%Y-%m-%d')