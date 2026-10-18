# backend/services/log_service.py
from flask import g, has_request_context

from extensions import db
from models.log_entry import LogEntry


def _session_has_uncommitted_work() -> bool:
    """True se a sessao tem mudancas pendentes (ainda nao flushadas) OU ja
    flushadas mas nao comitadas na transacao corrente."""
    session = db.session()
    if session.new or session.dirty or session.deleted:
        return True
    transaction = session.get_transaction()
    if transaction is None:
        return False
    # Snapshot que o SQLAlchemy mantem para restaurar objetos no rollback:
    # preenchido a cada flush, esvaziado no commit.
    return bool(
        getattr(transaction, '_new', None)
        or getattr(transaction, '_dirty', None)
        or getattr(transaction, '_deleted', None)
    )


class LogService:
    @staticmethod
    def _write(
        nivel: str,
        acao: str,
        mensagem: str,
        entidade: str | None = None,
        entidade_id: int | None = None,
        metadados: dict | None = None,
        empresa_id: int | None = None,
        strict: bool = False,
    ) -> None:
        empresa_id = empresa_id or (getattr(g, 'current_empresa_id', None) if has_request_context() else None)
        if empresa_id is None and metadados:
            empresa_id = metadados.get('empresaId')
        if empresa_id is None:
            if strict:
                raise RuntimeError('Empresa de auditoria obrigatoria.')
            return

        entry = LogEntry(
            empresa_id=empresa_id,
            nivel=nivel,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            mensagem=mensagem,
            metadados=metadados
        )
        # Se o chamador tem trabalho pendente na sessao, o log entra na MESMA
        # transacao (flush) e quem comita e o chamador -- antes, o commit daqui
        # persistia parcialmente loops de negocio (ex.: automacao_service).
        # Sessao limpa (log depois do commit do chamador) ou modo strict
        # (auditoria fail-closed da plataforma) comitam na hora.
        caller_owns_transaction = not strict and _session_has_uncommitted_work()
        try:
            db.session.add(entry)
            if caller_owns_transaction:
                db.session.flush()
            else:
                db.session.commit()
        except Exception:
            db.session.rollback()
            if strict:
                raise

    @staticmethod
    def info(acao: str, mensagem: str, entidade: str | None = None, entidade_id: int | None = None, metadados: dict | None = None, *, empresa_id: int | None = None, strict: bool = False) -> None:
        LogService._write('info', acao, mensagem, entidade, entidade_id, metadados, empresa_id, strict)

    @staticmethod
    def warning(acao: str, mensagem: str, entidade: str | None = None, entidade_id: int | None = None, metadados: dict | None = None) -> None:
        LogService._write('warning', acao, mensagem, entidade, entidade_id, metadados)

    @staticmethod
    def error(acao: str, mensagem: str, entidade: str | None = None, entidade_id: int | None = None, metadados: dict | None = None) -> None:
        LogService._write('error', acao, mensagem, entidade, entidade_id, metadados)

    @staticmethod
    def list_recent(limit: int = 50, nivel: str | None = None, entidade: str | None = None, entidade_id: int | None = None) -> list[dict]:
        query = LogEntry.query

        if nivel:
            query = query.filter(LogEntry.nivel == nivel)
        if entidade:
            query = query.filter(LogEntry.entidade == entidade)
        if entidade_id is not None:
            query = query.filter(LogEntry.entidade_id == entidade_id)

        entries = query.order_by(LogEntry.created_at.desc()).limit(limit).all()
        return [entry.to_dict() for entry in entries]
