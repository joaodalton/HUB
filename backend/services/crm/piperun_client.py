"""PipeRun CRM transport; the caller supplies the decrypted token."""
import requests

PIPERUN_API_BASE_URL = 'https://api.pipe.run/v1'


class PipeRunError(RuntimeError):
    pass


class PipeRunClient:
    def __init__(self, token: str):
        if not token:
            raise PipeRunError('Credencial PipeRun nao configurada.')
        self._base_url = PIPERUN_API_BASE_URL
        self._headers = {'token': token, 'Content-Type': 'application/json', 'User-Agent': 'HUB/1.0'}

    def testar_conexao(self) -> dict:
        result = self._request('GET', '')
        if result.get('message') != 'OK':
            raise PipeRunError('PipeRun recusou a conexao.')
        return result

    def listar_negocios(self, cursor: str | None = None, show: int = 100, updated_at_start: str | None = None) -> dict:
        params = {'show': show}
        if cursor:
            params['cursor'] = cursor
        if updated_at_start:
            params['updated_at_start'] = updated_at_start
        return self._request('GET', '/deals', params=params)

    def _request(self, method: str, path: str, *, params=None) -> dict:
        try:
            response = requests.request(method, f'{self._base_url}{path}', headers=self._headers,
                params=params, timeout=20, allow_redirects=False)
        except requests.RequestException as exc:
            raise PipeRunError('Nao foi possivel comunicar com o PipeRun.') from exc
        if not response.ok:
            raise PipeRunError('PipeRun recusou a operacao.')
        try:
            result = response.json()
        except ValueError as exc:
            raise PipeRunError('Resposta PipeRun invalida.') from exc
        if not isinstance(result, dict):
            raise PipeRunError('Resposta PipeRun invalida.')
        if result.get('success') is False:
            raise PipeRunError('PipeRun recusou a operacao.')
        return result
