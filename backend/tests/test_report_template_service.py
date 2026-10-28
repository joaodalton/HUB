"""Templates proprios de relatorio por empresa: CRUD + isolamento de tenant
(cada empresa so ve/edita/exclui os PROPRIOS; os fixos do sistema aparecem
pra todo mundo e nunca sao tocados aqui)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.report_template import ReportTemplate  # noqa: E402
from services import report_template_service as svc  # noqa: E402
from services.report_templates import SYSTEM_TEMPLATES, default_template  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class ReportTemplateServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'report-template-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([Empresa(nome='A', slug='rt-a'), Empresa(nome='B', slug='rt-b')])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.session.query(ReportTemplate).delete()
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def test_list_combina_fixos_do_sistema_com_proprios_da_empresa(self):
        svc.create_template(1, 'Marca A', '112233')
        resultado = svc.list_templates(1)
        ids = {item['id'] for item in resultado}
        self.assertEqual(ids, {*SYSTEM_TEMPLATES.keys(), *[i['id'] for i in resultado if i['editable']]})
        proprio = next(item for item in resultado if item['editable'])
        self.assertEqual(proprio['label'], 'Marca A')
        self.assertEqual(proprio['accentHex'], '112233')

    def test_empresa_nao_ve_template_de_outra_empresa(self):
        svc.create_template(1, 'Da empresa 1', 'AABBCC')
        resultado_b = svc.list_templates(2)
        self.assertFalse(any(item['editable'] for item in resultado_b))

    def test_create_valida_nome_obrigatorio(self):
        with self.assertRaises(ValueError):
            svc.create_template(1, '', '112233')

    def test_create_valida_formato_hex(self):
        with self.assertRaises(ValueError):
            svc.create_template(1, 'Invalido', 'zzzzzz')
        with self.assertRaises(ValueError):
            svc.create_template(1, 'Invalido', '12345')  # 5 digitos, nao 6

    def test_create_aceita_sem_cor(self):
        criado = svc.create_template(1, 'Sem cor', None)
        self.assertIsNone(criado['accentHex'])

    def test_update_nao_alcanca_template_de_outra_empresa(self):
        criado = svc.create_template(1, 'Original', '112233')
        template_id = int(criado['id'].removeprefix('custom:'))
        resultado = svc.update_template(2, template_id, {'nome': 'Hackeado'})
        self.assertIsNone(resultado)
        linha = ReportTemplate.query.filter_by(id=template_id).first()
        self.assertEqual(linha.nome, 'Original')

    def test_update_altera_nome_e_cor_do_proprio(self):
        criado = svc.create_template(1, 'Original', '112233')
        template_id = int(criado['id'].removeprefix('custom:'))
        atualizado = svc.update_template(1, template_id, {'nome': 'Novo nome', 'accentHex': '445566'})
        self.assertEqual(atualizado['label'], 'Novo nome')
        self.assertEqual(atualizado['accentHex'], '445566')

    def test_delete_nao_alcanca_template_de_outra_empresa(self):
        criado = svc.create_template(1, 'Original', '112233')
        template_id = int(criado['id'].removeprefix('custom:'))
        self.assertFalse(svc.delete_template(2, template_id))
        self.assertIsNotNone(ReportTemplate.query.filter_by(id=template_id).first())

    def test_delete_remove_o_proprio(self):
        criado = svc.create_template(1, 'Original', '112233')
        template_id = int(criado['id'].removeprefix('custom:'))
        self.assertTrue(svc.delete_template(1, template_id))
        self.assertIsNone(ReportTemplate.query.filter_by(id=template_id).first())

    def test_get_template_resolve_custom_da_propria_empresa(self):
        criado = svc.create_template(1, 'Minha marca', '778899')
        resolvido = svc.get_template(criado['id'], 1)
        self.assertEqual(resolvido.label, 'Minha marca')
        self.assertEqual(resolvido.accent_hex, '778899')

    def test_get_template_nao_resolve_custom_de_outra_empresa_cai_no_padrao(self):
        criado = svc.create_template(1, 'Da empresa 1', '778899')
        resolvido = svc.get_template(criado['id'], 2)
        self.assertEqual(resolvido, default_template())

    def test_get_template_resolve_fixo_do_sistema(self):
        resolvido = svc.get_template('azul', 1)
        self.assertEqual(resolvido, SYSTEM_TEMPLATES['azul'])

    def test_get_template_sem_id_cai_no_padrao(self):
        self.assertEqual(svc.get_template(None, 1), default_template())

    def test_get_template_id_invalido_cai_no_padrao(self):
        self.assertEqual(svc.get_template('nao-existe', 1), default_template())
        self.assertEqual(svc.get_template('custom:abc', 1), default_template())


if __name__ == '__main__':
    unittest.main()
