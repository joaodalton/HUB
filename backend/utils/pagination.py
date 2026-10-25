# backend/utils/pagination.py
from flask import request

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def get_pagination_params(default_page_size: int = DEFAULT_PAGE_SIZE, max_page_size: int = MAX_PAGE_SIZE) -> tuple[int, int]:
    """Le page/pageSize da querystring -- mesmo nome de parametro e mesmo
    formato de metadados ja usados em billing_calculation_routes.py
    (_invoices()): nao inventa um contrato de paginacao novo. page comeca em
    1; pageSize nunca confia no valor do cliente sem clamp."""
    page = request.args.get('page', default=1, type=int) or 1
    page_size = request.args.get('pageSize', default=default_page_size, type=int) or default_page_size
    return max(page, 1), min(max(page_size, 1), max_page_size)


def paginate(query, page: int, page_size: int) -> tuple[list, dict]:
    """Pagina uma query SQLAlchemy ja filtrada/ordenada (offset/limit).
    Retorna (itens_da_pagina, pagination) -- 'pagination' vai como chave
    irma de 'data' na resposta (ver utils/api_response.py::success_response),
    igual ao contrato existente de /billing-calculations/invoices."""
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = (total + page_size - 1) // page_size if total else 0
    return items, {'page': page, 'pageSize': page_size, 'total': total, 'pages': pages}
