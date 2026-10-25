import io
import unittest

from docx import Document
from openpyxl import load_workbook
from pptx import Presentation

from services.google_report_renderers import ReportTable
from services.office_report_renderers import render_as_docx, render_as_pptx, render_as_xlsx


def _table():
    return ReportTable(title='Cadastro', headers=['Nome', 'Codigo'], rows=[['Cliente A', 'UC-1'], ['Cliente B', 'UC-2']])


class OfficeReportRenderersTest(unittest.TestCase):
    def test_render_as_docx_produces_bytes_with_title_and_table(self):
        data = render_as_docx(_table())
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)

        document = Document(io.BytesIO(data))
        texts = '\n'.join(p.text for p in document.paragraphs)
        self.assertIn('Cadastro', texts)
        table = document.tables[0]
        self.assertEqual([cell.text for cell in table.rows[0].cells], ['Nome', 'Codigo'])
        self.assertEqual([cell.text for cell in table.rows[1].cells], ['Cliente A', 'UC-1'])

    def test_render_as_xlsx_produces_bytes_with_headers_and_rows(self):
        data = render_as_xlsx(_table())
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)

        workbook = load_workbook(io.BytesIO(data))
        worksheet = workbook.active
        self.assertEqual([cell.value for cell in worksheet[1]], ['Nome', 'Codigo'])
        self.assertEqual([cell.value for cell in worksheet[2]], ['Cliente A', 'UC-1'])

    def test_render_as_pptx_produces_bytes_with_title_and_table(self):
        data = render_as_pptx(_table())
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)

        presentation = Presentation(io.BytesIO(data))
        slide = presentation.slides[0]
        self.assertEqual(slide.shapes.title.text, 'Cadastro')
        table_shape = next(shape for shape in slide.shapes if shape.has_table)
        table = table_shape.table
        self.assertEqual(table.cell(0, 0).text, 'Nome')
        self.assertEqual(table.cell(1, 0).text, 'Cliente A')

    def test_empty_rows_do_not_raise(self):
        table = ReportTable(title='Vazio', headers=['Nome'], rows=[])
        self.assertTrue(render_as_docx(table))
        self.assertTrue(render_as_xlsx(table))
        self.assertTrue(render_as_pptx(table))


if __name__ == '__main__':
    unittest.main()
