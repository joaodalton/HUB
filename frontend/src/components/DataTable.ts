import { createElement, statusTone } from '../dom';
import { createIcon } from './Icon';
import { createModalShell } from './Modal';
import { createStatusBadge } from './StatusBadge';
import { createTableSkeleton, createUiState, type UiStateKind } from './UiState';

export type TableColumn<T> = {
  key: string;
  label: string;
  align?: 'left' | 'right';
  headerRender?: () => HTMLElement;
  // Opcional: quando presente, ignora item[key] e desenha a celula do jeito
  // que a pagina quiser (ex.: id+nome numa celula so, botao de acao). key
  // continua obrigatorio (serve so de identificador da coluna nesse caso).
  render?: (row: T) => HTMLElement | string;
  // Sempre visivel, nao aparece no modal de escolha de colunas.
  locked?: boolean;
  // Colunas "extras" podem nascer ocultas (default true).
  defaultVisible?: boolean;
};

type DataTableOptions<T> = {
  title: string;
  eyebrow: string;
  rows: T[];
  columns: Array<TableColumn<T>>;
  emptyMessage: string;
  state?: 'ready' | 'loading' | UiStateKind;
  stateTitle?: string;
  emptyAction?: { label: string; onClick: () => void };
  errorAction?: { label: string; onClick: () => void };
  onRowClick?: (row: T) => void;
  // Chave de persistencia das colunas no localStorage; default = slug(title).
  storageKey?: string;
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function isTogglable<T>(column: TableColumn<T>): boolean {
  return !column.locked && Boolean(column.label);
}

type ColumnPrefs = { visible: Record<string, boolean>; order: string[] };

function loadColumnPrefs(storageKey: string): ColumnPrefs {
  try {
    const raw = window.localStorage.getItem(`hub.datatable.columns.${storageKey}`);
    const parsed = raw ? JSON.parse(raw) : null;
    return {
      visible: parsed?.visible ?? {},
      order: Array.isArray(parsed?.order) ? parsed.order : []
    };
  } catch {
    return { visible: {}, order: [] };
  }
}

function saveColumnPrefs(storageKey: string, prefs: ColumnPrefs): void {
  try {
    window.localStorage.setItem(`hub.datatable.columns.${storageKey}`, JSON.stringify(prefs));
  } catch {
    // localStorage indisponivel (ex.: navegacao privada) -- segue so em memoria.
  }
}

// `saved` filtrado pelas keys que existem hoje, depois completado com as que
// faltarem (coluna nova adicionada depois) no fim, na ordem de definicao.
function resolveOrderKeys(keys: string[], saved: string[]): string[] {
  const existing = new Set(keys);
  const ordered = saved.filter((key) => existing.has(key));
  keys.forEach((key) => { if (!ordered.includes(key)) ordered.push(key); });
  return ordered;
}

export function createDataTable<T extends Record<string, unknown>>({
  title,
  eyebrow,
  rows,
  columns,
  emptyMessage,
  state = 'ready',
  stateTitle,
  emptyAction,
  errorAction,
  onRowClick,
  storageKey
}: DataTableOptions<T>): HTMLElement {
  const panel = createElement('section', { className: 'data-panel data-panel-scroll' });
  const panelTitle = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrowElement = createElement('span', { className: 'eyebrow', textContent: eyebrow });
  const heading = createElement('h2', { textContent: title });
  const tableWrap = createElement('div', { className: 'table-wrap' });

  const resolvedStorageKey = storageKey ?? slugify(title);
  const firstColumn = columns[0];
  // Regra da primeira coluna tem prioridade: so conta como "coluna status"
  // fixa no fim se nao for ela mesma a primeira coluna.
  const statusColumn = columns.find((column) => column.key === 'status' && column.key !== firstColumn?.key);
  const togglableColumns = columns.filter(isTogglable);
  // Primeira coluna e a coluna status nunca entram no reordenamento, so no
  // toggle de visibilidade.
  const reorderableColumns = togglableColumns.filter((column) => column.key !== firstColumn?.key && column.key !== statusColumn?.key);
  let columnPrefs = loadColumnPrefs(resolvedStorageKey);

  // Primeira coluna e coluna status sao permanentemente visiveis, sem
  // controle do usuario -- nunca consultam prefs.visible.
  const isColumnVisible = (column: TableColumn<T>): boolean =>
    column.key === firstColumn?.key || column.key === statusColumn?.key
      ? true
      : !isTogglable(column) || (columnPrefs.visible[column.key] ?? (column.defaultVisible ?? true));

  // Primeira coluna fixa no inicio, coluna status (se existir) sempre
  // ultima -- aplicado ANTES do filtro de visibilidade em paintTable(), e
  // como status nunca pode ser ocultada ela sobra como ultimo elemento
  // mesmo depois do filtro remover colunas ocultas no meio. As demais
  // mantem a posicao original quando nao forem reordenaveis (locked, sem
  // label) e seguem a ordem salva quando forem.
  function getOrderedColumns(): Array<TableColumn<T>> {
    if (columns.length === 0) return columns;
    const rest = columns.slice(1).filter((column) => column.key !== statusColumn?.key);
    const orderedKeys = resolveOrderKeys(reorderableColumns.map((column) => column.key), columnPrefs.order);
    const reorderableByKey = new Map(reorderableColumns.map((column) => [column.key, column]));
    let cursor = 0;
    const orderedRest = rest.map((column) => {
      if (!reorderableByKey.has(column.key)) return column;
      return reorderableByKey.get(orderedKeys[cursor++])!;
    });
    return statusColumn ? [firstColumn, ...orderedRest, statusColumn] : [firstColumn, ...orderedRest];
  }

  function paintTable(): void {
    const visibleColumns = getOrderedColumns().filter(isColumnVisible);
    const table = createElement('table', { className: 'data-table' });
    const thead = createElement('thead');
    const headerRow = createElement('tr');
    let body: HTMLElement = createElement('tbody');

    visibleColumns.forEach((column) => {
      const th = createElement('th');
      if (column.headerRender) th.appendChild(column.headerRender());
      else th.textContent = column.label;
      if (column.align === 'right') th.classList.add('align-right');
      headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);

    if (state === 'loading') {
      body = createTableSkeleton(visibleColumns.length);
    } else if (rows.length === 0) {
      const row = createElement('tr');
      const cell = createElement('td', { className: 'empty-table' });
      cell.colSpan = visibleColumns.length;
      const kind = state === 'ready' ? 'empty' : state;
      cell.appendChild(createUiState({
        kind,
        title: stateTitle ?? emptyMessage,
        action: state === 'filtered' ? emptyAction : state === 'error' ? errorAction : undefined,
        compact: true
      }));
      row.appendChild(cell);
      body.appendChild(row);
    } else {
      rows.forEach((item) => {
        const row = createElement('tr');
        if (onRowClick) {
          row.classList.add('clickable-row');
          row.tabIndex = 0;
          row.setAttribute('role', 'button');
          row.addEventListener('click', () => onRowClick(item));
          row.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            onRowClick(item);
          });
        }

        visibleColumns.forEach((column) => {
          const cell = createElement('td');
          if (column.align === 'right') cell.classList.add('align-right');

          if (column.render) {
            const rendered = column.render(item);
            if (typeof rendered === 'string') cell.textContent = rendered;
            else cell.appendChild(rendered);
          } else {
            const value = String(item[column.key] ?? '');
            if (column.key === 'status') cell.appendChild(createStatusBadge(value, statusTone(value)));
            else cell.textContent = value;
          }

          row.appendChild(cell);
        });

        body.appendChild(row);
      });
    }

    table.append(thead, body);
    tableWrap.replaceChildren(table);
  }

  titleText.append(eyebrowElement, heading);
  panelTitle.appendChild(titleText);
  if (reorderableColumns.length > 0) {
    const columnsButton = createElement('button', { className: 'icon-button neutral', type: 'button', title: 'Escolher colunas da tabela' });
    columnsButton.setAttribute('aria-label', 'Escolher colunas da tabela');
    columnsButton.appendChild(createIcon('settings'));
    columnsButton.addEventListener('click', () => openColumnsModal());
    panelTitle.appendChild(columnsButton);
  }
  panel.append(panelTitle, tableWrap);
  paintTable();

  function openColumnsModal(): void {
    const modal = createModalShell('Colunas da tabela');
    const list = createElement('ul', { className: 'column-toggle-list' });
    modal.body.appendChild(list);
    document.body.appendChild(modal.overlay);
    renderModalList(list);
  }

  // Reconstroi a lista do modal na ordem atual -- chamado na abertura e de
  // novo a cada drop, sem fechar o modal. Primeira coluna e coluna status
  // nunca aparecem aqui -- sao permanentemente visiveis e fixas em posicao.
  function renderModalList(list: HTMLElement): void {
    const orderedKeys = resolveOrderKeys(reorderableColumns.map((column) => column.key), columnPrefs.order);
    const columnByKey = new Map(reorderableColumns.map((column) => [column.key, column]));
    const rows = orderedKeys.map((key) => columnByKey.get(key)!);

    list.replaceChildren(...rows.map((column) => createColumnRow(column, orderedKeys, list)));
  }

  function createColumnRow(column: TableColumn<T>, orderedKeys: string[], list: HTMLElement): HTMLElement {
    const item = createElement('li', { className: 'column-toggle-item' });
    const label = createElement('label', { className: 'column-toggle-label' });
    const checkbox = createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = isColumnVisible(column);
    checkbox.addEventListener('change', () => {
      columnPrefs = { ...columnPrefs, visible: { ...columnPrefs.visible, [column.key]: checkbox.checked } };
      saveColumnPrefs(resolvedStorageKey, columnPrefs);
      paintTable();
    });
    label.append(checkbox, document.createTextNode(column.label));
    item.appendChild(label);

    // So colunas reordenaveis (fora a primeira e a de status) ganham alca de
    // arrastar -- sem lib nova, so Drag and Drop API nativa.
    if (orderedKeys.includes(column.key)) {
      const handle = createElement('span', { className: 'column-drag-handle', textContent: '⋮⋮', title: 'Arrastar para reordenar' });
      handle.setAttribute('aria-hidden', 'true');
      item.appendChild(handle);
      item.draggable = true;

      item.addEventListener('dragstart', (event) => {
        item.classList.add('dragging');
        event.dataTransfer?.setData('text/plain', column.key);
      });
      item.addEventListener('dragend', () => {
        item.classList.remove('dragging');
        list.querySelectorAll('.column-toggle-item').forEach((row) => row.classList.remove('drag-over'));
      });
      item.addEventListener('dragover', (event) => {
        event.preventDefault();
        item.classList.add('drag-over');
      });
      item.addEventListener('dragleave', () => item.classList.remove('drag-over'));
      item.addEventListener('drop', (event) => {
        event.preventDefault();
        item.classList.remove('drag-over');
        const draggedKey = event.dataTransfer?.getData('text/plain');
        if (draggedKey) reorderColumns(draggedKey, column.key, list);
      });
    }

    return item;
  }

  function reorderColumns(draggedKey: string, targetKey: string, list: HTMLElement): void {
    if (draggedKey === targetKey) return;
    const keys = resolveOrderKeys(reorderableColumns.map((column) => column.key), columnPrefs.order);
    const fromIndex = keys.indexOf(draggedKey);
    const toIndex = keys.indexOf(targetKey);
    if (fromIndex === -1 || toIndex === -1) return;
    keys.splice(toIndex, 0, keys.splice(fromIndex, 1)[0]);
    columnPrefs = { ...columnPrefs, order: keys };
    saveColumnPrefs(resolvedStorageKey, columnPrefs);
    paintTable();
    renderModalList(list);
  }

  return panel;
}

// Acoes (ver/editar/excluir) saem de dentro da tabela e viram uma trilha
// visual paralela ao table-wrap, fora do grid, na mesma ordem/altura das
// linhas -- chame depois de createDataTable(...) passando o painel que ela
// retornou. Scroll sincronizado nos dois sentidos pra acompanhar o
// table-wrap quando a lista excede max-height (data-panel-scroll).
export function attachActionsRail<T>(panel: HTMLElement, rows: T[], renderActions: (row: T) => HTMLElement): void {
  const tableWrap = panel.querySelector<HTMLElement>('.table-wrap');
  if (!tableWrap || rows.length === 0) return;

  const rail = createElement('div', { className: 'table-actions-rail' });
  // Conteudo nao-vazio (nbsp) forma uma linha de texto real do mesmo
  // tamanho do th -- garante a mesma altura renderizada do thead sem
  // precisar adivinhar o valor em px de "line-height: normal".
  rail.appendChild(createElement('div', { className: 'table-actions-rail-header', textContent: ' ' }));
  rows.forEach((row) => {
    const item = createElement('div', { className: 'table-actions-rail-row' });
    item.appendChild(renderActions(row));
    rail.appendChild(item);
  });

  const layout = createElement('div', { className: 'table-row-with-actions' });
  tableWrap.replaceWith(layout);
  layout.append(tableWrap, rail);

  tableWrap.addEventListener('scroll', () => { rail.scrollTop = tableWrap.scrollTop; });
  rail.addEventListener('scroll', () => { tableWrap.scrollTop = rail.scrollTop; });
}
