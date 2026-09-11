"""Agenda temporal unificada: pendências derivadas + eventos próprios."""
from datetime import date, datetime, timedelta

from flask import g

from extensions import db
from models.agenda_event import AgendaEvent
from models.pendencia import Pendencia
from services.log_service import LogService

VISOES_VALIDAS = frozenset({'dia', 'semana', 'mes'})
MAX_INTERVAL_DAYS = 92
MAX_ITENS = 500


def listar_itens(*, inicio: str | None, fim: str | None, visao: str | None) -> dict:
    visao_normalizada = (visao or 'mes').lower()
    if visao_normalizada not in VISOES_VALIDAS:
        raise ValueError('Visao invalida. Use dia, semana ou mes.')
    inicio_data, fim_data = _resolver_periodo(inicio, fim, visao_normalizada)
    inicio_datetime = datetime.combine(inicio_data, datetime.min.time())
    try:
        fim_exclusivo = datetime.combine(fim_data + timedelta(days=1), datetime.min.time())
    except OverflowError as exc:
        raise ValueError('Fim esta fora do intervalo suportado.') from exc
    pendencias = Pendencia.query.filter(
        Pendencia.empresa_id == g.current_empresa_id, Pendencia.prazo.isnot(None),
        Pendencia.status == 'aberta', Pendencia.prazo >= inicio_datetime, Pendencia.prazo < fim_exclusivo,
    ).order_by(Pendencia.prazo.asc(), Pendencia.id.asc()).limit(MAX_ITENS).all()
    eventos = AgendaEvent.query.filter(
        AgendaEvent.empresa_id == g.current_empresa_id, AgendaEvent.status == 'aberto',
        AgendaEvent.inicio >= inicio_datetime, AgendaEvent.inicio < fim_exclusivo,
    ).order_by(AgendaEvent.inicio.asc(), AgendaEvent.id.asc()).limit(MAX_ITENS).all()
    itens = [_pendencia_item(item) for item in pendencias] + [_evento_item(item) for item in eventos]
    itens.sort(key=lambda item: (item['prazo'], item['fonte'], item['id']))
    return {'visao': visao_normalizada, 'inicio': inicio_data.isoformat(), 'fim': fim_data.isoformat(), 'itens': itens[:MAX_ITENS]}


def criar_evento(data: dict) -> dict:
    event = AgendaEvent(empresa_id=g.current_empresa_id, **_event_values(data))
    db.session.add(event)
    db.session.commit()
    _audit('agenda_event_create', event)
    return event.to_dict()


def atualizar_evento(event_id: int, data: dict) -> dict | None:
    event = _event(event_id)
    if not event:
        return None
    for key, value in _event_values({**event.to_dict(), **data}).items():
        setattr(event, key, value)
    db.session.commit()
    _audit('agenda_event_update', event)
    return event.to_dict()


def cancelar_evento(event_id: int) -> bool:
    event = _event(event_id)
    if not event:
        return False
    event.status = 'cancelado'
    db.session.commit()
    _audit('agenda_event_cancel', event)
    return True


def _event(event_id: int):
    return AgendaEvent.query.filter_by(id=event_id, empresa_id=g.current_empresa_id).first()


def _event_values(data: dict) -> dict:
    title = str(data.get('titulo') or '').strip()
    category = str(data.get('categoria') or 'Operacional').strip()
    start = _parse_datetime(data.get('inicio'))
    end = _parse_datetime(data.get('fim')) if data.get('fim') else None
    if not title or len(title) > 200 or not category or len(category) > 50 or not start:
        raise ValueError('Titulo, categoria e inicio do evento sao obrigatorios.')
    if end and end < start:
        raise ValueError('Fim do evento nao pode ser anterior ao inicio.')
    return {'titulo': title, 'descricao': str(data.get('descricao') or '').strip() or None,
            'inicio': start, 'fim': end, 'categoria': category}


def _resolver_periodo(inicio: str | None, fim: str | None, visao: str) -> tuple[date, date]:
    if bool(inicio) != bool(fim):
        raise ValueError('Inicio e fim devem ser informados juntos.')
    if inicio and fim:
        inicio_data, fim_data = _parse_data(inicio, 'Inicio'), _parse_data(fim, 'Fim')
        if inicio_data > fim_data:
            raise ValueError('Inicio nao pode ser posterior ao fim.')
        if (fim_data - inicio_data).days > MAX_INTERVAL_DAYS:
            raise ValueError(f'Intervalo nao pode exceder {MAX_INTERVAL_DAYS + 1} dias.')
        return inicio_data, fim_data
    hoje = date.today()
    if visao == 'dia': return hoje, hoje
    if visao == 'semana':
        inicio_data = hoje - timedelta(days=(hoje.weekday() + 1) % 7)
        return inicio_data, inicio_data + timedelta(days=6)
    inicio_data = hoje.replace(day=1)
    return inicio_data, (inicio_data.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _parse_data(value: str, label: str) -> date:
    try: return date.fromisoformat(value)
    except (TypeError, ValueError) as exc: raise ValueError(f'{label} deve usar YYYY-MM-DD.') from exc


def _parse_datetime(value) -> datetime | None:
    if not value: return None
    try: return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        try: return datetime.combine(date.fromisoformat(str(value)), datetime.min.time())
        except (TypeError, ValueError) as exc: raise ValueError('Data/hora invalida.') from exc


def _pendencia_item(pendencia: Pendencia) -> dict:
    return {'fonte': 'pendencia', 'pendenciaId': pendencia.id, 'eventoId': None, 'id': pendencia.id,
            'titulo': pendencia.titulo, 'descricao': pendencia.descricao, 'tipo': pendencia.tipo,
            'categoria': pendencia.categoria, 'origem': pendencia.origem, 'prioridade': pendencia.prioridade,
            'status': pendencia.status, 'prazo': pendencia.prazo.isoformat(), 'fim': None,
            'clienteId': pendencia.client_id, 'ucId': pendencia.consumer_unit_id, 'usinaId': pendencia.plant_id,
            'documentoId': pendencia.document_id}


def _evento_item(evento: AgendaEvent) -> dict:
    return {'fonte': 'evento', 'pendenciaId': None, 'eventoId': evento.id, 'id': evento.id,
            'titulo': evento.titulo, 'descricao': evento.descricao, 'tipo': 'evento', 'categoria': evento.categoria,
            'origem': 'Agenda', 'prioridade': 'media', 'status': evento.status, 'prazo': evento.inicio.isoformat(),
            'fim': evento.fim.isoformat() if evento.fim else None, 'clienteId': None, 'ucId': None,
            'usinaId': None, 'documentoId': None}


def _audit(action: str, event: AgendaEvent) -> None:
    LogService.info(acao=action, mensagem=f'Evento de agenda "{event.titulo}" alterado', entidade='AgendaEvent', entidade_id=event.id)
