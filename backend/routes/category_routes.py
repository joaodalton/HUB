# backend/routes/category_routes.py
from flask import Blueprint, request

from extensions import db
from models.category import Category
from utils.api_response import error_response, success_response


category_routes = Blueprint('category_routes', __name__, url_prefix='/categories')


@category_routes.route('', methods=['GET'])
def index():
    categories = Category.query.order_by(Category.nome).all()
    return success_response([category.to_dict() for category in categories])


@category_routes.route('', methods=['POST'])
def store():
    data = request.get_json(silent=True) or {}
    nome = data.get('nome', '').strip()

    if not nome:
        return error_response('Nome e obrigatorio.', 400)

    existing = Category.query.filter(db.func.lower(Category.nome) == nome.lower()).first()
    if existing:
        return error_response('Ja existe uma categoria com esse nome.', 409)

    category = Category(nome=nome, tipo=data.get('tipo'), descricao=data.get('descricao'))
    db.session.add(category)
    db.session.commit()

    return success_response(category.to_dict(), 'Categoria criada.', 201)