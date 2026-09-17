from flask import Blueprint
from sqlalchemy import text

from extensions import db


health_routes = Blueprint('health_routes', __name__)


@health_routes.route('/')
def home():
    return {"status": "Servidor rodando com sucesso!"}


@health_routes.route('/ready')
def ready():
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        return {'status': 'unavailable', 'database': 'unavailable'}, 503
    return {'status': 'ok', 'database': 'ok'}
