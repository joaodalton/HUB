# backend/routes/rateio_routes.py
from flask import Blueprint, Response, request

from services.rateio_service import aplicar_rateio, atualizar_distribuicao, confirmar_selecao, funil_qualificacao, list_historico, preview_rateio
from services.rateio_formulario_service import montar_tabela_formulario, verificar_termos_adesao
from services.rateio_pdf_service import gerar_formulario_pdf, gerar_termos_adesao_pdf
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


rateio_routes = Blueprint('rateio_routes', __name__, url_prefix='/api/v1/rateio')


@rateio_routes.route('/preview', methods=['GET'])
@require_permission('rateios.read')
def preview():
    plant_id = request.args.get('plantId', type=int)
    return success_response(preview_rateio(plant_id))


@rateio_routes.route('/aplicar', methods=['POST'])
@require_permission('rateios.calculate')
def aplicar():
    data = request.get_json(silent=True) or {}
    competencia = data.get('competencia', '')
    plant_id = data.get('plantId')

    if not competencia:
        return error_response('Competencia e obrigatoria (formato YYYY-MM).', 400)

    try:
        resultado = aplicar_rateio(competencia, plant_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(resultado, 'Rateio aplicado.')


@rateio_routes.route('/confirmar', methods=['POST'])
@require_permission('rateios.update')
def confirmar():
    data = request.get_json(silent=True) or {}
    plant_id = data.get('plantId')
    competencia = data.get('competencia', '')
    selecoes = data.get('selecoes', [])

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)
    if not competencia:
        return error_response('Competencia e obrigatoria (formato YYYY-MM).', 400)

    try:
        resultado = confirmar_selecao(plant_id, competencia, selecoes)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(resultado, 'Rateio confirmado. Clientes conectados a usina.', 201)

@rateio_routes.route('/distribuicao', methods=['PUT'])
@require_permission('rateios.update')
def distribuicao():
    data = request.get_json(silent=True) or {}
    plant_id = data.get('plantId')
    atualizacoes = data.get('atualizacoes', [])

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)

    try:
        resultado = atualizar_distribuicao(plant_id, atualizacoes)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(resultado, 'Distribuicao atualizada.')

@rateio_routes.route('/qualificacao', methods=['GET'])
@require_permission('rateios.read')
def qualificacao():
    plant_id = request.args.get('plantId', type=int)

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)

    try:
        return success_response(funil_qualificacao(plant_id))
    except ValueError as exc:
        return error_response(str(exc), 404)


@rateio_routes.route('/historico', methods=['GET'])
@require_permission('rateios.read')
def historico():
    competencia = request.args.get('competencia')
    plant_id = request.args.get('plantId', type=int)
    uc_id = request.args.get('ucId', type=int)

    return success_response(list_historico(competencia, plant_id, uc_id))


# GET /api/v1/rateio/formulario?plantId=... -- tabela de revisao pro formulario Copel
# (linha da geradora + PlantConnection ja confirmadas). Nao recalcula nada,
# so le o que ja esta gravado no banco.
@rateio_routes.route('/formulario', methods=['GET'])
@require_permission('rateios.read')
def formulario_tabela():
    plant_id = request.args.get('plantId', type=int)

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)

    try:
        return success_response(montar_tabela_formulario(plant_id))
    except ValueError as exc:
        return error_response(str(exc), 404)


# POST /api/v1/rateio/formulario/verificar-documentos -- Body: {plantId}.
# Confere Termo de Adesao de cada UC beneficiaria; se faltar algum, cria
# Pendencia (categoria Documentos, prioridade critica) e retorna ok=false.
@rateio_routes.route('/formulario/verificar-documentos', methods=['POST'])
@require_permission('rateios.update')
def formulario_verificar_documentos():
    data = request.get_json(silent=True) or {}
    plant_id = data.get('plantId')

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)

    try:
        resultado = verificar_termos_adesao(plant_id, registrar_pendencia=True)
    except ValueError as exc:
        return error_response(str(exc), 404)

    return success_response(resultado)


# POST /api/v1/rateio/formulario/gerar-pdf -- Body: {plantId, responsavelNome, responsavelCpf}.
# Retorna o PDF (binario) do Formulario Copel ja preenchido. Bloqueia (400) se
# faltar Termo de Adesao ou passar de 24 UCs beneficiarias.
@rateio_routes.route('/formulario/gerar-pdf', methods=['POST'])
@require_permission('rateios.read')
def formulario_gerar_pdf():
    data = request.get_json(silent=True) or {}
    plant_id = data.get('plantId')
    responsavel_nome = (data.get('responsavelNome') or '').strip()
    responsavel_cpf = (data.get('responsavelCpf') or '').strip()

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)
    if not responsavel_nome or not responsavel_cpf:
        return error_response('Nome e CPF do responsavel sao obrigatorios.', 400)

    try:
        pdf_bytes = gerar_formulario_pdf(
            plant_id,
            responsavel_nome,
            responsavel_cpf,
            linhas_override=data.get('linhas')
        )
    except ValueError as exc:
        return error_response(str(exc), 400)

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=formulario-copel-rateio.pdf'}
    )


# POST /api/v1/rateio/formulario/gerar-termos -- Body: {plantId}. Retorna o PDF
# (binario) com os Termos de Adesao de todas as UCs beneficiarias mesclados,
# na mesma ordem alfabetica da tabela. Bloqueia (400) se faltar algum.
@rateio_routes.route('/formulario/gerar-termos', methods=['POST'])
@require_permission('rateios.read')
def formulario_gerar_termos():
    data = request.get_json(silent=True) or {}
    plant_id = data.get('plantId')

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)

    try:
        pdf_bytes = gerar_termos_adesao_pdf(plant_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=termos-adesao.pdf'}
    )
