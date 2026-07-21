# backend/services/log_service.py
from extensions import db
from models.log_entry import LogEntry


class LogService:
    @staticmethod
    def _write(nivel: str, acao: str, mensagem: str, entidade: str | None = None, metadados: dict | None = None) -> None:
        entry = LogEntry(
            nivel=nivel,
            acao=acao,
            entidade=entidade,
            mensagem=mensagem,
            metadados=metadados
        )
        try:
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    @staticmethod
    def info(acao: str, mensagem: str, entidade: str | None = None, metadados: dict | None = None) -> None:
        LogService._write('info', acao, mensagem, entidade, metadados)

    @staticmethod
    def warning(acao: str, mensagem: str, entidade: str | None = None, metadados: dict | None = None) -> None:
        LogService._write('warning', acao, mensagem, entidade, metadados)

    @staticmethod
    def error(acao: str, mensagem: str, entidade: str | None = None, metadados: dict | None = None) -> None:
        LogService._write('error', acao, mensagem, entidade, metadados)