from flask import Blueprint


health_routes = Blueprint('health_routes', __name__)


@health_routes.route('/')
def home():
    return {"status": "Servidor rodando com sucesso!"}


# TEMPORARIO -- so pra testar o Sentry, remover depois de confirmar que
# o erro chegou no dashboard (projeto Python/Flask).
@health_routes.route('/teste-sentry')
def teste_sentry():
    1 / 0
    return {"nunca chega aqui": True}