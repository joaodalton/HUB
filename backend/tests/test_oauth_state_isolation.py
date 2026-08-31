import os, sys, tempfile, unittest
from datetime import datetime, timedelta
from pathlib import Path

_DB=tempfile.NamedTemporaryFile(suffix='.db',delete=False); _DB.close()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from config import Config
from extensions import db
from models.empresa import Empresa
from models.setting import Setting
from services.oauth_service import _STATE_KEY_PREFIX, _store_pending_state
try:
 from .support import IsolatedTestRuntime
except ImportError:
 from support import IsolatedTestRuntime

class OAuthStateIsolationTest(IsolatedTestRuntime, unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92),'/')}",'oauth-state-test')
  cls.app=create_app()
  with cls.app.app_context():
   db.create_all(); db.session.add_all([Empresa(nome='A',slug='oauth-a'),Empresa(nome='B',slug='oauth-b')]); db.session.commit()
 @classmethod
 def tearDownClass(cls):
  with cls.app.app_context(): db.session.remove(); db.drop_all(); db.engine.dispose()
  os.unlink(_DB.name)
  cls.restore_test_runtime()
 def test_storing_a_state_only_purges_expired_states_for_a(self):
  with self.app.app_context():
   expired=Setting(empresa_id=2,chave=_STATE_KEY_PREFIX+'b',valor='{}',created_at=datetime.utcnow()-timedelta(minutes=16)); db.session.add(expired); db.session.commit()
   _store_pending_state('a','verifier',1)
   self.assertIsNotNone(Setting.query.filter_by(empresa_id=2,chave=_STATE_KEY_PREFIX+'b').first())

if __name__=='__main__': unittest.main()
