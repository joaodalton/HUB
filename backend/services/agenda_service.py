"""Visao operacional de prazos, sem estado proprio de Agenda.

Nesta primeira fase os itens da agenda sao sempre derivados de Pendencia. Ao
entrar Financeiro ou Rateio, cada fonte deve ser adicionada aqui como consulta
derivada, nunca como duplicacao persistida de evento.
"""
from datetime import date, datetime, timedelta

from flask import g

from models.pendencia import Pendencia


VISOES_VALIDAS = frozenset({'dia', 'semana', 'mes'})
MAX_INTERVAL_DAYS = 92
MAX_ITENS = 500


def listar_itens(*, inicio: str | None, fim: str | None, visao: str | None) -> dict:
    """Lista pendencias com prazo no intervalo inclusivo solicitado.

    Datas recebidas sao calendarios locais (YYYY-MM-DD); o banco guarda
    ``prazo`` sem timezone, portanto o filtro usa [inicio 00:00, dia seguinte
    a fim 00:00), sem perder itens com horario no ultimo dia.
    """
    visao_normalizada = (visao or 'mes').lower()
    if visao_normalizada not in VISOES_VALIDAS:
        raise ValueError('Visao invalida. Use dia, semana ou mes.')

    inicio_data, fim_data = _resolver_periodo(inicio, fim, visao_normalizada)
    inicio_datetime = datetime.combine(inicio_data, datetime.min.time())
    try:
        fim_exclusivo = datetime.combine(fim_data + timedelta(days=1), datetime.min.time())
    except OverflowError as exc:
        raise ValueError('Fim esta fora do intervalo suportado.') from exc

    # TenantMixin injeta o filtro nas queries ORM. O filtro explicito deixa a
    # fronteira de seguranca evidente para esta consulta de calendario.
    # Itens concluidos/cancelados deixam a agenda imediatamente porque ela e
    # uma fila operacional, nao um historico paralelo de eventos.
    pendencias = (
        Pendencia.query
        .filter(
            Pendencia.empresa_id == g.current_empresa_id,
            Pendencia.prazo.isnot(None),
            Pendencia.status == 'aberta',
            Pendencia.prazo >= inicio_datetime,
            Pendencia.prazo < fim_exclusivo,
        )
        .order_by(Pendencia.prazo.asc(), Pendencia.id.asc())
        .limit(MAX_ITENS)
        .all()
    )

    return {
        'visao': visao_normalizada,
        'inicio': inicio_data.isoformat(),
        'fim': fim_data.isoformat(),
        'itens': [_agenda_item(pendencia) for pendencia in pendencias],
    }


def _resolver_periodo(inicio: str | None, fim: str | None, visao: str) -> tuple[date, date]:
    if bool(inicio) != bool(fim):
        raise ValueError('Inicio e fim devem ser informados juntos.')

    if inicio and fim:
        inicio_data = _parse_data(inicio, 'Inicio')
        fim_data = _parse_data(fim, 'Fim')
        if inicio_data > fim_data:
            raise ValueError('Inicio nao pode ser posterior ao fim.')
        if (fim_data - inicio_data).days > MAX_INTERVAL_DAYS:
            raise ValueError(f'Intervalo nao pode exceder {MAX_INTERVAL_DAYS + 1} dias.')
        return inicio_data, fim_data

    hoje = date.today()
    if visao == 'dia':
        return hoje, hoje
    if visao == 'semana':
        inicio_semana = hoje - timedelta(days=(hoje.weekday() + 1) % 7)
        return inicio_semana, inicio_semana + timedelta(days=6)

    inicio_mes = hoje.replace(day=1)
    proximo_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1)
    return inicio_mes, proximo_mes - timedelta(days=1)


def _parse_data(valor: str, nome: str) -> date:
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(f'{nome} deve usar o formato YYYY-MM-DD.') from exc


def _agenda_item(pendencia: Pendencia) -> dict:
    """Projecao minima; nao expoe comentarios, email, metadados ou descricao."""
    return {
        'fonte': 'pendencia',
        'pendenciaId': pendencia.id,
        'id': pendencia.id,
        'titulo': pendencia.titulo,
        'tipo': pendencia.tipo,
        'categoria': pendencia.categoria,
        'origem': pendencia.origem,
        'prazo': pendencia.prazo.isoformat(),
        'prioridade': pendencia.prioridade,
        'status': pendencia.status,
        'clienteId': pendencia.client_id,
        'ucId': pendencia.consumer_unit_id,
        'usinaId': pendencia.plant_id,
        'documentoId': pendencia.document_id,
    }
