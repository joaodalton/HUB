"""ASAAS transport contract: reconciliation is a lookup, never a retry of POST."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.asaas_client import AsaasClient, AsaasError


class FaturaAsaasClientTest(unittest.TestCase):
    def setUp(self):
        self.client = AsaasClient.__new__(AsaasClient)
        self.client._headers = {'access_token': 'test-only-secret'}
        self.client._base_url = 'https://api-sandbox.asaas.com/v3'

    def test_lookup_sends_query_and_requires_exact_unique_match(self):
        response = Mock(ok=True)
        response.json.return_value = {'data': [{'id': 'pay_1', 'externalReference': 'hub-abc'}], 'hasMore': False}
        with patch('services.asaas_client.requests.request', return_value=response) as request:
            self.assertEqual(self.client.consultar_por_referencia('hub-abc')['id'], 'pay_1')
        self.assertEqual(request.call_args.args[0], 'GET')
        self.assertTrue(request.call_args.args[1].endswith('/payments'))
        self.assertEqual(request.call_args.kwargs['params'],
                         {'externalReference': 'hub-abc', 'limit': 2, 'offset': 0})
        self.assertIsNone(request.call_args.kwargs['json'])
        self.assertFalse(request.call_args.kwargs['allow_redirects'])

    def test_empty_lookup_does_not_issue_payment(self):
        with patch.object(self.client, '_request', return_value={'data': [], 'hasMore': False}) as request:
            self.assertIsNone(self.client.consultar_por_referencia('hub-abc'))
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], 'GET')

    def test_ambiguous_malformed_or_non_exact_lookup_is_rejected(self):
        for payload in ({}, {'data': []}, {'data': [], 'hasMore': True},
                        {'data': [{'externalReference': 'other'}], 'hasMore': False},
                        {'data': [None], 'hasMore': False},
                        {'data': [{'externalReference': 'hub-abc'}] * 2, 'hasMore': False}):
            with self.subTest(payload=payload), patch.object(self.client, '_request', return_value=payload):
                with self.assertRaises(AsaasError):
                    self.client.consultar_por_referencia('hub-abc')

    def test_transport_failure_and_invalid_success_are_ambiguous_without_retry(self):
        response = Mock(ok=True)
        response.json.side_effect = ValueError('invalid JSON')
        for options in ({'side_effect': requests.Timeout('test-only-secret')}, {'return_value': response}):
            with patch('services.asaas_client.requests.request', **options) as request:
                with self.assertRaises(AsaasError) as error:
                    self.client.criar_cobranca({})
                self.assertNotIn('test-only-secret', str(error.exception))
                request.assert_called_once()

    def test_provider_errors_do_not_expose_response_secrets(self):
        response = Mock(ok=False)
        response.json.return_value = {'errors': [{'description': 'test-only-secret'}]}
        with patch('services.asaas_client.requests.request', return_value=response):
            with self.assertRaises(AsaasError) as error:
                self.client.criar_cobranca({})
        self.assertNotIn('test-only-secret', str(error.exception))
