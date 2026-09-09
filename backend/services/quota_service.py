"""Enforcement de limite de recurso por empresa (Sprint A)."""
from models.assinatura import Assinatura
from models.limite_contratado import LimiteContratado
from planos.catalogo import get_plano


def _contar_clientes(empresa_id: int) -> int:
    from models.client import Client
    return Client.query.filter_by(empresa_id=empresa_id).count()


def _contar_ucs(empresa_id: int) -> int:
    from models.consumer_unit import ConsumerUnit
    return ConsumerUnit.query.filter_by(empresa_id=empresa_id).count()


def _contar_usinas(empresa_id: int) -> int:
    from models.plant import Plant
    return Plant.query.filter_by(empresa_id=empresa_id).count()


def _contar_usuarios(empresa_id: int) -> int:
    from models.user import User
    return User.query.filter_by(empresa_id=empresa_id).count()


_CONTADORES = {
    'clientes': _contar_clientes,
    'ucs': _contar_ucs,
    'usinas': _contar_usinas,
    'usuarios': _contar_usuarios,
}


def get_assinatura(empresa_id: int) -> Assinatura | None:
    return Assinatura.query.filter_by(empresa_id=empresa_id).first()


def get_limite(empresa_id: int, recurso: str) -> int | None:
    """None e ilimitado; assinatura ausente falha aberta por seguranca operacional."""
    assinatura = get_assinatura(empresa_id)
    if not assinatura or assinatura.tipo == 'vitalicio':
        return None

    franquia = get_plano(assinatura.plano_chave)['franquia'].get(recurso, 0)
    excedente = LimiteContratado.query.filter_by(empresa_id=empresa_id, recurso=recurso).first()
    return max(franquia, excedente.quantidade_contratada) if excedente else franquia


def verificar_cota(empresa_id: int, recurso: str) -> tuple[bool, int, int | None]:
    """Retorna permitido, uso atual e limite; limite None representa ilimitado."""
    limite = get_limite(empresa_id, recurso)
    if limite is None:
        return True, 0, None

    uso_atual = _CONTADORES[recurso](empresa_id)
    return uso_atual < limite, uso_atual, limite
