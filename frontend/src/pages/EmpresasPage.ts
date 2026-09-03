import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { createInput } from '../components/formFields';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createIcon } from '../components/Icon';
import { createBaseLayout } from '../layouts/BaseLayout';
import { createEmpresa, getEmpresaAtual, getEmpresaDocumentos, getEmpresas, updateEmpresaPlatform, type EmpresaAtual, type EmpresaDocumentos, type EmpresaRow } from '../services/empresaService';
import { enterEmpresa } from '../services/platformService';
import { getDashboardResumo, type DashboardResumo } from '../services/dashboardService';

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
    newButton.addEventListener('click', () => document.body.appendChild(createEmpresaModal(async data => { await createEmpresa(data); toast.success('Empresa criada.'); await load(); })));

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
          void openDetail(empresa);
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
      void openDetail(empresa);
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
      onSave: async (data) => {
        try {
          await updateEmpresaPlatform(empresa.id, data);
          toast.success('Empresa atualizada.');
          document.querySelector('.modal-overlay')?.remove();
          await load();
        } catch (error) {
          toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a empresa.');
        }
      },
      onClose: () => document.querySelector('.modal-overlay')?.remove()
    }));
  }

  function confirmDelete(empresa: EmpresaRow): void {
    const confirmed = window.confirm(
      `Suspender a empresa ${empresa.nome}? Os dados serão preservados.`
    );
    if (!confirmed) return;
    void updateEmpresaPlatform(empresa.id, { status: 'suspensa' })
      .then(() => { toast.success('Empresa suspensa.'); return load(); })
      .catch((error) => toast.error(error instanceof Error ? error.message : 'Não foi possível suspender a empresa.'));
  }

  function normalize(value: string): string {
    return value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  async function openDetail(empresa: EmpresaRow): Promise<void> {
    loading.show();
    try {
      await enterEmpresa(empresa.id);
      const [atual, documentos, resumo] = await Promise.all([
        getEmpresaAtual(), getEmpresaDocumentos(), getDashboardResumo()
      ]);
      content.replaceChildren(renderDetail(empresa, atual, documentos, resumo));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível abrir a empresa.');
    } finally {
      loading.hide();
    }
  }

  function renderDetail(empresa: EmpresaRow, atual: EmpresaAtual, documentos: EmpresaDocumentos, resumo: DashboardResumo): HTMLElement {
    const detail = createElement('div', { className: 'content-stack' });
    const back = createElement('button', { className: 'detail-back-link', type: 'button', textContent: '← Empresas' });
    back.addEventListener('click', renderContent);

    const header = createElement('section', { className: 'detail-header' });
    const title = createElement('div', { className: 'detail-title-row' });
    title.append(createElement('span', { className: 'cell-id-tag', textContent: `#${empresa.id}` }), createElement('h2', { textContent: atual.nome }), createStatusBadge(empresa.status));
    const headerActions = createElement('div', { className: 'detail-actions' });
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Editar' });
    edit.addEventListener('click', () => openEditorModal(empresa));
    const suspend = createElement('button', { className: 'danger-button', type: 'button', textContent: empresa.status === 'suspensa' ? 'Reativar' : 'Suspender' });
    suspend.addEventListener('click', () => void updateEmpresaPlatform(empresa.id, { status: empresa.status === 'suspensa' ? 'ativa' : 'suspensa' }).then(() => openDetail(empresa)).catch(error => toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar a empresa.')));
    headerActions.append(edit, suspend);
    header.append(title, headerActions);

    const panels = createElement('div', { className: 'detail-columns' });
    const info = createElement('section', { className: 'detail-info-panel' });
    const infoGrid = createElement('div', { className: 'detail-info-grid' });
    infoGrid.append(...[
      ['Razão social', atual.razaoSocial], ['CNPJ', atual.cnpj], ['E-mail', atual.email], ['Telefone', atual.telefone], ['Slug', empresa.slug]
    ].map(([label, value]) => createDetailField(String(label), value || 'Não informado')));
    info.append(createElement('span', { className: 'eyebrow', textContent: 'Informações gerais' }), infoGrid);
    const usage = createElement('section', { className: 'plant-summary-panel' });
    const usageRows = createElement('div', { className: 'plant-summary-rows' });
    usageRows.append(
      createSummaryRow('Usuários ativos', String(empresa.totalUsuarios)),
      createSummaryRow('Clientes cadastrados', countLabel(resumo.clientes.total)),
      createSummaryRow('UCs', countLabel(resumo.ucs.total)),
      createSummaryRow('Usinas', countLabel(resumo.usinas.total)));
    usage.append(createElement('span', { className: 'eyebrow', textContent: 'Uso & Limites' }), usageRows);
    const users = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Ver usuários desta empresa' });
    users.addEventListener('click', () => { window.history.pushState({}, '', '/usuarios'); window.dispatchEvent(new PopStateEvent('popstate')); });
    usage.appendChild(users);
    panels.append(info, usage);

    const tabs = createElement('section', { className: 'detail-tabs-panel' });
    const tabBar = createElement('div', { className: 'detail-tabs' });
    const subscriptionTab = createElement('button', { className: 'detail-tab disabled', type: 'button', textContent: 'Assinatura (em breve)' });
    subscriptionTab.disabled = true;
    tabBar.append(createElement('button', { className: 'detail-tab active', type: 'button', textContent: 'Documentos' }), subscriptionTab);
    const docs = createElement('div', { className: 'detail-info-grid' });
    docs.append(createDetailField('CNPJ', documentos.cnpj?.nome || 'Não anexado'), createDetailField('Estatuto', documentos.estatuto?.nome || 'Não anexado'));
    tabs.append(tabBar, docs);
    detail.append(back, header, panels, tabs);
    return detail;
  }
}

function createDetailField(label: string, value: string): HTMLElement {
  const field = createElement('div', { className: 'detail-info-field' });
  field.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
  return field;
}

function createSummaryRow(label: string, value: string): HTMLElement {
  const row = createElement('div', { className: 'plant-summary-row' });
  row.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
  return row;
}

function countLabel(total: number | null): string {
  return total === null ? 'Indisponível' : String(total);
}

function createEmpresaModal(onCreate: (data: { empresa: { nome: string; cnpj?: string }; owner: { nome: string; email: string; senha: string } }) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' }); const panel = createElement('article', { className: 'client-card' }); const form = createElement('form', { className: 'client-form' });
  const nome = createInput('Nome da empresa', 'text', '', true); const cnpj = createInput('CNPJ', 'text', '', false); const owner = createInput('Nome do proprietário', 'text', '', true); const email = createInput('E-mail do proprietário', 'email', '', true); const senha = createInput('Senha inicial', 'password', '', true); senha.input.minLength = 6;
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' }); const submit = createElement('button', { type: 'submit', textContent: 'Criar empresa' }); const close = () => overlay.remove(); cancel.addEventListener('click', close);
  form.append(createElement('h2', { textContent: 'Nova empresa' }), nome.field, cnpj.field, owner.field, email.field, senha.field, createElement('div', { className: 'form-actions' })); (form.lastElementChild as HTMLElement).append(cancel, submit);
  form.addEventListener('submit', async event => { event.preventDefault(); if (!form.reportValidity()) return; submit.disabled = true; try { await onCreate({ empresa: { nome: nome.input.value.trim(), cnpj: cnpj.input.value.trim() || undefined }, owner: { nome: owner.input.value.trim(), email: email.input.value.trim(), senha: senha.input.value } }); close(); } catch (error) { submit.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível criar a empresa.'); } }); panel.appendChild(form); overlay.appendChild(panel); return overlay;
}

/* -----------------------------------------------------------------------
   Modal de edição de empresa (placeholder visual — CRUD não implementado)
   ----------------------------------------------------------------------- */

type EditorModalOptions = {
  empresa: EmpresaRow;
  onSave: (data: { nome: string; cnpj: string; status: string }) => void | Promise<void>;
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
    <option value="ativa">Ativa</option>
    <option value="inativa">Inativa</option>
    <option value="suspensa">Suspensa</option>
  `;
  statusSelect.value = empresa.status ?? 'ativa';
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
    void onSave({ nome: nome.input.value.trim(), cnpj: cnpj.input.value.trim(), status: statusSelect.value });
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
