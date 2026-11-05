import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { cancelAgendaEvento, createAgendaEvento, getAgenda, updateAgendaEvento, type AgendaItem, type AgendaModo } from '../services/agendaService';
import { CATEGORIAS_POR_TIPO, createPendencia, PRIORIDADES, prioridadeLabel, prioridadeTone, tipoLabel, type PendenciaPayload } from '../services/pendenciasService';
import { getLanguage, t, type Language } from '../services/i18nService';

type Composer = 'pendencia' | 'evento' | null;

function localeTag(): string {
  const map: Record<Language, string> = { pt: 'pt-BR', en: 'en-US', fr: 'fr-FR' };
  return map[getLanguage()];
}

function weekdayLabels(): string[] {
  // Ancora numa semana que comeca num domingo (7/jan/2024) so pra gerar os nomes curtos via Intl.
  return [0, 1, 2, 3, 4, 5, 6].map((offset) => new Date(2024, 0, 7 + offset).toLocaleDateString(localeTag(), { weekday: 'short' }));
}

function modos(): Array<{ value: AgendaModo; label: string }> {
  return [
    { value: 'dia', label: t('agenda.page.modeDia') },
    { value: 'semana', label: t('agenda.page.modeSemana') },
    { value: 'mes', label: t('agenda.page.modeMes') }
  ];
}

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

  const layout = createBaseLayout({ content, eyebrow: t('agenda.page.eyebrow'), title: t('agenda.page.title') });
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
    if (loadingAgenda) { content.replaceChildren(createElement('section', { className: 'agenda-state loading-state', textContent: t('agenda.page.loading') })); return; }
    if (loadError) {
      const state = createElement('section', { className: 'agenda-state empty-state' });
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.retry') });
      retry.addEventListener('click', () => void loadAgenda());
      state.append(createIcon('agenda', 'empty-state-icon'), createElement('strong', { textContent: t('agenda.page.loadErrorTitle') }), createElement('span', { textContent: t('agenda.page.loadErrorDesc') }), retry);
      content.replaceChildren(state); return;
    }
    content.replaceChildren(createToolbar(), modo === 'mes' ? createMonthView() : createListView());
  }

  function createToolbar(): HTMLElement {
    const toolbar = createElement('section', { className: 'agenda-toolbar' });
    const modes = createElement('div', { className: 'agenda-mode-switch' });
    modos().forEach(({ value, label }) => {
      const button = createElement('button', { className: value === modo ? 'active' : '', type: 'button', textContent: label });
      button.setAttribute('aria-pressed', String(value === modo));
      button.addEventListener('click', () => { if (value !== modo) { modo = value; composer = null; editingEvent = null; void loadAgenda(); } });
      modes.appendChild(button);
    });
    const navigation = createElement('div', { className: 'agenda-month-nav' });
    const previous = createElement('button', { className: 'icon-button neutral', type: 'button', title: t('agenda.page.navPrevious'), textContent: '‹' });
    previous.addEventListener('click', () => { referenceDate = moveReference(modo, referenceDate, -1); void loadAgenda(); });
    const todayButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('agenda.page.navToday') });
    todayButton.addEventListener('click', () => { referenceDate = today; selectedDate = toDateKey(today); void loadAgenda(); });
    const next = createElement('button', { className: 'icon-button neutral', type: 'button', title: t('agenda.page.navNext'), textContent: '›' });
    next.addEventListener('click', () => { referenceDate = moveReference(modo, referenceDate, 1); void loadAgenda(); });
    navigation.append(previous, createElement('strong', { className: 'agenda-period-label', textContent: rangeLabel(modo, referenceDate) }), todayButton, next);
    const actions = createElement('div', { className: 'agenda-create-actions' });
    const pendencia = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('agenda.page.actionNovaPendencia') });
    const evento = createElement('button', { type: 'button', textContent: t('agenda.page.actionNovoEvento') });
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

  function createWeekdaysRow(): HTMLElement { const row = createElement('div', { className: 'agenda-weekdays' }); weekdayLabels().forEach((dia) => row.appendChild(createElement('span', { textContent: dia }))); return row; }

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
    if (!dates.length) panel.appendChild(createElement('p', { className: 'empty-state small', textContent: t('agenda.page.nenhumItemPeriodo') }));
    else dates.forEach((date) => panel.appendChild(createItemsPanel(date, grouped.get(date) ?? [], true)));
    return panel;
  }

  function createItemsPanel(date: string, dayItems: AgendaItem[], compact = false): HTMLElement {
    const panel = createElement('section', { className: compact ? 'agenda-day-panel agenda-list-day' : 'agenda-day-panel' });
    const noun = dayItems.length === 1 ? t('agenda.page.itemSingular') : t('agenda.page.itemPlural');
    panel.append(createElement('h3', { textContent: formatDateHeading(date) }), createElement('p', { className: 'agenda-day-subtitle', textContent: dayItems.length ? `${dayItems.length} ${noun} ${t('agenda.page.naAgenda')}` : t('agenda.page.nenhumItemDia') }));
    if (!compact && composer) panel.appendChild(createComposer(date));
    if (dayItems.length) { const list = createElement('div', { className: 'agenda-day-list' }); dayItems.slice().sort((a, b) => a.prazo.localeCompare(b.prazo)).forEach((item) => list.appendChild(createItemRow(item))); panel.appendChild(list); }
    return panel;
  }

  function createComposer(date: string): HTMLElement {
    const form = createElement('form', { className: 'agenda-composer' }); const isEvent = composer === 'evento';
    const title = inputField(t('agenda.page.fieldTitulo'), editingEvent?.titulo ?? '', true); const category = inputField(t('agenda.page.fieldCategoria'), editingEvent?.categoria ?? (isEvent ? t('agenda.page.defaultCategoriaEvento') : CATEGORIAS_POR_TIPO.pendencia[0]), true);
    const start = inputField(isEvent ? t('agenda.page.fieldInicio') : t('agenda.page.fieldPrazo'), editingEvent?.prazo ? toLocalInput(editingEvent.prazo) : `${date}T09:00`, true, 'datetime-local');
    const description = textareaField(t('agenda.page.fieldDescricao'), editingEvent?.descricao ?? '');
    const priority = createElement('select') as HTMLSelectElement; PRIORIDADES.forEach((value) => { const option = createElement('option', { textContent: prioridadeLabel(value) }) as HTMLOptionElement; option.value = value; option.selected = value === 'media'; priority.appendChild(option); });
    const end = isEvent ? inputField(t('agenda.page.fieldFim'), editingEvent?.fim ? toLocalInput(editingEvent.fim) : '', false, 'datetime-local') : null;
    const actions = createElement('div', { className: 'form-actions' }); const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.cancel') }); const save = createElement('button', { type: 'submit', textContent: editingEvent ? t('agenda.page.saveEvento') : isEvent ? t('agenda.page.createEvento') : t('agenda.page.createPendencia') });
    cancel.addEventListener('click', () => { composer = null; editingEvent = null; render(); }); actions.append(cancel, save);
    form.append(createElement('h4', { textContent: editingEvent ? t('agenda.page.headingEditEvento') : isEvent ? t('agenda.page.headingNewEvento') : t('agenda.page.headingNewPendencia') }), title.field, category.field, start.field, ...(end ? [end.field] : []), ...(isEvent ? [] : [selectField(t('agenda.page.fieldPrioridade'), priority)]), description.field, actions);
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
        await createPendencia(payload); toast.success(t('agenda.page.toastPendenciaCriada'));
      } else {
        const payload = { titulo: fields.title.value.trim(), categoria: fields.category.value.trim(), descricao: fields.description.value.trim(), inicio: fields.start.value, fim: fields.end?.value || null };
        if (editingEvent?.eventoId) { await updateAgendaEvento(editingEvent.eventoId, payload); toast.success(t('agenda.page.toastEventoAtualizado')); }
        else { await createAgendaEvento(payload); toast.success(t('agenda.page.toastEventoCriado')); }
      }
      composer = null; editingEvent = null; await loadAgenda();
    } catch (error) { toast.error(error instanceof Error ? error.message : t('agenda.page.errorSalvarItem')); }
    finally { loading.hide(); }
  }

  function createItemRow(item: AgendaItem): HTMLElement {
    const row = createElement(item.fonte === 'pendencia' ? 'a' : 'article', { className: 'agenda-item-row' });
    if (row instanceof HTMLAnchorElement && item.pendenciaId) { row.href = `/pendencias?selecionada=${encodeURIComponent(String(item.pendenciaId))}`; row.addEventListener('click', (event) => { event.preventDefault(); navigate(row.href); }); }
    const info = createElement('div', { className: 'agenda-item-info' }); info.append(createElement('strong', { textContent: item.titulo }), createElement('span', { className: 'agenda-item-meta', textContent: item.fonte === 'pendencia' ? `${itemContext(item)} · ${t('agenda.page.editarEmPendencias')}` : item.descricao || t('agenda.page.eventoOperacional') }));
    const badges = createElement('div', { className: 'agenda-item-badges' }); badges.append(createElement('span', { className: 'status-badge', textContent: item.fonte === 'evento' ? t('agenda.page.badgeEvento') : tipoLabel(item.tipo as 'pendencia') }), createElement('span', { className: item.fonte === 'evento' ? 'status-badge tone-info' : prioridadeTone(item.prioridade) === 'neutral' ? 'status-badge' : `status-badge tone-${prioridadeTone(item.prioridade)}`, textContent: item.fonte === 'evento' ? item.categoria : prioridadeLabel(item.prioridade) }));
    row.append(createElement('time', { className: 'agenda-item-time', textContent: item.prazo.slice(11, 16) || '—' }), info, badges);
    if (item.fonte === 'evento' && item.eventoId) { const actions = createElement('div', { className: 'agenda-item-actions' }); const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('agenda.page.actionEditar') }); const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: t('common.cancel') }); edit.addEventListener('click', () => { composer = 'evento'; editingEvent = item; selectedDate = item.prazo.slice(0, 10); render(); }); remove.addEventListener('click', () => void cancelEvent(item.eventoId as number)); actions.append(edit, remove); row.appendChild(actions); }
    return row;
  }

  async function cancelEvent(eventId: number): Promise<void> { if (!window.confirm(t('agenda.page.confirmCancelEvento'))) return; loading.show(); try { await cancelAgendaEvento(eventId); toast.success(t('agenda.page.toastEventoCancelado')); await loadAgenda(); } catch (error) { toast.error(error instanceof Error ? error.message : t('agenda.page.errorCancelarEvento')); } finally { loading.hide(); } }
}

function inputField(label: string, value: string, required: boolean, type = 'text'): { field: HTMLLabelElement; input: HTMLInputElement } { const field = createElement('label', { className: 'form-field' }); const input = createElement('input') as HTMLInputElement; input.type = type; input.value = value; input.required = required; field.append(createElement('span', { textContent: label }), input); return { field, input }; }
function textareaField(label: string, value: string): { field: HTMLLabelElement; input: HTMLTextAreaElement } { const field = createElement('label', { className: 'form-field form-field-wide' }); const input = createElement('textarea') as HTMLTextAreaElement; input.rows = 3; input.value = value; field.append(createElement('span', { textContent: label }), input); return { field, input }; }
function selectField(label: string, select: HTMLSelectElement): HTMLLabelElement { const field = createElement('label', { className: 'form-field' }); field.append(createElement('span', { textContent: label }), select); return field; }
function groupByDate(items: AgendaItem[]): Map<string, AgendaItem[]> { const grouped = new Map<string, AgendaItem[]>(); items.forEach((item) => { const key = item.prazo.slice(0, 10); if (key) grouped.set(key, [...(grouped.get(key) ?? []), item]); }); return grouped; }
function itemContext(item: AgendaItem): string { return item.clienteId || item.ucId || item.usinaId || item.documentoId ? t('agenda.page.contextVinculo') : t('agenda.page.contextSemVinculo'); }
function getRange(modo: AgendaModo, date: Date): { inicio: Date; fim: Date } { const current = startOfDay(date); if (modo === 'dia') return { inicio: current, fim: current }; if (modo === 'semana') { const inicio = new Date(current); inicio.setDate(inicio.getDate() - inicio.getDay()); const fim = new Date(inicio); fim.setDate(fim.getDate() + 6); return { inicio, fim }; } return { inicio: new Date(current.getFullYear(), current.getMonth(), 1), fim: new Date(current.getFullYear(), current.getMonth() + 1, 0) }; }
function moveReference(modo: AgendaModo, date: Date, offset: number): Date { const next = new Date(date); if (modo === 'dia') next.setDate(next.getDate() + offset); else if (modo === 'semana') next.setDate(next.getDate() + offset * 7); else next.setMonth(next.getMonth() + offset); return next; }
function rangeLabel(modo: AgendaModo, date: Date): string { if (modo === 'mes') return date.toLocaleDateString(localeTag(), { month: 'long', year: 'numeric' }); const { inicio, fim } = getRange(modo, date); return modo === 'dia' ? formatDateHeading(toDateKey(inicio)) : `${inicio.toLocaleDateString(localeTag())} — ${fim.toLocaleDateString(localeTag())}`; }
function formatDateHeading(date: string): string { return new Date(`${date}T12:00:00`).toLocaleDateString(localeTag(), { weekday: 'long', day: '2-digit', month: 'long' }); }
function toLocalInput(value: string): string { return value.slice(0, 16); }
function startOfDay(date: Date): Date { return new Date(date.getFullYear(), date.getMonth(), date.getDate()); }
function toDateKey(date: Date): string { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
function navigate(href: string): void { const url = new URL(href, window.location.origin); window.history.pushState({}, '', `${url.pathname}${url.search}`); window.dispatchEvent(new PopStateEvent('popstate')); }
