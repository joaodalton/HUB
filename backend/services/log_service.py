# backend/services/log_service.py
from extensions import db
from models.log_entry import LogEntry  # ajustar import conforme nome real do arquivo do model


class LogService:
    @staticmethod
    def _write(level: str, action: str, message: str, entity: str | None = None, metadata: dict | None = None) -> None:
        entry = LogEntry(
            level=level,
            action=action,
            entity=entity,
            message=message,
            metadata=metadata
        )
        try:
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    @staticmethod
    def info(action: str, message: str, entity: str | None = None, metadata: dict | None = None) -> None:
        LogService._write('info', action, message, entity, metadata)

    @staticmethod
    def warning(action: str, message: str, entity: str | None = None, metadata: dict | None = None) -> None:
        LogService._write('warning', action, message, entity, metadata)

    @staticmethod
    def error(action: str, message: str, entity: str | None = None, metadata: dict | None = None) -> None:
        LogService._write('error', action, message, entity, metadata)