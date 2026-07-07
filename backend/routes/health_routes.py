from flask import Blueprint


health_routes = Blueprint('health_routes', __name__)


@health_routes.route('/')
def home():
    return {"status": "Servidor rodando com sucesso!"}
