import unittest
from unittest.mock import MagicMock, patch

from services.google_reports_auth import (
    REQUIRED_REPORT_SCOPES, ReportAccountMissingError, ReportScopeError, get_report_credentials,
)


class GoogleReportsAuthTest(unittest.TestCase):
    @patch('services.google_reports_auth.GoogleAccount')
    def test_no_active_account_raises_account_missing(self, mock_model):
        mock_model.query.filter_by.return_value.first.return_value = None
        with self.assertRaises(ReportAccountMissingError):
            get_report_credentials(empresa_id=1)

    @patch('services.google_reports_auth.GoogleAccount')
    def test_account_without_new_scopes_raises_scope_error(self, mock_model):
        account = MagicMock()
        account.scopes = 'https://www.googleapis.com/auth/drive.readonly'
        mock_model.query.filter_by.return_value.first.return_value = account
        with self.assertRaises(ReportScopeError):
            get_report_credentials(empresa_id=1)

    @patch('services.google_reports_auth._build_oauth_credentials')
    @patch('services.google_reports_auth.GoogleAccount')
    def test_account_with_new_scopes_returns_credentials(self, mock_model, mock_build):
        account = MagicMock()
        account.scopes = ','.join(REQUIRED_REPORT_SCOPES + ['https://www.googleapis.com/auth/drive.readonly'])
        mock_model.query.filter_by.return_value.first.return_value = account
        mock_build.return_value = 'creds-fake'
        result = get_report_credentials(empresa_id=1)
        self.assertEqual(result, 'creds-fake')


if __name__ == '__main__':
    unittest.main()
