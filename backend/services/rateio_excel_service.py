"""Gera o formulário Copel em XLSX a partir do modelo CSV oficial fornecido."""
import csv
import io
import re
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side

from services.rateio_formulario_service import montar_tabela_formulario
from services.rateio_pdf_service import aplicar_linhas_override, validar_tabela_formulario, validar_termos_adesao_obrigatorios

ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
CSV_TEMPLATE_GLOB = '*ASSOCIAÇÃO - PERCENTUAL).csv'
LINHA_INICIAL_BENEFICIARIAS = 17
LINHA_TOTAL = 41
BENEFICIARIAS_MODELO = 24


def _template_path() -> Path:
    templates = list(ASSETS_DIR.glob(CSV_TEMPLATE_GLOB))
    if not templates:
        raise ValueError('Modelo CSV do formulário Copel não encontrado em backend/assets.')
    return templates[0]


def _carregar_modelo() -> Workbook:
    with _template_path().open(encoding='cp1252', newline='') as arquivo:
        linhas = list(csv.reader(arquivo, delimiter=';'))

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Formulário Copel'
    worksheet.sheet_view.showGridLines = False
    worksheet.freeze_panes = 'A17'

    for linha_idx, linha in enumerate(linhas, start=1):
        for coluna_idx, valor in enumerate(linha, start=1):
            celula = worksheet.cell(linha_idx, coluna_idx, None if valor == '\xa0' else valor)
            celula.alignment = Alignment(vertical='center', wrap_text=True)

    for coluna, largura in {'A': 8, 'B': 42, 'C': 25, 'D': 28, 'E': 18, 'F': 4, 'G': 8}.items():
        worksheet.column_dimensions[coluna].width = largura
    for linha in range(17, 41):
        worksheet.row_dimensions[linha].height = 20

    borda = Border(*(Side(style='thin') for _ in range(4)))
    for linha in range(16, 41):
        for coluna in range(1, 6):
            worksheet.cell(linha, coluna).border = borda
    return workbook


def _preencher_texto(celula, texto: str) -> None:
    celula.value = texto
    celula.font = Font(bold=False)


def gerar_formulario_excel(
    plant_id: int, responsavel_nome: str, responsavel_cpf: str, linhas_override: list[dict] | None = None
) -> bytes:
    if not responsavel_nome.strip() or not responsavel_cpf.strip():
        raise ValueError('Nome e CPF do responsavel sao obrigatorios.')

    tabela = montar_tabela_formulario(plant_id)
    aplicar_linhas_override(tabela, linhas_override)
    validar_tabela_formulario(tabela)

    validar_termos_adesao_obrigatorios(tabela, plant_id)

    workbook = _carregar_modelo()
    worksheet = workbook.active
    linhas_extras = max(0, len(tabela['linhas']) - BENEFICIARIAS_MODELO)
    if linhas_extras:
        worksheet.insert_rows(LINHA_TOTAL, linhas_extras)
        borda = Border(*(Side(style='thin') for _ in range(4)))
        for linha_excel in range(LINHA_TOTAL, LINHA_TOTAL + linhas_extras):
            worksheet.row_dimensions[linha_excel].height = 20
            for coluna in range(1, 6):
                worksheet.cell(linha_excel, coluna).border = borda
    worksheet['A4'] = re.sub(r'n[ºo]\s*_+', f'nº {tabela["ucGeradora"]}', str(worksheet['A4'].value), count=1)
    worksheet['A8'] = re.sub(r'n[ºo]\s*_+', f'nº {tabela["ucAncora"]}', str(worksheet['A8'].value), count=1)

    for linha in tabela['linhas']:
        linha_excel = LINHA_INICIAL_BENEFICIARIAS + linha['ordem'] - 1
        worksheet.cell(linha_excel, 1, linha['ordem'])
        _preencher_texto(worksheet.cell(linha_excel, 2), linha['nome'] or '')
        _preencher_texto(worksheet.cell(linha_excel, 3), linha['documento'] or '')
        _preencher_texto(worksheet.cell(linha_excel, 4), linha['ucIdentificacao'] or '')
        percentual = round(float(linha['percentual']) / 100, 4)
        worksheet.cell(linha_excel, 5, percentual).number_format = '0.00%'

    total = round(sum(float(linha['percentual']) for linha in tabela['linhas']) / 100, 4)
    linha_total = LINHA_TOTAL + linhas_extras
    worksheet.cell(linha_total, 5, total).number_format = '0.00%'
    _preencher_texto(worksheet[f'C{71 + linhas_extras}'], tabela['empresaNome'] or '')
    _preencher_texto(worksheet[f'C{72 + linhas_extras}'], tabela['empresaEmail'] or '')
    _preencher_texto(worksheet[f'C{73 + linhas_extras}'], tabela['empresaCnpj'] or '')
    _preencher_texto(worksheet[f'C{75 + linhas_extras}'], responsavel_nome.strip())
    _preencher_texto(worksheet[f'C{76 + linhas_extras}'], responsavel_cpf.strip())
    worksheet[f'A{81 + linhas_extras}'] = f'Data: {date.today():%d/%m/%Y}'

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
