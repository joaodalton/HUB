# backend/utils/observability.py
"""Logging estruturado (JSON em stdout), request_id e handler global de erro.

Antes disto nao havia logging de aplicacao: 33 blocos `except Exception`
engoliam o traceback e o cliente recebia 500 cru ou `str(exc)`. Agora:
- cada requisicao recebe um `request_id` (ou reaproveita `X-Request-ID`),
  devolvido no header e incluido em toda linha de log;
- excecao nao tratada vira JSON `{error, code, requestId}` sem detalhe
  interno, com traceback no log e no Sentry;
- `logging.getLogger(__name__)` em qualquer modulo sai formatado em JSON.
"""
import json
import logging
import sys
import uuid
from datetime import datetime, timezone

from flask import Flask, g, has_request_context, jsonify, request
from werkzeug.exceptions import HTTPException

REQUEST_ID_HEADER = 'X-Request-ID'


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        if has_request_context():
            payload['requestId'] = getattr(g, 'request_id', None)
            payload['method'] = request.method
            payload['path'] = request.path
            empresa_id = getattr(g, 'current_empresa_id', None)
            if empresa_id is not None:
                payload['empresaId'] = empresa_id
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        for key in ('acao', 'entidade', 'extra'):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    app.logger.handlers = []
    app.logger.propagate = True
    # Bibliotecas verbosas ficam em WARNING; o resto herda o nivel da raiz.
    for noisy in ('werkzeug', 'urllib3', 'googleapiclient', 'botocore', 'boto3', 'sqlalchemy.engine'):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def register_request_id(app: Flask) -> None:
    @app.before_request
    def _assign_request_id():
        incoming = (request.headers.get(REQUEST_ID_HEADER) or '').strip()
        g.request_id = incoming[:64] if incoming else uuid.uuid4().hex

    @app.after_request
    def _echo_request_id(response):
        request_id = getattr(g, 'request_id', None)
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        return response


def register_error_handlers(app: Flask) -> None:
    logger = logging.getLogger('hub.errors')

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        # Rotas que ja devolvem JSON proprio (error_response) nao passam aqui;
        # isto cobre 404/405/413/429 gerados pelo Flask/Werkzeug/Limiter.
        payload = {'error': exc.description or exc.name, 'code': f'HTTP_{exc.code}'}
        request_id = getattr(g, 'request_id', None)
        if request_id:
            payload['requestId'] = request_id
        response = jsonify(payload)
        response.status_code = exc.code or 500
        if exc.code == 429 and getattr(exc, 'retry_after', None):
            response.headers['Retry-After'] = str(exc.retry_after)
        return response

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        logger.error('Erro nao tratado', exc_info=exc)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:  # Sentry ausente ou mal configurado nunca mascara o erro original
            pass
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
        payload = {'error': 'Erro interno. Tente novamente.', 'code': 'INTERNAL_ERROR'}
        request_id = getattr(g, 'request_id', None)
        if request_id:
            payload['requestId'] = request_id
        return jsonify(payload), 500
