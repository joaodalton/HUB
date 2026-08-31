from flask import Blueprint, request

from extensions import limiter
from services.api_credential_service import CredentialConflictError, atualizar, criar, excluir, listar, obter, testar
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


api_credential_routes = Blueprint('api_credential_routes', __name__, url_prefix='/api/v1/api-credentials')


@api_credential_routes.route('', methods=['GET'])
@require_permission('settings.read')
def index():
    return success_response(listar())


@api_credential_routes.route('', methods=['POST'])
@require_permission('settings.update')
def store():
    try:
        return success_response(criar(request.get_json(silent=True) or {}), 'Credencial salva.', 201)
    except CredentialConflictError:
        from extensions import db
        db.session.rollback()
        return error_response('Ja existe uma credencial com este provider e nome nesta empresa.', 409)
    except RuntimeError:
        from extensions import db
        db.session.rollback()
        return error_response('Servico de criptografia indisponivel. Tente novamente mais tarde.', 503)
    except ValueError:
        from extensions import db
        db.session.rollback()
        return error_response('Nao foi possivel salvar a credencial. Verifique os campos.', 400)


@api_credential_routes.route('/<int:credential_id>', methods=['GET'])
@require_permission('settings.read')
def show(credential_id: int):
    credential = obter(credential_id)
    if not credential:
        return error_response('Credencial nao encontrada.', 404)
    return success_response(credential.to_dict())


@api_credential_routes.route('/<int:credential_id>', methods=['PUT'])
@require_permission('settings.update')
def update(credential_id: int):
    try:
        credential = atualizar(credential_id, request.get_json(silent=True) or {})
    except CredentialConflictError:
        from extensions import db
        db.session.rollback()
        return error_response('Ja existe uma credencial com este provider e nome nesta empresa.', 409)
    except RuntimeError:
        from extensions import db
        db.session.rollback()
        return error_response('Servico de criptografia indisponivel. Tente novamente mais tarde.', 503)
    except ValueError:
        from extensions import db
        db.session.rollback()
        return error_response('Nao foi possivel atualizar a credencial. Verifique os campos.', 400)
    if not credential:
        return error_response('Credencial nao encontrada.', 404)
    return success_response(credential, 'Credencial atualizada.')


@api_credential_routes.route('/<int:credential_id>', methods=['DELETE'])
@require_permission('settings.update')
def destroy(credential_id: int):
    if not excluir(credential_id):
        return error_response('Credencial nao encontrada.', 404)
    return success_response(None, 'Credencial excluida.')


@api_credential_routes.route('/<int:credential_id>/testar', methods=['POST'])
@limiter.limit('10 per minute')
@require_permission('settings.update')
def test(credential_id: int):
    try:
        resultado = testar(credential_id)
    except RuntimeError:
        return error_response('Servico de criptografia indisponivel. Tente novamente mais tarde.', 503)
    except ValueError:
        return error_response('Credencial indisponivel para teste local.', 400)
    if not resultado:
        return error_response('Credencial nao encontrada.', 404)
    return success_response(resultado, 'Teste local concluido; nenhuma chamada externa foi realizada.')
