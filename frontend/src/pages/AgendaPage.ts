import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getAgenda, type AgendaItem, type AgendaModo } from '../services/agendaService';
import { prioridadeLabel, prioridadeTone, tipoLabel } from '../services/pendenciasService';

const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const DIAS_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
const MODOS: Array<{ value: AgendaModo; label: string }> = [{ value: 'dia', label: 'Dia' }, { value: 'semana', label: 'Semana' }, { value: 'mes', label: 'Mês' }];

export function createAgendaPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  const today = startOfDay(new Date());
  let modo: AgendaModo = 'mes';
  let referenceDate = today;
  let selectedDate = toDateKey(today);
  let items: AgendaItem[] = [];
  let loadingAgenda = true;
  let loadError = false;

  const layout = createBaseLayout({ content, eyebrow: 'Agenda', title: 'Prazos das suas pendências' });
  render();
  void loadAgenda();
  return layout;

  async function loadAgenda(): Promise<void> {
    const { inicio, fim } = getRange(modo, referenceDate);
    loadingAgenda = true;
    loadError = false;
    render();
    loading.show();
    try {
      items = (await getAgenda(toDateKey(inicio), toDateKey(fim), modo)).itens;
    } catch {
      items = [];
      loadError = true;
    } finally {
      loadingAgenda = false;
      loading.hide();
      render();
    }
  }

  function render(): void {
    if (loadingAgenda) {
      content.replaceChildren(createElement('section', { className: 'agenda-state loading-state', textContent: 'Carregando agenda...' }));
      return;
    }
    if (loadError) {
      const state = createElement('section', { className: 'agenda-state empty-state' });
      state.append(createIcon('agenda', 'empty-state-icon'), createElement('strong', { textContent: 'Não foi possível carregar a agenda.' }), createElement('span', { textContent: 'Verifique sua conexão e tente novamente.' }));
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
      retry.addEventListener('click', () => void loadAgenda());
      state.appendChild(retry);
      content.replaceChildren(state);
      return;
    }
    content.replaceChildren(createToolbar(), modo === 'mes' ? createMonthView() : createListView());
  }

  function createToolbar(): HTMLElement {
    const toolbar = createElement('section', { className: 'agenda-toolbar' });
    const modes = createElement('div', { className: 'agenda-mode-switch' });
    MODOS.forEach(({ value, label }) => {
      const button = createElement('button', { className: value === modo ? 'active' : '', type: 'button', textContent: label });
      button.setAttribute('aria-pressed', String(value === modo));
      button.addEventListener('click', () => { if (value !== modo) { modo = value; void loadAgenda(); } });
      modes.appendChild(button);
    });
    const navigation = createElement('div', { className: 'agenda-month-nav' });
    const previous = createElement('button', { className: 'icon-button neutral', type: 'button', title: 'Período anterior', textContent: '‹' });
    previous.addEventListener('click', () => { referenceDate = moveReference(modo, referenceDate, -1); void loadAgenda(); });
    const todayButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Hoje' });
    todayButton.addEventListener('click', () => { referenceDate = today; selectedDate = toDateKey(today); void loadAgenda(); });
    const next = createElement('button', { className: 'icon-button neutral', type: 'button', title: 'Próximo período', textContent: '›' });
    next.addEventListener('click', () => { referenceDate = moveReference(modo, referenceDate, 1); void loadAgenda(); });
    navigation.append(previous, createElement('strong', { className: 'agenda-period-label', textContent: rangeLabel(modo, referenceDate) }), todayButton, next);
    toolbar.append(modes, navigation);
    return toolbar;
  }

  function createMonthView(): HTMLElement {
    const grouped = groupByDate(items);
    const calendar = createElement('section', { className: 'agenda-calendar' });
    calendar.append(createWeekdaysRow(), createMonthGrid(grouped));
    const layoutWrap = createElement('div', { className: 'agenda-layout' });
    layoutWrap.append(calendar, createItemsPanel(selectedDate, grouped.get(selectedDate) ?? []));
    return layoutWrap;
  }

  function createWeekdaysRow(): HTMLElement {
    const row = createElement('div', { className: 'agenda-weekdays' });
    DIAS_SEMANA.forEach((dia) => row.appendChild(createElement('span', { textContent: dia })));
    return row;
  }

  function createMonthGrid(grouped: Map<string, AgendaItem[]>): HTMLElement {
    const grid = createElement('div', { className: 'agenda-grid' });
    const year = referenceDate.getFullYear();
    const month = referenceDate.getMonth();
    const firstWeekday = new Date(year, month, 1).getDay();
    const totalDays = new Date(year, month + 1, 0).getDate();
    const todayKey = toDateKey(today);
    for (let index = 0; index < firstWeekday; index += 1) grid.appendChild(createElement('div', { className: 'agenda-day empty' }));
    for (let day = 1; day <= totalDays; day += 1) {
      const key = toDateKey(new Date(year, month, day));
      const dayItems = grouped.get(key) ?? [];
      const cell = createElement('button', { className: 'agenda-day', type: 'button' });
      if (key === todayKey) cell.classList.add('today');
      if (key === selectedDate) cell.classList.add('selected');
      cell.appendChild(createElement('strong', { textContent: String(day) }));
      if (dayItems.length > 0) {
        const dots = createElement('div', { className: 'agenda-day-dots' });
        dayItems.slice(0, 3).forEach((item) => dots.appendChild(createElement('span', { className: `agenda-dot tone-${prioridadeTone(item.prioridade)}` })));
        cell.append(dots, createElement('span', { className: 'agenda-day-count', textContent: String(dayItems.length) }));
      }
      cell.addEventListener('click', () => { selectedDate = key; render(); });
      grid.appendChild(cell);
    }
    return grid;
  }

  function createListView(): HTMLElement {
    const grouped = groupByDate(items);
    const panel = createElement('section', { className: 'agenda-list-panel' });
    const dates = [...grouped.keys()].sort();
    if (dates.length === 0) panel.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhuma pendência com prazo neste período.' }));
    else dates.forEach((date) => panel.appendChild(createItemsPanel(date, grouped.get(date) ?? [], true)));
    return panel;
  }

  function createItemsPanel(date: string, dayItems: AgendaItem[], compact = false): HTMLElement {
    const panel = createElement(compact ? 'section' : 'aside', { className: compact ? 'agenda-day-panel agenda-list-day' : 'agenda-day-panel' });
    panel.append(createElement('h3', { textContent: formatDateHeading(date) }), createElement('p', { className: 'agenda-day-subtitle', textContent: dayItems.length === 0 ? 'Nenhum prazo neste dia.' : `${dayItems.length} ${dayItems.length === 1 ? 'pendência' : 'pendências'} com prazo` }));
    if (dayItems.length > 0) {
      const list = createElement('div', { className: 'agenda-day-list' });
      dayItems.slice().sort((a, b) => a.prazo.localeCompare(b.prazo)).forEach((item) => list.appendChild(createItemRow(item)));
      panel.appendChild(list);
    }
    return panel;
  }

  function createItemRow(item: AgendaItem): HTMLElement {
    const row = createElement('a', { className: 'agenda-item-row' });
    row.href = `/pendencias?selecionada=${encodeURIComponent(String(item.id))}`;
    row.addEventListener('click', (event) => { event.preventDefault(); navigate(row.href); });
    const info = createElement('div', { className: 'agenda-item-info' });
    info.append(createElement('strong', { textContent: item.titulo }), createElement('span', { className: 'agenda-item-meta', textContent: itemContext(item) }));
    const badges = createElement('div', { className: 'agenda-item-badges' });
    badges.append(createElement('span', { className: 'status-badge', textContent: tipoLabel(item.tipo) }), createElement('span', { className: prioridadeTone(item.prioridade) === 'neutral' ? 'status-badge' : `status-badge tone-${prioridadeTone(item.prioridade)}`, textContent: prioridadeLabel(item.prioridade) }));
    row.append(createElement('time', { className: 'agenda-item-time', textContent: item.prazo.slice(11, 16) || '—' }), info, badges);
    return row;
  }
}

function groupByDate(items: AgendaItem[]): Map<string, AgendaItem[]> {
  const grouped = new Map<string, AgendaItem[]>();
  items.forEach((item) => { const key = item.prazo.slice(0, 10); if (key) grouped.set(key, [...(grouped.get(key) ?? []), item]); });
  return grouped;
}
function itemContext(item: AgendaItem): string {
  if (item.clienteId || item.ucId || item.usinaId || item.documentoId) return 'Vínculo disponível na Pendência';
  return 'Sem vínculo cadastrado';
}
function getRange(modo: AgendaModo, date: Date): { inicio: Date; fim: Date } {
  const current = startOfDay(date);
  if (modo === 'dia') return { inicio: current, fim: current };
  if (modo === 'semana') { const inicio = new Date(current); inicio.setDate(inicio.getDate() - inicio.getDay()); const fim = new Date(inicio); fim.setDate(fim.getDate() + 6); return { inicio, fim }; }
  return { inicio: new Date(current.getFullYear(), current.getMonth(), 1), fim: new Date(current.getFullYear(), current.getMonth() + 1, 0) };
}
function moveReference(modo: AgendaModo, date: Date, offset: number): Date { const next = new Date(date); if (modo === 'dia') next.setDate(next.getDate() + offset); else if (modo === 'semana') next.setDate(next.getDate() + offset * 7); else next.setMonth(next.getMonth() + offset); return next; }
function rangeLabel(modo: AgendaModo, date: Date): string { if (modo === 'mes') return `${MESES[date.getMonth()]} ${date.getFullYear()}`; const { inicio, fim } = getRange(modo, date); return modo === 'dia' ? formatDateHeading(toDateKey(inicio)) : `${inicio.toLocaleDateString('pt-BR')} — ${fim.toLocaleDateString('pt-BR')}`; }
function formatDateHeading(date: string): string { return new Date(`${date}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' }); }
function startOfDay(date: Date): Date { return new Date(date.getFullYear(), date.getMonth(), date.getDate()); }
function toDateKey(date: Date): string { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
function navigate(href: string): void { const url = new URL(href, window.location.origin); window.history.pushState({}, '', `${url.pathname}${url.search}`); window.dispatchEvent(new PopStateEvent('popstate')); }
