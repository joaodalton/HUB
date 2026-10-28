# backend/services/automacao_regras.py
"""
Chaves de regra e deduplicacao do motor de automacao de pendencias.

Extraido de automacao_service.py (split por responsabilidade, sem mudanca de
comportamento). Ver automacao_service.py para a orquestracao principal.
"""
from models.pendencia import Pendencia

# Chave estruturada de cada regra automatica. Fica em Pendencia.metadados['regra']
# e e o que a deduplicacao e a auto-resolucao usam -- antes dependiam do texto
# do titulo (`ilike('%sem usina%')`): renomear a mensagem desligava a regra.
# Pendencias legadas (sem 'regra') continuam reconhecidas pelo titulo.
REGRA_UC_SEM_USINA = 'uc_sem_usina'
REGRA_CLIENTE_SEM_UC = 'cliente_sem_uc'
REGRA_CAMPOS_OBRIGATORIOS = 'campos_obrigatorios'
REGRA_DOCUMENTOS_OBRIGATORIOS = 'documentos_obrigatorios'
REGRA_FATURA_GERACAO_USINA = 'fatura_geracao_usina'
REGRA_FATURA_ERRO_EMISSAO = 'fatura_erro_emissao'
REGRA_CONTA_DESCONECTADA = 'conta_google_desconectada'
REGRA_SESSAO_USUARIO_INATIVO = 'sessao_usuario_inativo'
_TITULO_LEGADO = {
    REGRA_UC_SEM_USINA: 'sem usina',
    REGRA_CLIENTE_SEM_UC: 'sem uc',
    REGRA_CAMPOS_OBRIGATORIOS: 'falta ',
    REGRA_DOCUMENTOS_OBRIGATORIOS: 'falta documento',
}


def _regra_de(pendencia: Pendencia) -> str | None:
    metadados = pendencia.metadados or {}
    regra = metadados.get('regra') if isinstance(metadados, dict) else None
    if regra:
        return regra
    titulo = (pendencia.titulo or '').lower()
    # Ordem importa: 'falta documento' e mais especifico que 'falta '
    for chave in (REGRA_DOCUMENTOS_OBRIGATORIOS, REGRA_CAMPOS_OBRIGATORIOS, REGRA_UC_SEM_USINA, REGRA_CLIENTE_SEM_UC):
        if _TITULO_LEGADO[chave] in titulo:
            return chave
    return None


def _pendencias_abertas_por_regra() -> dict[str, list[Pendencia]]:
    """Uma query para todas as pendencias abertas de automacao, agrupadas por regra."""
    abertas = Pendencia.query.filter(Pendencia.status == 'aberta').all()
    grupos: dict[str, list[Pendencia]] = {}
    for pendencia in abertas:
        regra = _regra_de(pendencia)
        if regra:
            grupos.setdefault(regra, []).append(pendencia)
    return grupos


def _ja_existe_pendencia_ativa(
    cliente_id: int = None,
    uc_id: int = None,
    regra: str = None
) -> bool:
    """
    Verifica se já existe uma pendência/alerta/erro ativa (não resolvida, não cancelada)
    para o cliente ou UC especificada, opcionalmente da mesma regra automática.
    """
    query = Pendencia.query.filter(
        Pendencia.status == 'aberta'
    )

    if cliente_id:
        query = query.filter(Pendencia.client_id == cliente_id)
    if uc_id:
        query = query.filter(Pendencia.consumer_unit_id == uc_id)

    pendencias = query.all()

    if not regra:
        return len(pendencias) > 0

    return any(_regra_de(p) == regra for p in pendencias)
