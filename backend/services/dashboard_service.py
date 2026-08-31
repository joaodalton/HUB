"""Consultas agregadas para o painel operacional.

O dashboard não mantém uma tabela própria: todos os números são derivados dos
registros de origem na empresa ativa da requisição. Isso evita defasagem entre
uma pendência alterada e o que aparece no painel.
"""
from datetime import datetime, timedelta

from flask import g
from sqlalchemy import case, func

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.pendencia import Pendencia
from models.plant import Plant
from services.permission_service import can


_PRIORIDADE_ORDEM = case(
    (Pendencia.prioridade == 'critica', 0),
    (Pendencia.prioridade == 'alta', 1),
    (Pendencia.prioridade == 'media', 2),
    else_=3,
)
_PRAZO_AUSENTE_ORDENACAO = case((Pendencia.prazo.is_(None), 1), else_=0)


def _contar_por_status(model) -> dict[str, int]:
    rows = (
        db.session.query(model.status, func.count(model.id))
        .filter(model.empresa_id == g.current_empresa_id)
        .group_by(model.status)
        .all()
    )
    return {status: total for status, total in rows}


def _contar_documentos_por_categoria() -> dict[str, int]:
    rows = (
        db.session.query(Document.category_id, func.count(Document.id))
        .filter(Document.empresa_id == g.current_empresa_id)
        .group_by(Document.category_id)
        .all()
    )
    # Categorias são globais hoje; usar o id preserva o dado mesmo que a
    # categoria seja renomeada ou removida no futuro.
    return {str(category_id) if category_id is not None else 'semCategoria': total
            for category_id, total in rows}


def _metricas_de_entidade(model, permission: str, *, status: bool = False) -> dict:
    if not can(g.current_user, permission):
        return {'disponivel': False, 'total': None, **({'porStatus': None} if status else {})}

    result = {
        'disponivel': True,
        'total': db.session.query(func.count(model.id)).filter(
            model.empresa_id == g.current_empresa_id
        ).scalar() or 0,
    }
    if status:
        result['porStatus'] = _contar_por_status(model)
    return result


def get_resumo_operacional() -> dict:
    """Retorna o retrato operacional da empresa atualmente autenticada."""
    agora = datetime.utcnow()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fim_proximos_sete_dias = agora + timedelta(days=7)
    abertas = Pendencia.status == 'aberta'
    empresa = Pendencia.empresa_id == g.current_empresa_id

    vencidas = db.session.query(func.count(Pendencia.id)).filter(
        empresa, abertas, Pendencia.prazo.isnot(None), Pendencia.prazo < agora
    ).scalar() or 0
    vencendo_em_sete_dias = db.session.query(func.count(Pendencia.id)).filter(
        empresa, abertas, Pendencia.prazo.isnot(None),
        Pendencia.prazo >= agora, Pendencia.prazo <= fim_proximos_sete_dias
    ).scalar() or 0
    resolvidas_no_mes = db.session.query(func.count(Pendencia.id)).filter(
        empresa, Pendencia.status == 'resolvida', Pendencia.resolved_at >= inicio_mes
    ).scalar() or 0

    fila = (
        Pendencia.query.filter(empresa, abertas)
        .order_by(_PRIORIDADE_ORDEM, _PRAZO_AUSENTE_ORDENACAO, Pendencia.prazo.asc(), Pendencia.created_at.asc())
        .limit(10)
        .all()
    )

    documentos = _metricas_de_entidade(Document, 'documents.read')
    if documentos['disponivel']:
        documentos['porCategoria'] = _contar_documentos_por_categoria()
    else:
        documentos['porCategoria'] = None

    return {
        'geradoEm': agora.isoformat(),
        'pendencias': {
            'abertas': db.session.query(func.count(Pendencia.id)).filter(empresa, abertas).scalar() or 0,
            'vencidas': vencidas,
            'vencendoEm7Dias': vencendo_em_sete_dias,
            'resolvidasNoMes': resolvidas_no_mes,
            'fila': [pendencia.to_dict() for pendencia in fila],
        },
        'clientes': _metricas_de_entidade(Client, 'clients.read', status=True),
        'ucs': _metricas_de_entidade(ConsumerUnit, 'consumer_units.read'),
        'usinas': _metricas_de_entidade(Plant, 'plants.read', status=True),
        'documentos': documentos,
    }
