"""CRUD dos templates proprios de cada empresa (tabela report_templates) +
combinacao com os templates fixos do sistema (report_templates.py) pra
resolver 'qual template usar' na hora de gerar um relatorio. Os fixos valem
pra todas as empresas e nunca sao gravados aqui; cada empresa só pode
criar/editar/excluir os PRÓPRIOS (filtro por empresa_id, nunca vê o de
outra)."""
import re

from extensions import db
from models.report_template import ReportTemplate as ReportTemplateModel
from services.report_templates import ReportTemplate, SYSTEM_TEMPLATES, default_template, get_system_template

_HEX_RE = re.compile(r'^[0-9A-Fa-f]{6}$')


def _validar_accent_hex(value) -> str | None:
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise ValueError('Cor deve ser um hexadecimal de 6 digitos (ex.: 2563EB).')
    return value.upper()


def _to_template(row: ReportTemplateModel) -> ReportTemplate:
    return ReportTemplate(id=f'custom:{row.id}', label=row.nome, accent_hex=row.accent_hex, editable=True)


def _custom_db_id(template_id: str) -> int | None:
    if not template_id or not template_id.startswith('custom:'):
        return None
    try:
        return int(template_id.removeprefix('custom:'))
    except ValueError:
        return None


def list_templates(empresa_id: int) -> list[dict]:
    sistema = [{'id': t.id, 'label': t.label, 'editable': False} for t in SYSTEM_TEMPLATES.values()]
    proprios = [
        row.to_dict() for row in
        ReportTemplateModel.query.filter_by(empresa_id=empresa_id).order_by(ReportTemplateModel.nome).all()
    ]
    return sistema + proprios


def get_template(template_id: str | None, empresa_id: int) -> ReportTemplate:
    if not template_id:
        return default_template()

    custom_id = _custom_db_id(template_id)
    if custom_id is not None:
        row = ReportTemplateModel.query.filter_by(id=custom_id, empresa_id=empresa_id).first()
        return _to_template(row) if row else default_template()

    return get_system_template(template_id) or default_template()


def create_template(empresa_id: int, nome: str, accent_hex: str | None) -> dict:
    nome = (nome or '').strip()
    if not nome:
        raise ValueError('Nome do template e obrigatorio.')
    row = ReportTemplateModel(empresa_id=empresa_id, nome=nome, accent_hex=_validar_accent_hex(accent_hex))
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def update_template(empresa_id: int, template_id: int, data: dict) -> dict | None:
    row = ReportTemplateModel.query.filter_by(id=template_id, empresa_id=empresa_id).first()
    if not row:
        return None
    if 'nome' in data:
        nome = (data.get('nome') or '').strip()
        if not nome:
            raise ValueError('Nome do template e obrigatorio.')
        row.nome = nome
    if 'accentHex' in data:
        row.accent_hex = _validar_accent_hex(data.get('accentHex'))
    db.session.commit()
    return row.to_dict()


def delete_template(empresa_id: int, template_id: int) -> bool:
    row = ReportTemplateModel.query.filter_by(id=template_id, empresa_id=empresa_id).first()
    if not row:
        return False
    db.session.delete(row)
    db.session.commit()
    return True
