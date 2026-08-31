"""Garante que a excecao HTTP do OAuthlib nunca vaze para producao."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config  # noqa: E402
from app import create_app  # noqa: E402
from routes.oauth_routes import _configured_callback_url  # noqa: E402
from services.oauth_service import _configure_transport_security  # noqa: E402


class OAuthTransportSecurityTest(unittest.TestCase):
    def setUp(self):
        self.original_debug = Config.DEBUG
        self.original_allow = Config.OAUTH_ALLOW_INSECURE_TRANSPORT
        self.original_uri = Config.GOOGLE_OAUTH_REDIRECT_URI
        self.original_frontend = Config.FRONTEND_URL
        self.original_env = os.environ.get('OAUTHLIB_INSECURE_TRANSPORT')

    def tearDown(self):
        Config.DEBUG = self.original_debug
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = self.original_allow
        Config.GOOGLE_OAUTH_REDIRECT_URI = self.original_uri
        Config.FRONTEND_URL = self.original_frontend
        if self.original_env is None:
            os.environ.pop('OAUTHLIB_INSECURE_TRANSPORT', None)
        else:
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = self.original_env

    def test_production_requires_https_and_removes_insecure_inherited_flag(self):
        Config.DEBUG = False
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = False
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'http://localhost:8000/api/v1/oauth/google/callback'
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        with self.assertRaisesRegex(RuntimeError, 'HTTPS'):
            _configure_transport_security()
        self.assertNotIn('OAUTHLIB_INSECURE_TRANSPORT', os.environ)

    def test_production_https_removes_insecure_inherited_flag(self):
        Config.DEBUG = False
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'https://api.example.test/api/v1/oauth/google/callback'
        Config.FRONTEND_URL = 'https://frontend.example.test'
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        _configure_transport_security()
        self.assertNotIn('OAUTHLIB_INSECURE_TRANSPORT', os.environ)

    def test_production_rejects_insecure_or_non_absolute_frontend_url(self):
        Config.DEBUG = False
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'https://api.example.test/api/v1/oauth/google/callback'
        Config.FRONTEND_URL = 'http://frontend.example.test'
        with self.assertRaisesRegex(RuntimeError, 'FRONTEND_URL'):
            _configure_transport_security()
        Config.FRONTEND_URL = 'https://user:secret@frontend.example.test/#fragment'
        with self.assertRaisesRegex(RuntimeError, 'FRONTEND_URL'):
            _configure_transport_security()

    def test_only_explicit_local_development_can_enable_http(self):
        Config.DEBUG = True
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = True
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'http://localhost:8000/api/v1/oauth/google/callback'
        Config.FRONTEND_URL = 'http://localhost:5173'
        _configure_transport_security()
        self.assertEqual(os.environ.get('OAUTHLIB_INSECURE_TRANSPORT'), '1')

    def test_debug_without_explicit_opt_in_cannot_enable_http(self):
        Config.DEBUG = True
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = False
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'http://localhost:8000/api/v1/oauth/google/callback'
        Config.FRONTEND_URL = 'http://localhost:5173'
        with self.assertRaisesRegex(RuntimeError, 'HTTPS'):
            _configure_transport_security()

    def test_debug_public_http_callback_is_rejected(self):
        Config.DEBUG = True
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = True
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'http://example.test/api/v1/oauth/google/callback'
        with self.assertRaisesRegex(RuntimeError, 'HTTPS'):
            _configure_transport_security()

    def test_callback_uses_the_configured_https_url_not_internal_request_scheme(self):
        Config.DEBUG = False
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = False
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'https://api.example.test/api/v1/oauth/google/callback'
        Config.FRONTEND_URL = 'https://frontend.example.test'
        self.assertEqual(
            _configured_callback_url(b'code=abc&state=expected'),
            'https://api.example.test/api/v1/oauth/google/callback?code=abc&state=expected',
        )
        app = create_app()
        app.config['TESTING'] = True
        with patch('routes.oauth_routes.handle_callback') as callback:
            response = app.test_client().get(
                '/api/v1/oauth/google/callback?code=abc&state=expected',
                base_url='http://internal-render-service',
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            callback.call_args.args[0],
            'https://api.example.test/api/v1/oauth/google/callback?code=abc&state=expected',
        )

    def test_callback_error_validates_transport_and_url_encodes_reason(self):
        Config.DEBUG = False
        Config.OAUTH_ALLOW_INSECURE_TRANSPORT = False
        Config.GOOGLE_OAUTH_REDIRECT_URI = 'https://api.example.test/api/v1/oauth/google/callback'
        Config.FRONTEND_URL = 'https://frontend.example.test'
        app = create_app()
        app.config['TESTING'] = True
        response = app.test_client().get('/api/v1/oauth/google/callback?error=access_denied%26retry')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers['Location'],
            'https://frontend.example.test/configuracoes?google_oauth=erro&motivo=access_denied%26retry',
        )
        Config.FRONTEND_URL = 'http://frontend.example.test'
        rejected = app.test_client().get('/api/v1/oauth/google/callback?error=access_denied')
        self.assertEqual(rejected.status_code, 503)


if __name__ == '__main__':
    unittest.main()
