# backend/services/pendencia_service.py
from datetime import datetime

from flask import g
from sqlalchemy.orm import selectinload

from extensions import db
from models.pendencia import Pendencia, PendenciaComentario, PRIORIDADES, RESPONSAVEL_TIPOS
from models.user import ROLES
from services.log_service import LogService
from utils.pagination import paginate

def _tenant(model, identifier): return model.query.filter_by(id=identifier, empresa_id=g.current_empresa_id).first()


def _resolver_responsavel(data: dict, empresa_id: int, atual_tipo: str, atual_id, atual_cargo):
    """Valida e resolve responsavel_id/responsavel_tipo/responsavel_cargo a
    partir do payload, preservando valores atuais quando a chave nao vem no
    payload (semantica de update parcial). Garante a exclusividade: tipo
    'cargo' zera responsavel_id, tipo 'usuario' zera responsavel_cargo."""
    tipo = data.get('responsavelTipo', atual_tipo)
    if tipo not in RESPONSAVEL_TIPOS:
        raise ValueError(f'responsavelTipo invalido. Use uma de: {", ".join(RESPONSAVEL_TIPOS)}.')

    if tipo == 'cargo':
        cargo = data.get('responsavelCargo', atual_cargo)
        if cargo not in ROLES:
            raise ValueError(f'responsavelCargo invalido. Use uma de: {", ".join(ROLES)}.')
        return None, tipo, cargo

    # tipo == 'usuario'
    responsavel_id = data.get('responsavelId', atual_id)
    if responsavel_id:
        from models.user import User
        responsavel = User.query.filter_by(id=responsavel_id, empresa_id=empresa_id).first()
        if not responsavel:
            raise ValueError('Responsavel pertence a outra empresa.')
    return responsavel_id, tipo, None


def list_pendencias(filtros: dict, page: int = 1, page_size: int = 50) -> tuple[list[dict], dict]:
    # Filtro automatico via TenantMixin (extensions.py)
    query = Pendencia.query.options(
        selectinload(Pendencia.client),
        selectinload(Pendencia.consumer_unit),
        selectinload(Pendencia.plant),
        selectinload(Pendencia.document),
        selectinload(Pendencia.responsavel),
        selectinload(Pendencia.comentarios).selectinload(PendenciaComentario.autor),
    )

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

    query = query.order_by(Pendencia.created_at.desc())
    pendencias, pagination = paginate(query, page, page_size)
    return [pendencia.to_dict() for pendencia in pendencias], pagination


def get_pendencia(pendencia_id: int) -> dict | None:
    pendencia = _tenant(Pendencia, pendencia_id)
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
    # Antes so aceitava categoria de uma lista fixa (CATEGORIAS_POR_TIPO) --
    # agora qualquer string nao-vazia e aceita, pra permitir categoria nova
    # criada na hora pelo usuario (ver frontend: pendenciaCategoriasService.ts,
    # que guarda as extras na tabela Setting generica). CATEGORIAS_PADRAO em
    # models/pendencia.py continua existindo, so deixou de ser uma trava --
    # vira sugestao inicial no dropdown do frontend.
    categoria = (data.get('categoria') or '').strip()

    if not categoria:
        raise ValueError('Categoria e obrigatoria.')

    prioridade = data.get('prioridade', 'media')
    if prioridade not in PRIORIDADES:
        raise ValueError(
            f'Prioridade invalida. Use uma de: {", ".join(PRIORIDADES)}.'
        )

    # Validação de referências cruzadas entre empresas.
    # Uma pendência não pode apontar para cliente/UC/planta/document de
    # outra empresa. Isso protege contra vazamento de referências cruzadas
    # mesmo quando o frontend (ou um request malicioso) envia IDs livres.
    empresa_id = g.current_empresa_id

    if data.get('clienteId'):
        from models.client import Client
        cliente = _tenant(Client, data['clienteId'])
        if not cliente or cliente.empresa_id != empresa_id:
            raise ValueError('Cliente pertence a outra empresa.')

    if data.get('ucId'):
        from models.consumer_unit import ConsumerUnit
        uc = _tenant(ConsumerUnit, data['ucId'])
        if not uc or uc.empresa_id != empresa_id:
            raise ValueError('UC pertence a outra empresa.')

    if data.get('usinaId'):
        from models.plant import Plant
        planta = _tenant(Plant, data['usinaId'])
        if not planta or planta.empresa_id != empresa_id:
            raise ValueError('Usina pertence a outra empresa.')

    if data.get('documentoId'):
        from models.document import Document
        doc = _tenant(Document, data['documentoId'])
        if not doc or doc.empresa_id != empresa_id:
            raise ValueError('Documento pertence a outra empresa.')

    # Responsavel pode ser um usuario fixo ou um cargo (ver models/pendencia.py
    # RESPONSAVEL_TIPOS). _resolver_responsavel aplica a exclusividade e a
    # validacao de tenant (User não usa TenantMixin, login precisa achar por
    # email antes de ter empresa na sessão -- por isso o filtro manual).
    responsavel_id, responsavel_tipo, responsavel_cargo = _resolver_responsavel(
        data, empresa_id, atual_tipo='usuario', atual_id=None, atual_cargo=None
    )

    pendencia = Pendencia(
        empresa_id=g.current_empresa_id,
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
        responsavel_id=responsavel_id,
        responsavel_tipo=responsavel_tipo,
        responsavel_cargo=responsavel_cargo,
        metadados=data.get('metadados')
    )
    db.session.add(pendencia)
    db.session.commit()

    LogService.info(
        acao='create',
        mensagem=f'{tipo.capitalize()} "{pendencia.titulo}" criada ({origem})',
        entidade='Pendencia',
        entidade_id=pendencia.id
    )
    return pendencia.to_dict()


def update_pendencia(pendencia_id: int, data: dict) -> dict | None:
    pendencia = _tenant(Pendencia, pendencia_id)
    if not pendencia:
        return None

    # Validação de referências cruzadas também em update.
    if 'clienteId' in data and data['clienteId'] is not None:
        from models.client import Client
        cliente = _tenant(Client, data['clienteId'])
        if not cliente or cliente.empresa_id != g.current_empresa_id:
            raise ValueError('Cliente pertence a outra empresa.')
        pendencia.client_id = data['clienteId']

    if 'ucId' in data and data['ucId'] is not None:
        from models.consumer_unit import ConsumerUnit
        uc = _tenant(ConsumerUnit, data['ucId'])
        if not uc or uc.empresa_id != g.current_empresa_id:
            raise ValueError('UC pertence a outra empresa.')
        pendencia.consumer_unit_id = data['ucId']

    if 'usinaId' in data and data['usinaId'] is not None:
        from models.plant import Plant
        planta = _tenant(Plant, data['usinaId'])
        if not planta or planta.empresa_id != g.current_empresa_id:
            raise ValueError('Usina pertence a outra empresa.')
        pendencia.plant_id = data['usinaId']

    if 'documentoId' in data and data['documentoId'] is not None:
        from models.document import Document
        doc = _tenant(Document, data['documentoId'])
        if not doc or doc.empresa_id != g.current_empresa_id:
            raise ValueError('Documento pertence a outra empresa.')
        pendencia.document_id = data['documentoId']

    if 'responsavelId' in data or 'responsavelTipo' in data or 'responsavelCargo' in data:
        responsavel_id, responsavel_tipo, responsavel_cargo = _resolver_responsavel(
            data, g.current_empresa_id,
            atual_tipo=pendencia.responsavel_tipo,
            atual_id=pendencia.responsavel_id,
            atual_cargo=pendencia.responsavel_cargo
        )
        pendencia.responsavel_id = responsavel_id
        pendencia.responsavel_tipo = responsavel_tipo
        pendencia.responsavel_cargo = responsavel_cargo

    if 'categoria' in data:
        categoria = (data['categoria'] or '').strip()
        if not categoria:
            raise ValueError('Categoria e obrigatoria.')
        pendencia.categoria = categoria

    if 'prioridade' in data:
        if data['prioridade'] not in PRIORIDADES:
            raise ValueError('Prioridade invalida.')
        pendencia.prioridade = data['prioridade']

    pendencia.titulo = data.get('titulo', pendencia.titulo).strip()
    pendencia.descricao = data.get('descricao', pendencia.descricao)
    pendencia.prazo = _parse_datetime(data['prazo']) if 'prazo' in data else pendencia.prazo

    db.session.commit()
    LogService.info(
        acao='update',
        mensagem=f'"{pendencia.titulo}" atualizada',
        entidade='Pendencia',
        entidade_id=pendencia.id
    )
    return pendencia.to_dict()


def resolver_pendencia(pendencia_id: int) -> dict | None:
    pendencia = _tenant(Pendencia, pendencia_id)
    if not pendencia:
        return None
    pendencia.status = 'resolvida'
    pendencia.resolved_at = datetime.utcnow()
    db.session.commit()
    LogService.info(
        acao='resolver',
        mensagem=f'"{pendencia.titulo}" resolvida',
        entidade='Pendencia',
        entidade_id=pendencia.id
    )
    return pendencia.to_dict()


def cancelar_pendencia(pendencia_id: int) -> dict | None:
    pendencia = _tenant(Pendencia, pendencia_id)
    if not pendencia:
        return None
    pendencia.status = 'cancelada'
    db.session.commit()
    LogService.info(
        acao='cancelar',
        mensagem=f'"{pendencia.titulo}" cancelada',
        entidade='Pendencia',
        entidade_id=pendencia.id
    )
    return pendencia.to_dict()


def reabrir_pendencia(pendencia_id: int) -> dict | None:
    pendencia = _tenant(Pendencia, pendencia_id)
    if not pendencia:
        return None
    pendencia.status = 'aberta'
    pendencia.resolved_at = None
    db.session.commit()
    LogService.info(
        acao='reabrir',
        mensagem=f'"{pendencia.titulo}" reaberta',
        entidade='Pendencia',
        entidade_id=pendencia.id
    )
    return pendencia.to_dict()


def delete_pendencia(pendencia_id: int) -> bool:
    pendencia = _tenant(Pendencia, pendencia_id)
    if not pendencia:
        return False
    db.session.delete(pendencia)
    db.session.commit()
    return True


def adicionar_comentario(pendencia_id: int, texto: str, autor_id: int | None) -> dict | None:
    pendencia = _tenant(Pendencia, pendencia_id)
    if not pendencia:
        return None
    # Validação de referência cruzada: a pendência deve pertencer à empresa
    # do usuário que está adicionando o comentário.
    if pendencia.empresa_id != g.current_empresa_id:
        raise ValueError('Pendencia pertence a outra empresa.')
    comentario = PendenciaComentario(
        empresa_id=g.current_empresa_id,
        pendencia_id=pendencia_id,
        autor_id=autor_id,
        texto=texto.strip()
    )
    db.session.add(comentario)
    db.session.commit()
    LogService.info(
        acao='comentario',
        mensagem='Comentario adicionado',
        entidade='Pendencia',
        entidade_id=pendencia.id
    )
    return pendencia.to_dict()


def _parse_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, '%Y-%m-%d')
