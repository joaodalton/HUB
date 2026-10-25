"""Renderizadores locais: recebem a mesma ReportTable usada pelos formatos
Google e geram o arquivo office (docx/xlsx/pptx) em memoria, sem nenhuma
chamada de rede/Drive/credencial -- funciona mesmo sem conta Google."""
import io

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font
from pptx import Presentation
from pptx.util import Inches

from services.google_report_renderers import ReportTable


def render_as_docx(table: ReportTable) -> bytes:
    document = Document()
    document.add_heading(table.title, level=1)
    cols = max(len(table.headers), 1)
    doc_table = document.add_table(rows=1, cols=cols)
    doc_table.style = 'Table Grid'
    for col_index, header in enumerate(table.headers):
        doc_table.rows[0].cells[col_index].text = header
    for row in table.rows:
        cells = doc_table.add_row().cells
        for col_index, value in enumerate(row):
            cells[col_index].text = str(value) if value is not None else ''
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def render_as_xlsx(table: ReportTable) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = table.title[:31] or 'Relatorio'
    worksheet.append(table.headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
    for row in table.rows:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_as_pptx(table: ReportTable) -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = table.title
    rows = len(table.rows) + 1
    cols = max(len(table.headers), 1)
    shape = slide.shapes.add_table(rows, cols, Inches(0.5), Inches(1.5), Inches(9), Inches(0.8 * rows))
    pptx_table = shape.table
    for col_index, header in enumerate(table.headers):
        pptx_table.cell(0, col_index).text = header or ''
    for row_index, row in enumerate(table.rows, start=1):
        for col_index, value in enumerate(row):
            pptx_table.cell(row_index, col_index).text = str(value) if value is not None else ''
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()
