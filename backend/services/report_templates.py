"""Templates visuais FIXOS pro gerador de relatorio -- valem pra todas as
empresas, nunca sao salvos no banco e so mudam por deploy. Cada empresa pode
complementar esta lista com os proprios templates (tabela report_templates,
ver services/report_template_service.py); este modulo so sabe dos fixos.
Cada template so controla cor de destaque (titulo + cabecalho da tabela);
conteudo/colunas nunca mudam."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTemplate:
    id: str
    label: str
    # Hex sem '#' (RRGGBB). None = visual atual, sem nenhuma cor aplicada.
    accent_hex: str | None
    editable: bool = False


SYSTEM_TEMPLATES: dict[str, ReportTemplate] = {
    'padrao': ReportTemplate('padrao', 'Padrão (sem cor)', None),
    'azul': ReportTemplate('azul', 'Azul corporativo', '2563EB'),
    'verde': ReportTemplate('verde', 'Verde energia', '15803D'),
}
DEFAULT_TEMPLATE_ID = 'padrao'


def get_system_template(template_id: str) -> ReportTemplate | None:
    return SYSTEM_TEMPLATES.get(template_id)


def default_template() -> ReportTemplate:
    return SYSTEM_TEMPLATES[DEFAULT_TEMPLATE_ID]
