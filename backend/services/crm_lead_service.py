"""Sync e leitura de leads/negocios importados de um CRM externo (PipeRun v1)."""
from datetime import datetime

from extensions import db
from models.api_credential import ApiCredential
from models.crm_lead import CrmLead
from services.crm.piperun_client import PipeRunClient

MAX_PAGINAS = 50


def listar(empresa_id: int, provider: str | None = None) -> list[dict]:
    query = CrmLead.query.filter_by(empresa_id=empresa_id)
    if provider:
        query = query.filter_by(provider=provider)
    leads = query.order_by(CrmLead.atualizado_em_origem.desc(), CrmLead.importado_em.desc()).all()
    return [lead.to_dict() for lead in leads]


def sincronizar(empresa_id: int, provider: str = 'piperun') -> dict:
    credential = ApiCredential.query.filter_by(empresa_id=empresa_id, provider=provider, interna=False).first()
    if not credential:
        raise ValueError('Nenhuma credencial PipeRun configurada para esta empresa.')
    client = PipeRunClient(credential.get_segredo())

    total_importados = 0
    total_atualizados = 0
    cursor = None
    for _ in range(MAX_PAGINAS):
        resposta = client.listar_negocios(cursor=cursor)
        for deal in resposta.get('data') or []:
            criado = _upsert(empresa_id, provider, deal)
            if criado:
                total_importados += 1
            else:
                total_atualizados += 1
        cursor = (resposta.get('meta') or {}).get('cursor', {}).get('next')
        if not cursor:
            break
    db.session.commit()
    return {'total_importados': total_importados, 'total_atualizados': total_atualizados}


def _upsert(empresa_id: int, provider: str, deal: dict) -> bool:
    external_id = str(deal.get('id'))
    lead = CrmLead.query.filter_by(empresa_id=empresa_id, provider=provider, external_id=external_id).first()
    criado = lead is None
    if lead is None:
        lead = CrmLead(empresa_id=empresa_id, provider=provider, external_id=external_id)
        db.session.add(lead)
    lead.titulo = deal.get('title')
    lead.status = deal.get('status')
    lead.valor = deal.get('value')
    lead.pipeline_nome = (deal.get('pipeline') or {}).get('name') if isinstance(deal.get('pipeline'), dict) else None
    lead.etapa_nome = (deal.get('stage') or {}).get('name') if isinstance(deal.get('stage'), dict) else None
    lead.dados_brutos = deal
    lead.criado_em_origem = _parse_data(deal.get('created_at'))
    lead.atualizado_em_origem = _parse_data(deal.get('updated_at'))
    return criado


def _parse_data(valor) -> datetime | None:
    if not valor:
        return None
    for formato in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor, formato)
        except (ValueError, TypeError):
            continue
    return None
