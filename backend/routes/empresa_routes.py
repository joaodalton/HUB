# backend/routes/empresa_routes.py
"""
Rotas de empresas para admin da plataforma:
  POST   /api/v1/empresas              cria empresa (só platform admin)
  GET    /api/v1/empresas              listagem (só platform admin)
  GET    /api/v1/empresas/<int:id>    detalhe completo com dados relacionados
  PUT    /api/v1/empresas/<int:id>    atualiza dados da empresa (só platform admin)
  POST   /api/v1/empresas/<int:id>/entrar  entra no contexto da empresa (só platform admin)
  POST   /api/v1/empresas/sair-plataforma  sai do contexto de impersonação
  DELETE /api/v1/empresas/<int:id>    excluir com confirmação de frase
"""
from flask import Blueprint, g, request, jsonify

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura import Fatura
from models.invitation import Invitation
from models.pendencia import Pendencia
from models.plant import Plant
from models.rateio_historico import RateioHistorico
from models.user import User
from services.empresa_service import criar_empresa_com_owner, update_empresa
from services.permission_service import require_platform_admin
from utils.api_response import error_response, success_response
from utils.auth import hash_password, set_platform_view_cookie, clear_platform_view_cookie

empresa_routes = Blueprint("empresa_routes", __name__, url_prefix="/api/v1/empresas")


# ---------- helpers de contagens ----------

def _count(model, empresa_id):
    if model is None or not hasattr(model, "query"):
        return 0
    try:
        return model.query.filter_by(empresa_id=empresa_id).count()
    except Exception:
        return 0


# ---------- POST /empresas (criar) ----------

@empresa_routes.route("", methods=["POST"])
@require_platform_admin()
def criar():
    body = request.get_json(silent=True) or {}
    empresa_data = body.get("empresa", {})
    owner_data = body.get("owner", {})

    nome = (empresa_data.get("nome") or "").strip()
    cnpj = (empresa_data.get("cnpj") or "").strip() or None
    razao_social = (empresa_data.get("razao_social") or "").strip() or None
    email = (empresa_data.get("email") or "").strip() or None
    telefone = (empresa_data.get("telefone") or "").strip() or None

    owner_nome = (owner_data.get("nome") or "").strip()
    owner_email = (owner_data.get("email") or "").strip().lower()
    owner_senha = owner_data.get("senha") or ""

    if not nome:
        return error_response("Nome da empresa é obrigatório.", 400)
    if not owner_nome or not owner_email or not owner_senha:
        return error_response("Dados do owner (nome, email, senha) são obrigatórios.", 400)
    if len(owner_senha) < 6:
        return error_response("Senha precisa ter pelo menos 6 caracteres.", 400)

    try:
        result = criar_empresa_com_owner(
            {
                "empresa": {
                    "nome": nome,
                    "razao_social": razao_social,
                    "cnpj": cnpj,
                    "email": email,
                    "telefone": telefone,
                },
                "owner": {
                    "nome": owner_nome,
                    "email": owner_email,
                    "senha": owner_senha,
                },
            }
        )
    except ValueError as exc:
        return error_response(str(exc), 409)

    return success_response(
        {
            "empresa": result["empresa"],
            "owner": result["owner"],
        },
        "Empresa criada com owner.",
        201,
    )


# ---------- GET /empresas (listagem para platform admin) ----------

@empresa_routes.route("", methods=["GET"])
@require_platform_admin()
def listar():
    empresas = Empresa.query.order_by(Empresa.nome).all()
    resultado = []
    for e in empresas:
        d = e.to_dict()
        d["totalUsuarios"] = _count(User, e.id)
        d["totalClientes"] = _count(Client, e.id)
        # Email do primeiro owner (proprietário)
        owner = User.query.filter_by(empresa_id=e.id, role='owner').first()
        d["ownerEmail"] = owner.email if owner else None
        resultado.append(d)

    return success_response(resultado, "Listagem de empresas.")

@empresa_routes.route("/<int:empresa_id>", methods=["GET"])
@require_platform_admin()
def detalhe(empresa_id: int):
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return error_response("Empresa não encontrada.", 404)

    res = empresa.to_dict()
    res["totalUsuarios"] = _count(User, empresa_id)
    res["totalClientes"] = _count(Client, empresa_id)
    res["totalUcs"] = _count(ConsumerUnit, empresa_id)
    res["totalUsinas"] = _count(Plant, empresa_id)
    res["totalPendencias"] = _count(Pendencia, empresa_id)
    res["totalFaturas"] = _count(Fatura, empresa_id)
    res["totalRateios"] = _count(RateioHistorico, empresa_id)
    res["totalDocumentos"] = _count(Document, empresa_id)
    res["totalConvites"] = _count(Invitation, empresa_id)

    return success_response(res, "Detalhe da empresa.")


# ---------- frases de exclusão ----------

def _frase_atual(empresa_id: int) -> str:
    """Retorna a frase atual (não persiste, serve para mostrar pro admin)."""
    return "Confirme com: CONFIRMAR"


def _validar_confirmacao(empresa_id: int, texto: str) -> bool:
    """
    Valida a confirmação de exclusão de empresa.

    Regras:
      - A frase que o admin deve digitar é sempre a mesma (CONFIRMAR),
        mas exibimos uma frase diferente a cada tentativa para obrigar
        atenção - ver lista_exclusao.py.
      - Aceita qualquer uma das frases da lista, em maiúsculas, no campo.
    """
    from utils.lista_exclusao import PHRASES

    txt = (texto or "").strip()
    if not txt:
        return False
    return txt.upper() == "CONFIRMAR" or txt.upper() in (p.upper() for p in PHRASES)


# ---------- PUT /empresas/<id> (atualizar) ----------

@empresa_routes.route("/<int:empresa_id>", methods=["PUT"])
@require_platform_admin()
def atualizar(empresa_id: int):
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return error_response("Empresa não encontrada.", 404)

    body = request.get_json(silent=True) or {}
    try:
        updated = update_empresa(empresa_id, body)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(updated.to_dict(), f"Empresa '{updated.nome}' atualizada.")


# ---------- POST /empresas/<id>/entrar (impersonação) ----------

@empresa_routes.route("/<int:empresa_id>/entrar", methods=["POST"])
@require_platform_admin()
def entrar(empresa_id: int):
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return error_response("Empresa não encontrada.", 404)

    response = jsonify({
        'success': True,
        'message': f'Visualizando como {empresa.nome}.',
        'data': {
            'empresaId': empresa.id,
            'empresaNome': empresa.nome
        }
    })
    set_platform_view_cookie(response, empresa_id)
    return response


# ---------- POST /empresas/sair-plataforma (sair da impersonação) ----------

@empresa_routes.route("/sair-plataforma", methods=["POST"])
@require_platform_admin()
def sair_plataforma():
    response = jsonify({
        'success': True,
        'message': 'Saiu do contexto de plataforma. Voltou ao seu contexto habitual.',
        'data': None
    })
    clear_platform_view_cookie(response)
    return response

@empresa_routes.route("/<int:empresa_id>", methods=["DELETE"])
@require_platform_admin()
def excluir(empresa_id: int):
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return error_response("Empresa não encontrada.", 404)

    body = request.get_json(silent=True) or {}
    confirmacao = (body.get("confirmacao") or "").strip()

    if not _validar_confirmacao(empresa_id, confirmacao):
        return success_response(
            {
                "empresaId": empresa_id,
                "empresaNome": empresa.nome,
                "frase": _frase_atual(empresa_id),
            },
            "Confirmacao invalida. Digite a frase exibida.",
            403,
        )

    # Deleta todos os usuários da empresa antes de deletar a empresa.
    # O owner também é deletado -- nao ha restricao de negocio que impeça
    # a exclusao de uma empresa inteira junto com seu owner (a restricao
    # "nao excluir owner" vale apenas para DELETE de user individual).
    users = User.query.filter_by(empresa_id=empresa_id).all()
    for u in users:
        db.session.delete(u)

    db.session.commit()

    # remove a empresa
    db.session.delete(empresa)
    db.session.commit()

    return success_response(
        {"empresaId": empresa_id, "empresaNome": empresa.nome},
        f"Empresa '{empresa.nome}' excluída.",
    )
