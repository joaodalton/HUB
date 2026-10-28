# backend/services/neon_service.py
"""Leitura do armazenamento usado nos projetos Neon (dev/producao) via API
oficial (console.neon.tech/api/v2). Somente leitura -- nunca troca a conexao
ativa do app (SQLALCHEMY_DATABASE_URI e fixa no boot, ver config.py)."""
import requests

from config import Config

NEON_API_BASE_URL = 'https://console.neon.tech/api/v2'


class NeonError(RuntimeError):
    pass


def _headers() -> dict:
    if not Config.NEON_API_KEY:
        raise NeonError('NEON_API_KEY nao configurada.')
    return {'Authorization': f'Bearer {Config.NEON_API_KEY}', 'Accept': 'application/json'}


def _get(path: str, project_id: str) -> dict:
    response = requests.get(f'{NEON_API_BASE_URL}{path}', headers=_headers(), timeout=10)
    if response.status_code != 200:
        raise NeonError(f'Neon API retornou {response.status_code} para o projeto {project_id}.')
    return response.json()


def _branches_storage(project_id: str) -> dict:
    """Soma logical_size (bytes) de todas as branches do projeto."""
    branches = _get(f'/projects/{project_id}/branches', project_id).get('branches', [])
    detalhes = [{
        'nome': branch.get('name'),
        'tamanhoBytes': branch.get('logical_size') or 0,
    } for branch in branches]
    total = sum(branch['tamanhoBytes'] for branch in detalhes)
    return {'totalBytes': total, 'branches': detalhes}


def _project_info(project_id: str) -> dict:
    """Versao do Postgres e limite de armazenamento do plano."""
    project = _get(f'/projects/{project_id}', project_id).get('project', {})
    return {
        'pgVersion': project.get('pg_version'),
        'limiteBytes': project.get('branch_logical_size_limit_bytes'),
    }


def _compute_status(project_id: str) -> str | None:
    """Estado do compute primario (ex.: 'active', 'idle') -- 'idle' no Neon
    free significa hibernado por inatividade, nao erro."""
    endpoints = _get(f'/projects/{project_id}/endpoints', project_id).get('endpoints', [])
    if not endpoints:
        return None
    return endpoints[0].get('current_state')


def get_storage_summary() -> list[dict]:
    """Retorna o uso de armazenamento por ambiente configurado (dev/producao).
    Ambiente sem NEON_PROJECT_ID_* configurado nao entra na lista."""
    ambientes = [
        ('dev', Config.NEON_PROJECT_ID_DEV),
        ('producao', Config.NEON_PROJECT_ID_PROD),
    ]
    resultado = []
    for label, project_id in ambientes:
        if not project_id:
            continue
        storage = _branches_storage(project_id)
        info = _project_info(project_id)
        resultado.append({
            'ambiente': label,
            'projectId': project_id,
            'totalBytes': storage['totalBytes'],
            'branches': storage['branches'],
            'limiteBytes': info['limiteBytes'],
            'pgVersion': info['pgVersion'],
            'computeStatus': _compute_status(project_id),
        })
    return resultado
