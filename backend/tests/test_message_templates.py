import os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

_DB=tempfile.NamedTemporaryFile(suffix='.db',delete=False); _DB.close()
os.environ.update({'DATABASE_URL':f"sqlite:///{_DB.name.replace(chr(92),'/')}",'SECRET_KEY':'message-test','FLASK_DEBUG':'true'})
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db, limiter
from models.empresa import Empresa
from models.user import User
from models.message_template import MessageTemplate
from services.message_template_service import seed_for_empresa
from services.message_template_service import render_email_for_empresa
from utils.auth import generate_token

class MessageTemplatesTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=create_app(); cls.app.config['TESTING']=True; limiter.enabled=False
  with cls.app.app_context():
   db.create_all(); a=Empresa(nome='A',slug='mt-a'); b=Empresa(nome='B',slug='mt-b'); db.session.add_all([a,b]); db.session.flush(); db.session.add_all([User(empresa_id=a.id,nome='A',email='a@mt.test',password_hash='x',role='admin'),User(empresa_id=a.id,nome='V',email='v@mt.test',password_hash='x',role='viewer'),User(empresa_id=b.id,nome='B',email='b@mt.test',password_hash='x',role='admin')]); db.session.commit(); cls.a,cls.viewer,cls.b=1,2,3
 @classmethod
 def tearDownClass(cls):
  with cls.app.app_context(): db.session.remove(); db.drop_all(); db.engine.dispose()
  os.unlink(_DB.name)
 def _headers(self,user):
  with self.app.app_context(): return {'Authorization':'Bearer '+generate_token(user)}
 def _request(self,user,path,method='GET',body=None): return self.app.test_client().open(path,method=method,headers=self._headers(user),json=body)
 def test_create_preview_and_tenant_isolation(self):
  payload={'canal':'email','chave':'boas-vindas','nome':'Boas vindas','assunto':'Olá {{nome}}','corpo':'Olá {{nome}}, acesse {{link}}','variaveisPermitidas':['nome','link']}
  with patch('services.email_service.send_email') as send_email:
   made=self._request(self.a,'/api/v1/message-templates','POST',payload); self.assertEqual(made.status_code,201); identifier=made.json['data']['id']
  preview=self._request(self.a,f'/api/v1/message-templates/{identifier}/preview','POST',{'variaveis':{'nome':'<img>','link':'https://a.test'}}); self.assertEqual(preview.status_code,200); self.assertIn('&lt;img&gt;',preview.json['data']['html']); send_email.assert_not_called()
  self.assertEqual(self._request(self.viewer,f'/api/v1/message-templates/{identifier}/preview','POST',{'variaveis':{}}).status_code,403)
  self.assertEqual(self._request(self.b,f'/api/v1/message-templates/{identifier}').status_code,404)
  self.assertEqual(self._request(self.viewer,'/api/v1/message-templates','POST',payload).status_code,403)
 def test_rejects_xss_unknown_variables_and_whatsapp_has_no_subject(self):
  bad={'canal':'whatsapp','chave':'w','nome':'W','corpo':'<b>{{desconhecida}}</b>','variaveisPermitidas':['nome']}
  self.assertEqual(self._request(self.a,'/api/v1/message-templates','POST',bad).status_code,400)
  good={'canal':'whatsapp','chave':'w','nome':'W','corpo':'Olá {{nome}}','variaveisPermitidas':['nome']}
  made=self._request(self.a,'/api/v1/message-templates','POST',good); self.assertEqual(made.status_code,201); self.assertIsNone(made.json['data']['assunto'])
  self.assertEqual(self._request(self.a,f"/api/v1/message-templates/{made.json['data']['id']}/preview",'POST',{'variaveis':{'empresa':'X'}}).status_code,400)
 def test_rejects_non_https_link_and_malformed_placeholder(self):
  base={'canal':'email','chave':'link','nome':'Link','assunto':'Assunto','corpo':'{{link}}','variaveisPermitidas':['link']}
  made=self._request(self.a,'/api/v1/message-templates','POST',base); identifier=made.json['data']['id']
  for link in ('http://a.test','javascript:alert(1)','data:text/plain,x'):
   self.assertEqual(self._request(self.a,f'/api/v1/message-templates/{identifier}/preview','POST',{'variaveis':{'link':link}}).status_code,400)
  base['chave']='malformado'; base['corpo']='Olá {{nome'; base['variaveisPermitidas']=['nome']
  self.assertEqual(self._request(self.a,'/api/v1/message-templates','POST',base).status_code,400)
 def test_seed_for_new_company_creates_tenant_defaults(self):
  with self.app.app_context():
   company=Empresa(nome='Novo',slug='mt-novo'); db.session.add(company); db.session.commit(); seed_for_empresa(company.id)
   self.assertEqual(MessageTemplate.query.filter_by(empresa_id=company.id,canal='email').count(),2)
 def test_adapter_rejects_unsafe_links_before_rendering(self):
  with self.app.app_context():
   seed_for_empresa(1)
   for link in ('http://a.test','javascript:alert(1)','data:text/plain,x'):
    with self.assertRaises(ValueError): render_email_for_empresa(1,'convite',{'link':link,'papel':'viewer','empresa':'A'})

if __name__=='__main__': unittest.main()
