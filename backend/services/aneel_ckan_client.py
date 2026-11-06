"""Cliente restrito para os dados públicos CKAN da ANEEL."""
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

OFFICIAL_HOST = 'dadosabertos.aneel.gov.br'
REQUIRED_COLUMNS = ('SigNomeAgente', 'DscComponenteTarifario', 'DscBaseTarifaria', 'DscSubGrupoTarifario',
                    'DscModalidadeTarifaria', 'DscClasseConsumidor', 'DscSubClasseConsumidor',
                    'DscDetalheConsumidor', 'DscPostoTarifario', 'VlrComponenteTarifario', 'DscUnidade',
                    'DatInicioVigencia', 'DatFimVigencia', 'DscResolucaoHomologatoria')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AneelCkanUnavailable(RuntimeError):
    pass


class AneelCkanInvalidResponse(RuntimeError):
    pass


class AneelCkanClient:
    def __init__(self, *, api_url='https://dadosabertos.aneel.gov.br/api/3/action', timeout_seconds=15, token=''):
        parsed = urlsplit(api_url)
        if parsed.scheme != 'https' or parsed.hostname != OFFICIAL_HOST:
            raise ValueError('A API CKAN deve usar o host oficial HTTPS da ANEEL.')
        self.api_url = api_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.token = token

    def copel_fio_b(self, year: int, max_rows=1000):
        resource = self._resource(year)
        filters = {'SigNomeAgente': 'COPEL-DIS', 'DscComponenteTarifario': 'TUSD_FioB',
                   'DscBaseTarifaria': 'Tarifa de Aplicação', 'DscDetalheConsumidor': 'SCEE',
                   'DscUnidade': 'R$/MWh'}
        records, generated_at = self._records(resource['id'], filters, max_rows)
        return records, {'resource_id': resource['id'], 'source_url': resource.get('url') or self.api_url,
                         'source_version': resource.get('last_modified') or resource.get('hash') or generated_at,
                         'generated_at': generated_at, 'filters': filters}

    def _resource(self, year: int):
        if type(year) is not int or year < 2010 or year > datetime.utcnow().year + 1:
            raise ValueError('Ano ANEEL inválido.')
        resources = self._request('package_show', {'id': 'componentes-tarifarias'}).get('resources')
        expected = f'componentes-tarifarias-{year}.csv'
        if not isinstance(resources, list):
            raise AneelCkanInvalidResponse('Resposta CKAN sem recursos do dataset.')
        for resource in resources:
            if isinstance(resource, dict) and resource.get('name') == expected and resource.get('datastore_active') is True and resource.get('id'):
                return resource
        raise ValueError(f'Recurso ANEEL ativo para {year} não encontrado.')

    def _records(self, resource_id, filters, max_rows):
        rows, next_page = [], None
        while True:
            if len(rows) >= max_rows:
                raise ValueError('Consulta ANEEL excede o limite de registros permitido.')
            query = {'resource_id': resource_id, 'filters': json.dumps(filters),
                     'limit': min(500, max_rows - len(rows)), 'include_next_page': 'true'}
            if next_page:
                query['filters'] = json.dumps({**filters, **next_page})
            result = self._request('datastore_search', query)
            page = result.get('records')
            if not isinstance(page, list):
                raise AneelCkanInvalidResponse('Resposta CKAN sem registros válidos.')
            if any(not isinstance(row, dict) or any(not isinstance(row.get(name), str) for name in REQUIRED_COLUMNS) for row in page):
                raise AneelCkanInvalidResponse('Resposta CKAN com schema inválido.')
            rows.extend(page)
            next_page = result.get('next_page')
            if not next_page:
                return rows, rows[0].get('DatGeracaoConjuntoDados') if rows else None
            if not isinstance(next_page, dict):
                raise AneelCkanInvalidResponse('Paginação CKAN inválida.')

    def _request(self, action, params):
        request = Request(f'{self.api_url}/{action}?{urlencode(params)}', headers={'Authorization': self.token} if self.token else {})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise AneelCkanUnavailable('ANEEL indisponível. Tente novamente mais tarde.') from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AneelCkanInvalidResponse('Resposta inválida da API ANEEL.') from exc
        if not isinstance(payload, dict) or payload.get('success') is not True or not isinstance(payload.get('result'), dict):
            raise AneelCkanInvalidResponse('Resposta inválida da API ANEEL.')
        return payload['result']
