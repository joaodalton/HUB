import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { createInput } from '../components/formFields';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createIcon } from '../components/Icon';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getEmpresas, type EmpresaRow } from '../services/empresaService';

export function createEmpresasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const layout = createBaseLayout({
    content,
    eyebrow: 'Plataforma',
    title: 'Empresas'
  });
  const loading = useGlobalLoading();
  const toast = useToast();
  let empresas: EmpresaRow[] = [];
  let searchTerm = '';

  void load();

  return layout;

  async function load(): Promise<void> {
    loading.show();
    try {
      empresas = await getEmpresas();
      toast.info('Em breve: edição e exclusão de empresa.');
    } catch {
      toast.error('Não foi possível carregar as empresas.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  function renderContent(): void {
    content.replaceChildren(renderList());
  }

  function renderList(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });

    const toolbar = createElement('div', { className: 'page-actions' });

    const searchInput = createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Pesquisar empresa...';
    searchInput.value = searchTerm;
    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value;
      refresh();
    });

    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';

    const newButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newButton.append(createIcon('plus'), document.createTextNode('Nova Empresa'));
    newButton.addEventListener('click', () => {
      toast.info('Em breve: cadastro de empresa.');
    });

    toolbar.append(searchInput, spacer, newButton);

    const tableHolder = createElement('div');

    function refresh(): void {
      tableHolder.replaceChildren(createTable());
    }

    function createTable(): HTMLElement {
      const filtered = getFiltered();
      const isFiltered = Boolean(searchTerm);

      return createDataTable<EmpresaRow>({
        title: 'Empresas cadastradas na plataforma',
        eyebrow: 'Empresas',
        rows: filtered,
        emptyMessage: loadError()
          ? 'Não foi possível carregar as empresas.'
          : isFiltered
            ? 'Nenhuma empresa encontrada para esse filtro.'
            : 'Nenhuma empresa cadastrada ainda.',
        onRowClick: (empresa) => {
          toast.info(`Visualizar empresa ${empresa.nome} — em breve.`);
        },
        columns: [
          {
            key: 'nome',
            label: 'Empresa',
            render: (empresa) => createNomeCell(empresa)
          },
          {
            key: 'cnpj',
            label: 'CNPJ',
            render: (empresa) => empresa.cnpj || '-'
          },
          {
            key: 'status',
            label: 'Status',
            render: (empresa) => createStatusBadge(empresa.status)
          },
          {
            key: 'totalUsuarios',
            label: 'Usuários',
            align: 'right',
            render: (empresa) => String(empresa.totalUsuarios)
          },
          {
            key: 'acao',
            label: '',
            align: 'right',
            render: (empresa) => createRowActions(empresa)
          }
        ]
      });
    }

    refresh();
    fragment.append(toolbar, tableHolder);
    return fragment;
  }

  function getFiltered(): EmpresaRow[] {
    if (!searchTerm) return empresas;
    const term = normalize(searchTerm);
    return empresas.filter(
      (e) => normalize(e.nome).includes(term) || normalize(e.slug).includes(term)
    );
  }

  function createNomeCell(empresa: EmpresaRow): HTMLElement {
    const wrap = createElement('div', { className: 'cell-id-name' });
    wrap.append(
      createElement('span', { className: 'cell-id-tag', textContent: `#${empresa.id}` }),
      createElement('span', { textContent: empresa.nome }),
      createElement('span', {
        className: 'cell-slug',
        textContent: empresa.slug
      })
    );
    return wrap;
  }

  function createStatusBadge(status: string): HTMLElement {
    const tone = statusTone(status);
    const label = status === 'ativo' ? 'Ativo' : 'Inativo';
    return createElement('span', {
      className: `status-badge tone-${tone}`,
      textContent: label
    });
  }

  function createRowActions(empresa: EmpresaRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-row-actions' });

    const viewButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    viewButton.appendChild(createIcon('eye'));
    viewButton.title = 'Visualizar / Entrar';
    viewButton.setAttribute('aria-label', `Visualizar ${empresa.nome}`);
    viewButton.addEventListener('click', (event) => {
      event.stopPropagation();
      toast.info(`Entrar como ${empresa.nome} — em breve.`);
    });

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.title = 'Editar';
    editButton.setAttribute('aria-label', `Editar ${empresa.nome}`);
    editButton.addEventListener('click', (event) => {
      event.stopPropagation();
      openEditorModal(empresa);
    });

    const deleteButton = createElement('button', { className: 'icon-button', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.title = 'Excluir';
    deleteButton.setAttribute('aria-label', `Excluir ${empresa.nome}`);
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      confirmDelete(empresa);
    });

    wrap.append(viewButton, editButton, deleteButton);
    return wrap;
  }

  function loadError(): boolean {
    return false;
  }

  function openEditorModal(empresa: EmpresaRow): void {
    document.body.appendChild(buildEditorModal({
      empresa,
      onSave: () => {
        toast.info('Salvar empresa — em breve (CRUD não implementado).');
      },
      onClose: () => document.querySelector('.modal-overlay')?.remove()
    }));
  }

  function confirmDelete(empresa: EmpresaRow): void {
    const confirmed = window.confirm(
      `Excluir a empresa ${empresa.nome}? Essa ação não pode ser desfeita.`
    );
    if (!confirmed) return;
    toast.info('Exclusão de empresa — em breve.');
  }

  function normalize(value: string): string {
    return value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }
}

/* -----------------------------------------------------------------------
   Modal de edição de empresa (placeholder visual — CRUD não implementado)
   ----------------------------------------------------------------------- */

type EditorModalOptions = {
  empresa: EmpresaRow;
  onSave: () => void;
  onClose: () => void;
};

function buildEditorModal({ empresa, onSave, onClose }: EditorModalOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Editar empresa' });
  const heading = createElement('h2', { textContent: empresa.nome });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Fechar',
    type: 'button'
  });

  const fields = createElement('div', { className: 'form-grid' });

  const nome = createInput('Nome', 'text', empresa.nome, true);
  const cnpj = createInput('CNPJ', 'text', empresa.cnpj ?? '', true);

  const statusField = createElement('label', { className: 'form-field' });
  const statusLabel = createElement('span', { textContent: 'Status' });
  const statusSelect = createElement('select');
  statusSelect.innerHTML = `
    <option value="ativo">Ativo</option>
    <option value="inativo">Inativo</option>
  `;
  statusSelect.value = (empresa.status ?? 'ativo') === 'ativo' ? 'ativo' : 'inativo';
  statusField.append(statusLabel, statusSelect);

  const slugInfo = createElement('div', { className: 'form-field form-field-wide slug-info' });
  const slugLabel = createElement('span', { textContent: 'Slug' });
  const slugValue = createElement('span', {
    className: 'slug-value',
    textContent: empresa.slug
  });
  const slugNote = createElement('span', {
    className: 'slug-note',
    textContent: 'usado como identificador — não editável'
  });
  slugInfo.append(slugLabel, slugValue, slugNote);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', {
    className: 'button-with-icon',
    textContent: 'Salvar empresa',
    type: 'submit'
  });
  saveButton.append(createIcon('check'));

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(
    nome.field,
    cnpj.field,
    statusField,
    slugInfo
  );
  actions.appendChild(saveButton);

  closeButton.addEventListener('click', onClose);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onClose();
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    onSave();
  });

  form.append(header, fields, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}

function statusTone(status: string): 'success' | 'warning' {
  const normalized = status.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  return normalized.includes('ativo') ? 'success' : 'warning';
}
