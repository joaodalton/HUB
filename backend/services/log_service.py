# backend/services/log_service.py
from extensions import db
from models.log_entry import LogEntry


class LogService:
    @staticmethod
    def _write(
        nivel: str,
        acao: str,
        mensagem: str,
        entidade: str | None = None,
        entidade_id: int | None = None,
        metadados: dict | None = None
    ) -> None:
        entry = LogEntry(
            nivel=nivel,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            mensagem=mensagem,
            metadados=metadados
        )
        try:
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    @staticmethod
    def info(acao: str, mensagem: str, entidade: str | None = None, entidade_id: int | None = None, metadados: dict | None = None) -> None:
        LogService._write('info', acao, mensagem, entidade, entidade_id, metadados)

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