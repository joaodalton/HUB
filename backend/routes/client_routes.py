from flask import Blueprint, request

from services.client_service import (
    create_client,
    delete_client,
    get_client,
    list_clients,
    update_client
)
from services.permission_service import require_permission, require_quota
from services.fatura_concessionaria_upload_service import InvoiceUploadError, upload_invoice
from utils.api_response import error_response, success_response


client_routes = Blueprint('client_routes', __name__, url_prefix='/api/v1/clients')


@client_routes.route('/<int:client_id>/invoices/upload', methods=['POST'])
@require_permission('faturas.create')
def upload_concessionaria_invoice(client_id: int):
    files = request.files.getlist('arquivo')
    if len(files) != 1 or not files[0].filename:
        return error_response('Envie exatamente um arquivo PDF.', 400, code='INVALID_PDF')
    file_storage = files[0]

    try:
        result, duplicate = upload_invoice(client_id, file_storage)
    except InvoiceUploadError as exc:
        return error_response(str(exc), exc.status_code, code=exc.code)
    except Exception:
        return error_response(
            'Armazenamento de documentos indisponivel.', 503,
            code='DOCUMENT_STORAGE_UNAVAILABLE',
        )

    return success_response(
        result,
        'Fatura ja recebida.' if duplicate else 'Fatura recebida.',
        200 if duplicate else 201,
    )


@client_routes.route('', methods=['GET'])
@require_permission('clients.read')
def index():
    return success_response(list_clients())


@client_routes.route('/<int:client_id>', methods=['GET'])
@require_permission('clients.read')
def show(client_id: int):
    client = get_client(client_id)

    if not client:
        return error_response('Cliente nao encontrado.', 404)

    return success_response(client)


@client_routes.route('', methods=['POST'])
@require_permission('clients.create')
@require_quota('clientes')
def store():
    data = request.get_json(silent=True) or {}

    if not str(data.get('email') or '').strip():
        return error_response('Email e obrigatorio.', 400)

    try:
        client = create_client(data)
    except ValueError as exc:
        if str(exc) == 'UC nao encontrada para este cliente.':
            return error_response(str(exc), 404)
        return error_response(str(exc), 409 if 'Ja existe' in str(exc) or 'JÃ¡ existe' in str(exc) else 400)

    return success_response(client, 'Cliente cadastrado.', 201)

@client_routes.route('/<int:client_id>', methods=['PUT'])
@require_permission('clients.update')
def update(client_id: int):
    data = request.get_json(silent=True) or {}

    if not str(data.get('email') or '').strip():
        return error_response('Email e obrigatorio.', 400)

    try:
        client = update_client(client_id, data)
    except ValueError as exc:
        if str(exc) == 'UC nao encontrada para este cliente.':
            return error_response(str(exc), 404)
        return error_response(str(exc), 409 if 'Ja existe' in str(exc) or 'JÃ¡ existe' in str(exc) else 400)

    if not client:
        return error_response('Cliente nao encontrado.', 404)

    return success_response(client, 'Cliente atualizado.')


@client_routes.route('/<int:client_id>', methods=['DELETE'])
@require_permission('clients.delete')
def destroy(client_id: int):
    if not delete_client(client_id):
        return error_response('Cliente nao encontrado.', 404)

    return success_response(None, 'Cliente excluido.')
