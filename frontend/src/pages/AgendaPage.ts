import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  getPendencias,
  prioridadeLabel,
  prioridadeTone,
  tipoLabel,
  vinculacaoLabel,
  type PendenciaRow
} from '../services/pendenciasService';

const MESES = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
];
const DIAS_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

export function createAgendaPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  const today = new Date();
  let viewYear = today.getFullYear();
  let viewMonth = today.getMonth(); // 0-11
  let selectedDate = toDateKey(today);
  let pendencias: PendenciaRow[] = [];
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Agenda',
    title: 'Prazos e pendências organizados por dia'
  });

  loadAll();

  return layout;

  async function loadAll(): Promise<void> {
    loading.show();
    try {
      pendencias = await getPendencias();
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Não foi possível carregar a agenda. Verifique se o backend está rodando.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  // Agrupa por prazo (YYYY-MM-DD) -- so pendencias com prazo definido entram
  // na agenda; sem prazo, elas continuam existindo normal em /pendencias,
  // so nao aparecem aqui (nao ha "dia" pra por elas).
  function groupByDate(): Map<string, PendenciaRow[]> {
    const map = new Map<string, PendenciaRow[]>();

    pendencias.forEach((item) => {
      if (!item.prazo) return;
      const key = item.prazo.slice(0, 10);
      const list = map.get(key) ?? [];
      list.push(item);
      map.set(key, list);
    });

    return map;
  }

  function renderContent(): void {
    const grouped = groupByDate();

    const calendarPanel = createElement('section', { className: 'agenda-calendar' });
    calendarPanel.append(createMonthHeader(), createWeekdaysRow(), createMonthGrid(grouped));

    const dayPanel = createDayPanel(grouped.get(selectedDate) ?? []);

    const layoutWrap = createElement('div', { className: 'agenda-layout' });
    layoutWrap.append(calendarPanel, dayPanel);

    content.replaceChildren(layoutWrap);
  }

  function createMonthHeader(): HTMLElement {
    const header = createElement('div', { className: 'agenda-month-header' });
    const label = createElement('h2', { textContent: `${MESES[viewMonth]} ${viewYear}` });

    const nav = createElement('div', { className: 'agenda-month-nav' });
    const prevButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    prevButton.appendChild(createIcon('more')); // placeholder visual, trocado por seta abaixo
    prevButton.innerHTML = '';
    prevButton.textContent = '‹';
    prevButton.title = 'Mês anterior';

    const todayButton = createElement('button', { className: 'secondary-button', textContent: 'Hoje', type: 'button' });

    const nextButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    nextButton.textContent = '›';
    nextButton.title = 'Próximo mês';

    prevButton.addEventListener('click', () => {
      viewMonth -= 1;
      if (viewMonth < 0) {
        viewMonth = 11;
        viewYear -= 1;
      }
      renderContent();
    });

    nextButton.addEventListener('click', () => {
      viewMonth += 1;
      if (viewMonth > 11) {
        viewMonth = 0;
        viewYear += 1;
      }
      renderContent();
    });

    todayButton.addEventListener('click', () => {
      const now = new Date();
      viewYear = now.getFullYear();
      viewMonth = now.getMonth();
      selectedDate = toDateKey(now);
      renderContent();
    });

    nav.append(prevButton, todayButton, nextButton);
    header.append(label, nav);
    return header;
  }

  function createWeekdaysRow(): HTMLElement {
    const row = createElement('div', { className: 'agenda-weekdays' });
    DIAS_SEMANA.forEach((dia) => row.appendChild(createElement('span', { textContent: dia })));
    return row;
  }

  function createMonthGrid(grouped: Map<string, PendenciaRow[]>): HTMLElement {
    const grid = createElement('div', { className: 'agenda-grid' });

    const firstWeekday = new Date(viewYear, viewMonth, 1).getDay();
    const totalDays = new Date(viewYear, viewMonth + 1, 0).getDate();
    const todayKey = toDateKey(new Date());

    for (let i = 0; i < firstWeekday; i += 1) {
      grid.appendChild(createElement('div', { className: 'agenda-day empty' }));
    }

    for (let day = 1; day <= totalDays; day += 1) {
      const date = new Date(viewYear, viewMonth, day);
      const key = toDateKey(date);
      const items = grouped.get(key) ?? [];

      const cell = createElement('button', { className: 'agenda-day', type: 'button' });
      if (key === todayKey) cell.classList.add('today');
      if (key === selectedDate) cell.classList.add('selected');

      const number = createElement('strong', { textContent: String(day) });
      cell.appendChild(number);

      if (items.length > 0) {
        const dots = createElement('div', { className: 'agenda-day-dots' });
        // No maximo 3 bolinhas visiveis + contador, pra nao estourar a
        // celula quando tiver muita coisa no mesmo dia.
        items.slice(0, 3).forEach((item) => {
          dots.appendChild(createElement('span', { className: `agenda-dot tone-${prioridadeTone(item.prioridade)}` }));
        });
        cell.appendChild(dots);

        if (items.length > 0) {
          cell.appendChild(createElement('span', { className: 'agenda-day-count', textContent: String(items.length) }));
        }
      }

      cell.addEventListener('click', () => {
        selectedDate = key;
        renderContent();
      });

      grid.appendChild(cell);
    }

    return grid;
  }

  function createDayPanel(items: PendenciaRow[]): HTMLElement {
    const panel = createElement('aside', { className: 'agenda-day-panel' });
    const [year, month, day] = selectedDate.split('-');
    const heading = createElement('h3', { textContent: `${day}/${month}/${year}` });
    const subtitle = createElement('p', {
      className: 'agenda-day-subtitle',
      textContent: items.length === 0 ? 'Nenhum prazo neste dia.' : `${items.length} ${items.length === 1 ? 'item' : 'itens'} com prazo`
    });

    panel.append(heading, subtitle);

    if (loadError) {
      panel.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Não foi possível carregar a agenda.' }));
      return panel;
    }

    if (items.length === 0) {
      return panel;
    }

    const list = createElement('div', { className: 'agenda-day-list' });

    items
      .sort((a, b) => (a.prazo ?? '').localeCompare(b.prazo ?? ''))
      .forEach((item) => {
        const row = createElement('a', { className: 'agenda-item-row' });
        row.href = '/pendencias';
        row.addEventListener('click', (event) => {
          event.preventDefault();
          window.history.pushState({}, '', '/pendencias');
          window.dispatchEvent(new PopStateEvent('popstate'));
        });

        const time = createElement('span', {
          className: 'agenda-item-time',
          textContent: item.prazo ? item.prazo.slice(11, 16) || '--:--' : '--:--'
        });

        const info = createElement('div', { className: 'agenda-item-info' });
        info.append(
          createElement('strong', { textContent: item.titulo }),
          createElement('span', { className: 'agenda-item-meta', textContent: vinculacaoLabel(item) })
        );

        const badges = createElement('div', { className: 'agenda-item-badges' });
        badges.append(
          createElement('span', { className: 'status-badge', textContent: tipoLabel(item.tipo) }),
          createElement('span', {
            className: `status-badge tone-${prioridadeTone(item.prioridade)}`,
            textContent: prioridadeLabel(item.prioridade)
          })
        );

        row.append(time, info, badges);
        list.appendChild(row);
      });

    panel.appendChild(list);
    return panel;
  }
}

function toDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}