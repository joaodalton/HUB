import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { cancelAgendaEvento, createAgendaEvento, getAgenda, updateAgendaEvento, type AgendaItem, type AgendaModo } from '../services/agendaService';
import { CATEGORIAS_POR_TIPO, createPendencia, PRIORIDADES, prioridadeLabel, prioridadeTone, tipoLabel, type PendenciaPayload } from '../services/pendenciasService';

const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const DIAS_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
const MODOS: Array<{ value: AgendaModo; label: string }> = [{ value: 'dia', label: 'Dia' }, { value: 'semana', label: 'Semana' }, { value: 'mes', label: 'Mês' }];
type Composer = 'pendencia' | 'evento' | null;

export function createAgendaPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  const toast = useToast();
  const today = startOfDay(new Date());
  let modo: AgendaModo = 'mes';
  let referenceDate = today;
  let selectedDate = toDateKey(today);
  let items: AgendaItem[] = [];
  let loadingAgenda = true;
  let loadError = false;
  let composer: Composer = null;
  let editingEvent: AgendaItem | null = null;

  const layout = createBaseLayout({ content, eyebrow: 'Agenda', title: 'Eventos e prazos operacionais' });
  render();
  void loadAgenda();
  return layout;

  async function loadAgenda(): Promise<void> {
    const { inicio, fim } = getRange(modo, referenceDate);
    loadingAgenda = true; loadError = false; render(); loading.show();
    try { items = (await getAgenda(toDateKey(inicio), toDateKey(fim), modo)).itens; }
    catch { items = []; loadError = true; }
    finally { loadingAgenda = false; loading.hide(); render(); }
  }

  function render(): void {
    if (loadingAgenda) { content.replaceChildren(createElement('section', { className: 'agenda-state loading-state', textContent: 'Carregando agenda...' })); return; }
    if (loadError) {
      const state = createElement('section', { className: 'agenda-state empty-state' });
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
      retry.addEventListener('click', () => void loadAgenda());
      state.append(createIcon('agenda', 'empty-state-icon'), createElement('strong', { textContent: 'Não foi possível carregar a agenda.' }), createElement('span', { textContent: 'Verifique sua conexão e tente novamente.' }), retry);
      content.replaceChildren(state); return;
    }
    content.replaceChildren(createToolbar(), modo === 'mes' ? createMonthView() : createListView());
  }

  function createToolbar(): HTMLElement {
    const toolbar = createElement('section', { className: 'agenda-toolbar' });
    const modes = createElement('div', { className: 'agenda-mode-switch' });
    MODOS.forEach(({ value, label }) => {
      const button = createElement('button', { className: value === modo ? 'active' : '', type: 'button', textContent: label });
      button.setAttribute('aria-pressed', String(value === modo));
      button.addEventListener('click', () => { if (value !== modo) { modo = value; composer = null; editingEvent = null; void loadAgenda(); } });
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
    const actions = createElement('div', { className: 'agenda-create-actions' });
    const pendencia = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Nova pendência' });
    const evento = createElement('button', { type: 'button', textContent: 'Novo evento' });
    pendencia.addEventListener('click', () => showComposer('pendencia'));
    evento.addEventListener('click', () => showComposer('evento'));
    actions.append(pendencia, evento); toolbar.append(modes, navigation, actions); return toolbar;
  }

  function createMonthView(): HTMLElement {
    const grouped = groupByDate(items);
    const calendar = createElement('section', { className: 'agenda-calendar' });
    calendar.append(createWeekdaysRow(), createMonthGrid(grouped));
    const layoutWrap = createElement('div', { className: 'agenda-layout' });
    layoutWrap.append(calendar, createItemsPanel(selectedDate, grouped.get(selectedDate) ?? []));
    return layoutWrap;
  }

  function createWeekdaysRow(): HTMLElement { const row = createElement('div', { className: 'agenda-weekdays' }); DIAS_SEMANA.forEach((dia) => row.appendChild(createElement('span', { textContent: dia }))); return row; }

  function createMonthGrid(grouped: Map<string, AgendaItem[]>): HTMLElement {
    const grid = createElement('div', { className: 'agenda-grid' }); const year = referenceDate.getFullYear(); const month = referenceDate.getMonth();
    for (let index = 0; index < new Date(year, month, 1).getDay(); index += 1) grid.appendChild(createElement('div', { className: 'agenda-day empty' }));
    for (let day = 1; day <= new Date(year, month + 1, 0).getDate(); day += 1) {
      const key = toDateKey(new Date(year, month, day)); const dayItems = grouped.get(key) ?? [];
      const cell = createElement('button', { className: 'agenda-day', type: 'button' });
      if (key === toDateKey(today)) cell.classList.add('today'); if (key === selectedDate) cell.classList.add('selected'); cell.appendChild(createElement('strong', { textContent: String(day) }));
      if (dayItems.length) { const dots = createElement('div', { className: 'agenda-day-dots' }); dayItems.slice(0, 3).forEach((item) => dots.appendChild(createElement('span', { className: item.fonte === 'evento' ? 'agenda-dot event' : `agenda-dot tone-${prioridadeTone(item.prioridade)}` }))); cell.append(dots, createElement('span', { className: 'agenda-day-count', textContent: String(dayItems.length) })); }
      cell.addEventListener('click', () => { selectedDate = key; composer = null; editingEvent = null; render(); }); grid.appendChild(cell);
    }
    return grid;
  }

  function createListView(): HTMLElement {
    const grouped = groupByDate(items); const panel = createElement('section', { className: 'agenda-list-panel' }); const dates = [...grouped.keys()].sort();
    if (!dates.length) panel.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhum evento ou pendência neste período.' }));
    else dates.forEach((date) => panel.appendChild(createItemsPanel(date, grouped.get(date) ?? [], true)));
    return panel;
  }

  function createItemsPanel(date: string, dayItems: AgendaItem[], compact = false): HTMLElement {
    const panel = createElement('section', { className: compact ? 'agenda-day-panel agenda-list-day' : 'agenda-day-panel' });
    const noun = dayItems.length === 1 ? 'item' : 'itens';
    panel.append(createElement('h3', { textContent: formatDateHeading(date) }), createElement('p', { className: 'agenda-day-subtitle', textContent: dayItems.length ? `${dayItems.length} ${noun} na agenda` : 'Nenhum item neste dia.' }));
    if (!compact && composer) panel.appendChild(createComposer(date));
    if (dayItems.length) { const list = createElement('div', { className: 'agenda-day-list' }); dayItems.slice().sort((a, b) => a.prazo.localeCompare(b.prazo)).forEach((item) => list.appendChild(createItemRow(item))); panel.appendChild(list); }
    return panel;
  }

  function createComposer(date: string): HTMLElement {
    const form = createElement('form', { className: 'agenda-composer' }); const isEvent = composer === 'evento';
    const title = inputField('Título', editingEvent?.titulo ?? '', true); const category = inputField('Categoria', editingEvent?.categoria ?? (isEvent ? 'Operacional' : CATEGORIAS_POR_TIPO.pendencia[0]), true);
    const start = inputField(isEvent ? 'Início' : 'Prazo', editingEvent?.prazo ? toLocalInput(editingEvent.prazo) : `${date}T09:00`, true, 'datetime-local');
    const description = textareaField('Descrição', editingEvent?.descricao ?? '');
    const priority = createElement('select') as HTMLSelectElement; PRIORIDADES.forEach((value) => { const option = createElement('option', { textContent: prioridadeLabel(value) }) as HTMLOptionElement; option.value = value; option.selected = value === 'media'; priority.appendChild(option); });
    const end = isEvent ? inputField('Fim (opcional)', editingEvent?.fim ? toLocalInput(editingEvent.fim) : '', false, 'datetime-local') : null;
    const actions = createElement('div', { className: 'form-actions' }); const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' }); const save = createElement('button', { type: 'submit', textContent: editingEvent ? 'Salvar evento' : isEvent ? 'Criar evento' : 'Criar pendência' });
    cancel.addEventListener('click', () => { composer = null; editingEvent = null; render(); }); actions.append(cancel, save);
    form.append(createElement('h4', { textContent: editingEvent ? 'Editar evento' : isEvent ? 'Novo evento' : 'Nova pendência' }), title.field, category.field, start.field, ...(end ? [end.field] : []), ...(isEvent ? [] : [selectField('Prioridade', priority)]), description.field, actions);
    form.addEventListener('submit', (event) => void saveComposer(event, { title: title.input, category: category.input, start: start.input, end: end?.input, description: description.input, priority }));
    return form;
  }

  function showComposer(kind: Exclude<Composer, null>): void {
    composer = kind; editingEvent = null;
    if (modo !== 'mes') { modo = 'mes'; referenceDate = new Date(`${selectedDate}T12:00:00`); void loadAgenda(); }
    else render();
  }

  async function saveComposer(event: Event, fields: { title: HTMLInputElement; category: HTMLInputElement; start: HTMLInputElement; end?: HTMLInputElement; description: HTMLTextAreaElement; priority: HTMLSelectElement }): Promise<void> {
    event.preventDefault(); if (!fields.title.value.trim() || !fields.category.value.trim() || !fields.start.value) { fields.title.reportValidity(); return; }
    loading.show();
    try {
      if (composer === 'pendencia') {
        const payload: PendenciaPayload = { titulo: fields.title.value.trim(), categoria: fields.category.value.trim(), descricao: fields.description.value.trim(), clienteId: null, ucId: null, usinaId: null, prazo: fields.start.value, prioridade: fields.priority.value as PendenciaPayload['prioridade'] };
        await createPendencia(payload); toast.success('Pendência criada e adicionada à agenda.');
      } else {
        const payload = { titulo: fields.title.value.trim(), categoria: fields.category.value.trim(), descricao: fields.description.value.trim(), inicio: fields.start.value, fim: fields.end?.value || null };
        if (editingEvent?.eventoId) { await updateAgendaEvento(editingEvent.eventoId, payload); toast.success('Evento atualizado.'); }
        else { await createAgendaEvento(payload); toast.success('Evento criado.'); }
      }
      composer = null; editingEvent = null; await loadAgenda();
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível salvar o item.'); }
    finally { loading.hide(); }
  }

  function createItemRow(item: AgendaItem): HTMLElement {
    const row = createElement(item.fonte === 'pendencia' ? 'a' : 'article', { className: 'agenda-item-row' });
    if (row instanceof HTMLAnchorElement && item.pendenciaId) { row.href = `/pendencias?selecionada=${encodeURIComponent(String(item.pendenciaId))}`; row.addEventListener('click', (event) => { event.preventDefault(); navigate(row.href); }); }
    const info = createElement('div', { className: 'agenda-item-info' }); info.append(createElement('strong', { textContent: item.titulo }), createElement('span', { className: 'agenda-item-meta', textContent: item.fonte === 'pendencia' ? `${itemContext(item)} · editar em Pendências` : item.descricao || 'Evento operacional' }));
    const badges = createElement('div', { className: 'agenda-item-badges' }); badges.append(createElement('span', { className: 'status-badge', textContent: item.fonte === 'evento' ? 'Evento' : tipoLabel(item.tipo as 'pendencia') }), createElement('span', { className: item.fonte === 'evento' ? 'status-badge tone-info' : prioridadeTone(item.prioridade) === 'neutral' ? 'status-badge' : `status-badge tone-${prioridadeTone(item.prioridade)}`, textContent: item.fonte === 'evento' ? item.categoria : prioridadeLabel(item.prioridade) }));
    row.append(createElement('time', { className: 'agenda-item-time', textContent: item.prazo.slice(11, 16) || '—' }), info, badges);
    if (item.fonte === 'evento' && item.eventoId) { const actions = createElement('div', { className: 'agenda-item-actions' }); const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Editar' }); const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: 'Cancelar' }); edit.addEventListener('click', () => { composer = 'evento'; editingEvent = item; selectedDate = item.prazo.slice(0, 10); render(); }); remove.addEventListener('click', () => void cancelEvent(item.eventoId as number)); actions.append(edit, remove); row.appendChild(actions); }
    return row;
  }

  async function cancelEvent(eventId: number): Promise<void> { if (!window.confirm('Cancelar este evento?')) return; loading.show(); try { await cancelAgendaEvento(eventId); toast.success('Evento cancelado.'); await loadAgenda(); } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível cancelar o evento.'); } finally { loading.hide(); } }
}

function inputField(label: string, value: string, required: boolean, type = 'text'): { field: HTMLLabelElement; input: HTMLInputElement } { const field = createElement('label', { className: 'form-field' }); const input = createElement('input') as HTMLInputElement; input.type = type; input.value = value; input.required = required; field.append(createElement('span', { textContent: label }), input); return { field, input }; }
function textareaField(label: string, value: string): { field: HTMLLabelElement; input: HTMLTextAreaElement } { const field = createElement('label', { className: 'form-field form-field-wide' }); const input = createElement('textarea') as HTMLTextAreaElement; input.rows = 3; input.value = value; field.append(createElement('span', { textContent: label }), input); return { field, input }; }
function selectField(label: string, select: HTMLSelectElement): HTMLLabelElement { const field = createElement('label', { className: 'form-field' }); field.append(createElement('span', { textContent: label }), select); return field; }
function groupByDate(items: AgendaItem[]): Map<string, AgendaItem[]> { const grouped = new Map<string, AgendaItem[]>(); items.forEach((item) => { const key = item.prazo.slice(0, 10); if (key) grouped.set(key, [...(grouped.get(key) ?? []), item]); }); return grouped; }
function itemContext(item: AgendaItem): string { return item.clienteId || item.ucId || item.usinaId || item.documentoId ? 'Vínculo disponível na Pendência' : 'Sem vínculo cadastrado'; }
function getRange(modo: AgendaModo, date: Date): { inicio: Date; fim: Date } { const current = startOfDay(date); if (modo === 'dia') return { inicio: current, fim: current }; if (modo === 'semana') { const inicio = new Date(current); inicio.setDate(inicio.getDate() - inicio.getDay()); const fim = new Date(inicio); fim.setDate(fim.getDate() + 6); return { inicio, fim }; } return { inicio: new Date(current.getFullYear(), current.getMonth(), 1), fim: new Date(current.getFullYear(), current.getMonth() + 1, 0) }; }
function moveReference(modo: AgendaModo, date: Date, offset: number): Date { const next = new Date(date); if (modo === 'dia') next.setDate(next.getDate() + offset); else if (modo === 'semana') next.setDate(next.getDate() + offset * 7); else next.setMonth(next.getMonth() + offset); return next; }
function rangeLabel(modo: AgendaModo, date: Date): string { if (modo === 'mes') return `${MESES[date.getMonth()]} ${date.getFullYear()}`; const { inicio, fim } = getRange(modo, date); return modo === 'dia' ? formatDateHeading(toDateKey(inicio)) : `${inicio.toLocaleDateString('pt-BR')} — ${fim.toLocaleDateString('pt-BR')}`; }
function formatDateHeading(date: string): string { return new Date(`${date}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' }); }
function toLocalInput(value: string): string { return value.slice(0, 16); }
function startOfDay(date: Date): Date { return new Date(date.getFullYear(), date.getMonth(), date.getDate()); }
function toDateKey(date: Date): string { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
function navigate(href: string): void { const url = new URL(href, window.location.origin); window.history.pushState({}, '', `${url.pathname}${url.search}`); window.dispatchEvent(new PopStateEvent('popstate')); }
