# backend/routes/document_routes.py
from flask import Blueprint, redirect, request, send_file

from services.document_service import (
    create_document,
    create_drive_document,
    delete_document,
    get_document,
    list_documents,
    rename_document,
    resolve_file_path
)
from utils.api_response import error_response, success_response


document_routes = Blueprint('document_routes', __name__, url_prefix='/api/v1/documents')


# GET /api/v1/documents?clienteId=1&ucId=2 -- lista documentos, filtro opcional por cliente/UC
@document_routes.route('', methods=['GET'])
def index():
    client_id = request.args.get('clienteId', type=int)
    uc_id = request.args.get('ucId', type=int)
    return success_response(list_documents(client_id, uc_id))


@document_routes.route('/<int:document_id>', methods=['GET'])
def show(document_id: int):
    document = get_document(document_id)

    if not document:
        return error_response('Documento nao encontrado.', 404)

    return success_response(document.to_dict())


# POST /api/v1/documents -- multipart/form-data. Campos: arquivo (file), nome, clienteId, ucId, categoriaId
@document_routes.route('', methods=['POST'])
def store():
    if 'arquivo' not in request.files or not request.files['arquivo'].filename:
        return error_response('Nenhum arquivo enviado.', 400)

    data = {
        'nome': request.form.get('nome', ''),
        'clienteId': request.form.get('clienteId', type=int),
        'ucId': request.form.get('ucId', type=int),
        'categoriaId': request.form.get('categoriaId', type=int)
    }

    try:
        document = create_document(data, request.files['arquivo'])
    except ValueError as exc:
        return error_response(str(exc), 409)

    return success_response(document, 'Documento enviado.', 201)


# POST /api/v1/documents/drive-link -- Body JSON: {nome, driveFileId, categoriaId, clienteId?, ucId?, mimeType?}
# Vincula um arquivo que ja esta no Google Drive a um cliente/UC sem copiar/mover
# o arquivo -- so cria o registro em Document apontando pro fileId do Drive.
@document_routes.route('/drive-link', methods=['POST'])
def link_from_drive():
    data = request.get_json(silent=True) or {}

    if not data.get('categoriaId'):
        return error_response('Categoria e obrigatoria.', 400)
    if not (data.get('driveFileId') or '').strip():
        return error_response('Arquivo do Google Drive e obrigatorio.', 400)

    try:
        document = create_drive_document(data)
    except ValueError as exc:
        return error_response(str(exc), 409)

    return success_response(document, 'Documento vinculado.', 201)


# PUT /api/v1/documents/<id> -- Body: {nome}. So renomeia, nao troca o arquivo.


# PUT /api/v1/documents/<id> -- Body: {nome}. So renomeia, nao troca o arquivo.
@document_routes.route('/<int:document_id>', methods=['PUT'])
def rename(document_id: int):
    data = request.get_json(silent=True) or {}
    novo_nome = data.get('nome', '').strip()

    if not novo_nome:
        return error_response('Nome e obrigatorio.', 400)

    document = rename_document(document_id, novo_nome)

    if not document:
        return error_response('Documento nao encontrado.', 404)

    return success_response(document, 'Documento renomeado.')


@document_routes.route('/<int:document_id>', methods=['DELETE'])
def destroy(document_id: int):
    if not delete_document(document_id):
        return error_response('Documento nao encontrado.', 404)

    return success_response(None, 'Documento excluido.')


@document_routes.route('/<int:document_id>/download', methods=['GET'])
def download(document_id: int):
    document = get_document(document_id)

    if not document:
        return error_response('Documento nao encontrado.', 404)

    if document.storage_provider == 'google_drive':
        # Nao ha arquivo local pra esse Document -- o Drive continua sendo o
        # armazenamento (ver create_drive_document). Manda pra pagina de
        # visualizacao nativa do Drive em vez de tentar servir um binario.
        return redirect(f'https://drive.google.com/file/d/{document.storage_ref}/view')

    file_path = resolve_file_path(document)

    if not file_path:
        return error_response('Arquivo nao encontrado no disco.', 404)

    return send_file(file_path, as_attachment=True, download_name=document.nome)