# backend/routes/pendencia_routes.py
from flask import Blueprint, g, request

from extensions import limiter
from services.automacao_service import resolver_pendencias_resolvidas, verificar_e_criar_pendencias
from services.pendencia_service import (
    adicionar_comentario,
    cancelar_pendencia,
    criar_pendencia_manual,
    delete_pendencia,
    get_pendencia,
    get_resumo,
    list_pendencias,
    reabrir_pendencia,
    resolver_pendencia,
    update_pendencia
)
from utils.api_response import error_response, success_response


pendencia_routes = Blueprint('pendencia_routes', __name__, url_prefix='/api/v1/pendencias')

@pendencia_routes.route('', methods=['GET'])
def index():
    filtros = {
        'tipo': request.args.get('tipo'),
        'categoria': request.args.get('categoria'),
        'origem': request.args.get('origem'),
        'status': request.args.get('status'),
        'prioridade': request.args.get('prioridade'),
        'responsavelId': request.args.get('responsavelId', type=int),
        'clienteId': request.args.get('clienteId', type=int)
    }
    return success_response(list_pendencias(filtros))


@pendencia_routes.route('/resumo', methods=['GET'])
def resumo():
    return success_response(get_resumo())


@pendencia_routes.route('/<int:pendencia_id>', methods=['GET'])
def show(pendencia_id: int):
    pendencia = get_pendencia(pendencia_id)
    if not pendencia:
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(pendencia)


@pendencia_routes.route('', methods=['POST'])
@limiter.limit('30 per minute')
def store():
    data = request.get_json(silent=True) or {}

    if not data.get('titulo', '').strip():
        return error_response('Titulo e obrigatorio.', 400)
    if not data.get('categoria'):
        return error_response('Categoria e obrigatoria.', 400)

    data.setdefault('responsavelId', g.current_user.id)

    try:
        pendencia = criar_pendencia_manual(data)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(pendencia, 'Pendencia criada.', 201)


@pendencia_routes.route('/<int:pendencia_id>', methods=['PUT'])
@limiter.limit('30 per minute')
def update(pendencia_id: int):
    data = request.get_json(silent=True) or {}
    try:
        pendencia = update_pendencia(pendencia_id, data)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not pendencia:
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(pendencia, 'Pendencia atualizada.')


@pendencia_routes.route('/<int:pendencia_id>', methods=['DELETE'])
@limiter.limit('30 per minute')
def destroy(pendencia_id: int):
    if not delete_pendencia(pendencia_id):
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(None, 'Pendencia excluida.')


@pendencia_routes.route('/<int:pendencia_id>/resolver', methods=['POST'])
@limiter.limit('30 per minute')
def resolver(pendencia_id: int):
    pendencia = resolver_pendencia(pendencia_id)
    if not pendencia:
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(pendencia, 'Pendencia resolvida.')


@pendencia_routes.route('/<int:pendencia_id>/cancelar', methods=['POST'])
@limiter.limit('30 per minute')
def cancelar(pendencia_id: int):
    pendencia = cancelar_pendencia(pendencia_id)
    if not pendencia:
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(pendencia, 'Pendencia cancelada.')


@pendencia_routes.route('/<int:pendencia_id>/reabrir', methods=['POST'])
@limiter.limit('30 per minute')
def reabrir(pendencia_id: int):
    pendencia = reabrir_pendencia(pendencia_id)
    if not pendencia:
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(pendencia, 'Pendencia reaberta.')


@pendencia_routes.route('/<int:pendencia_id>/comentarios', methods=['POST'])
@limiter.limit('30 per minute')
def comentar(pendencia_id: int):
    data = request.get_json(silent=True) or {}
    texto = data.get('texto', '').strip()
    if not texto:
        return error_response('Texto do comentario e obrigatorio.', 400)
    pendencia = adicionar_comentario(pendencia_id, texto, g.current_user.id)
    if not pendencia:
        return error_response('Pendencia nao encontrada.', 404)
    return success_response(pendencia, 'Comentario adicionado.', 201)


# ========== Rotas de automacao ==========

@pendencia_routes.route('/verificar', methods=['POST'])
@limiter.limit('5 per minute')
def verificar():
    """
    Executa todas as verificacoes automaticas de pendencias.
    Chamado pela tela de Pendencias (sincronizacao automatica ao abrir)
    e pelo botao 'Verificar agora'.
    """
    try:
        # Primeiro resolve as pendencias que ja nao se aplicam
        resolvidas = resolver_pendencias_resolvidas()

        # Depois cria as novas pendencias/alertas necessarios
        resultado = verificar_e_criar_pendencias()

        return success_response({
            'verificacoes': resultado,
            'resolvidas': resolvidas,
            'total_criadas': sum(resultado.values()),
        }, 'Verificacao automatica concluida.')
    except Exception as exc:
        return error_response(f'Erro na verificacao automatica: {str(exc)}', 500)


@pendencia_routes.route('/regras', methods=['GET'])
def listar_regras():
    """
    Retorna a lista de regras automaticas disponiveis para exibicao
    na interface (Sprint 2: tela de automacao futura).
    """
    regras = [
        {
            'id': 'uc_sem_usina',
            'nome': 'UC sem usina vinculada',
            'descricao': 'Cria alerta quando uma UC fica mais de 7 dias sem conexão com usina',
            'categoria': 'Operacional',
            'ativa': True,
        },
        {
            'id': 'cliente_sem_uc',
            'nome': 'Cliente sem UC',
            'descricao': 'Cria pendencia quando cliente novo nao tem UC vinculada',
            'categoria': 'Cadastro',
            'ativa': True,
        },
        {
            'id': 'campos_faltando',
            'nome': 'Campos obrigatorios faltando',
            'descricao': 'Cria pendencia quando campos obrigatorios do cliente estao vazios',
            'categoria': 'Cadastro',
            'ativa': True,
        },
        {
            'id': 'documentos_faltando',
            'nome': 'Documentos obrigatorios faltando',
            'descricao': 'Cria pendencia quando documentos obrigatorios nao foram enviados',
            'categoria': 'Documentos',
            'ativa': True,
        },
    ]
    return success_response(regras)
