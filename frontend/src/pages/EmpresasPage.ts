import { attachActionsRail, createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { maskCnpjInput } from '../components/cadastroFields';
import { createFormSection, createInput } from '../components/formFields';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createIcon } from '../components/Icon';
import { createIconStatCard } from '../components/IconStatCard';
import { createBaseLayout } from '../layouts/BaseLayout';
import { createEmpresa, getEmpresaAtual, getEmpresaDocumentos, getEmpresas, updateEmpresaPlatform, type EmpresaAtual, type EmpresaDocumentos, type EmpresaRow } from '../services/empresaService';
import { getCurrentUser, refreshCurrentUser } from '../services/authService';
import { entrarNaEmpresa, sairDaVisualizacao } from '../platform/services/platformService';
import { getDashboardResumo, type DashboardResumo } from '../services/dashboardService';
import { t } from '../services/i18nService';

export function createEmpresasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const layout = createBaseLayout({
    content,
    eyebrow: t('empresas.page.eyebrow'),
    title: t('empresas.page.title')
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
      toast.error(t('empresas.page.loadError'));
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
    searchInput.placeholder = t('empresas.page.searchPlaceholder');
    searchInput.value = searchTerm;
    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value;
      refresh();
    });

    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';

    const newButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newButton.append(createIcon('plus'), document.createTextNode(t('empresas.page.newButton')));
    newButton.addEventListener('click', () => document.body.appendChild(createEmpresaModal(async data => { await createEmpresa(data); toast.success(t('empresas.page.createdSuccess')); await load(); })));

    toolbar.append(searchInput, spacer);

    const viewingEmpresaNome = getCurrentUser()?.platformViewEmpresaNome;
    if (viewingEmpresaNome) {
      const exitButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
      exitButton.append(createIcon('login'), document.createTextNode(t('empresas.page.exitButtonTemplate').replace('{name}', viewingEmpresaNome)));
      exitButton.title = t('empresas.page.exitButtonTitle');
      exitButton.addEventListener('click', () => void handleSair());
      toolbar.appendChild(exitButton);
    }

    toolbar.appendChild(newButton);

    const tableHolder = createElement('div');

    function refresh(): void {
      tableHolder.replaceChildren(createTable());
    }

    function createTable(): HTMLElement {
      const filtered = getFiltered();
      const isFiltered = Boolean(searchTerm);

      const panel = createDataTable<EmpresaRow>({
        title: t('empresas.page.tableTitle'),
        eyebrow: t('empresas.page.tableEyebrow'),
        rows: filtered,
        emptyMessage: loadError()
          ? t('empresas.page.loadError')
          : isFiltered
            ? t('empresas.page.emptyFiltered')
            : t('empresas.page.emptyAll'),
        onRowClick: (empresa) => {
          void openDetail(empresa);
        },
        columns: [
          {
            key: 'id',
            label: t('empresas.page.colId'),
            render: (empresa) => `#${empresa.id}`
          },
          {
            key: 'nome',
            label: t('empresas.page.colEmpresa'),
            render: (empresa) => createNomeCell(empresa)
          },
          {
            key: 'cnpj',
            label: t('empresas.page.colCnpj'),
            render: (empresa) => empresa.cnpj || '-'
          },
          {
            key: 'status',
            label: t('empresas.page.colStatus'),
            render: (empresa) => createStatusBadge(empresa.status)
          },
          {
            key: 'totalUsuarios',
            label: t('empresas.page.colUsuarios'),
            align: 'right',
            render: (empresa) => String(empresa.totalUsuarios)
          }
        ]
      });

      attachActionsRail(panel, filtered, createRowActions);
      return panel;
    }

    refresh();
    fragment.append(toolbar, createEmpresaMetrics(empresas), tableHolder);
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
    const labels: Record<string, string> = {
      ativa: t('empresas.page.statusAtiva'),
      inativa: t('empresas.page.statusInativa'),
      suspensa: t('empresas.page.statusSuspensa')
    };
    return createElement('span', {
      className: `status-badge tone-${tone}`,
      textContent: labels[status] ?? status
    });
  }

  function createRowActions(empresa: EmpresaRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-row-actions' });

    const viewButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    viewButton.appendChild(createIcon('eye'));
    viewButton.title = t('empresas.page.viewTitle');
    viewButton.setAttribute('aria-label', t('empresas.page.viewAriaTemplate').replace('{name}', empresa.nome));
    viewButton.addEventListener('click', (event) => {
      event.stopPropagation();
      void handleEntrar(empresa);
    });

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.title = t('empresas.page.editTitle');
    editButton.setAttribute('aria-label', t('empresas.page.editAriaTemplate').replace('{name}', empresa.nome));
    editButton.addEventListener('click', (event) => {
      event.stopPropagation();
      openEditorModal(empresa);
    });

    const deleteButton = createElement('button', { className: 'icon-button', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.title = t('empresas.page.deleteTitle');
    deleteButton.setAttribute('aria-label', t('empresas.page.deleteAriaTemplate').replace('{name}', empresa.nome));
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
          toast.success(t('empresas.page.updatedSuccess'));
          document.querySelector('.modal-overlay')?.remove();
          await load();
        } catch (error) {
          toast.error(error instanceof Error ? error.message : t('empresas.page.saveError'));
        }
      },
      onClose: () => document.querySelector('.modal-overlay')?.remove()
    }));
  }

  function confirmDelete(empresa: EmpresaRow): void {
    const confirmed = window.confirm(
      t('empresas.page.confirmSuspendTemplate').replace('{name}', empresa.nome)
    );
    if (!confirmed) return;
    void updateEmpresaPlatform(empresa.id, { status: 'suspensa' })
      .then(() => { toast.success(t('empresas.page.suspendedSuccess')); return load(); })
      .catch((error) => toast.error(error instanceof Error ? error.message : t('empresas.page.suspendError')));
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
      await entrarNaEmpresa(empresa.id);
      const [atual, documentos, resumo] = await Promise.all([
        getEmpresaAtual(), getEmpresaDocumentos(), getDashboardResumo()
      ]);
      content.replaceChildren(renderDetail(empresa, atual, documentos, resumo));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('empresas.page.openError'));
    } finally {
      loading.hide();
    }
  }

  async function handleEntrar(empresa: EmpresaRow): Promise<void> {
    loading.show();
    try {
      await entrarNaEmpresa(empresa.id);
      await refreshCurrentUser();
      window.history.pushState({}, '', '/dashboard');
      window.dispatchEvent(new PopStateEvent('popstate'));
    } catch {
      toast.error(t('empresas.page.enterError'));
    } finally {
      loading.hide();
    }
  }

  async function handleSair(): Promise<void> {
    loading.show();
    try {
      await sairDaVisualizacao();
      await refreshCurrentUser();
      toast.success(t('empresas.page.exitedSuccess'));
      await load();
    } catch {
      toast.error(t('empresas.page.exitError'));
    } finally {
      loading.hide();
    }
  }

  function renderDetail(empresa: EmpresaRow, atual: EmpresaAtual, documentos: EmpresaDocumentos, resumo: DashboardResumo): HTMLElement {
    const detail = createElement('div', { className: 'content-stack' });
    const back = createElement('button', { className: 'detail-back-link', type: 'button', textContent: t('empresas.page.backLink') });
    back.addEventListener('click', renderContent);

    const header = createElement('section', { className: 'detail-header' });
    const title = createElement('div', { className: 'detail-title-row' });
    title.append(createElement('span', { className: 'cell-id-tag', textContent: `#${empresa.id}` }), createElement('h2', { textContent: atual.nome }), createStatusBadge(empresa.status));
    const headerActions = createElement('div', { className: 'detail-actions' });
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('empresas.page.editButton') });
    edit.addEventListener('click', () => openEditorModal(empresa));
    const suspend = createElement('button', { className: 'danger-button', type: 'button', textContent: empresa.status === 'suspensa' ? t('empresas.page.reactivateButton') : t('empresas.page.suspendButton') });
    suspend.addEventListener('click', () => void updateEmpresaPlatform(empresa.id, { status: empresa.status === 'suspensa' ? 'ativa' : 'suspensa' }).then(() => openDetail(empresa)).catch(error => toast.error(error instanceof Error ? error.message : t('empresas.page.updateError'))));
    headerActions.append(edit, suspend);
    header.append(title, headerActions);

    const panels = createElement('div', { className: 'detail-columns' });
    const info = createElement('section', { className: 'detail-info-panel' });
    const infoGrid = createElement('div', { className: 'detail-info-grid' });
    infoGrid.append(...[
      [t('empresas.page.fieldRazaoSocial'), atual.razaoSocial], [t('empresas.page.fieldCnpj'), atual.cnpj], [t('empresas.page.fieldEmail'), atual.email], [t('empresas.page.fieldTelefone'), atual.telefone], [t('empresas.page.fieldSlug'), empresa.slug]
    ].map(([label, value]) => createDetailField(String(label), value || t('empresas.page.notInformed'))));
    info.append(createElement('span', { className: 'eyebrow', textContent: t('empresas.page.infoEyebrow') }), infoGrid);
    const usage = createElement('section', { className: 'plant-summary-panel' });
    const usageRows = createElement('div', { className: 'plant-summary-rows' });
    usageRows.append(
      createSummaryRow(t('empresas.page.summaryUsuarios'), String(empresa.totalUsuarios)),
      createSummaryRow(t('empresas.page.summaryClientes'), countLabel(resumo.clientes.total)),
      createSummaryRow(t('empresas.page.summaryUcs'), countLabel(resumo.ucs.total)),
      createSummaryRow(t('empresas.page.summaryUsinas'), countLabel(resumo.usinas.total)));
    usage.append(createElement('span', { className: 'eyebrow', textContent: t('empresas.page.usageEyebrow') }), usageRows);
    const users = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('empresas.page.viewUsersButton') });
    users.addEventListener('click', () => { window.history.pushState({}, '', '/usuarios'); window.dispatchEvent(new PopStateEvent('popstate')); });
    usage.appendChild(users);
    panels.append(info, usage);

    const tabs = createElement('section', { className: 'detail-tabs-panel' });
    const tabBar = createElement('div', { className: 'detail-tabs' });
    const subscriptionTab = createElement('button', { className: 'detail-tab disabled', type: 'button', textContent: t('empresas.page.subscriptionTab') });
    subscriptionTab.disabled = true;
    tabBar.append(createElement('button', { className: 'detail-tab active', type: 'button', textContent: t('empresas.page.documentsTab') }), subscriptionTab);
    const docs = createElement('div', { className: 'detail-info-grid' });
    docs.append(createDetailField(t('empresas.page.fieldCnpj'), documentos.cnpj?.nome || t('empresas.page.notAttached')), createDetailField(t('empresas.page.fieldEstatuto'), documentos.estatuto?.nome || t('empresas.page.notAttached')));
    tabs.append(tabBar, docs);
    detail.append(back, header, panels, tabs);
    return detail;
  }
}

function createEmpresaMetrics(empresas: EmpresaRow[]): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });
  grid.append(
    createIconStatCard({ icon: 'plants', chipColor: 'blue', value: String(empresas.length), label: t('empresas.page.metricEmpresas') }),
    createIconStatCard({ icon: 'check', chipColor: 'green', value: String(empresas.filter((empresa) => empresa.status === 'ativa').length), label: t('empresas.page.metricEmpresasAtivas') }),
    createIconStatCard({ icon: 'clients', chipColor: 'purple', value: String(empresas.reduce((total, empresa) => total + empresa.totalUsuarios, 0)), label: t('empresas.page.metricUsuarios') })
  );
  return grid;
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
  return total === null ? t('empresas.page.unavailable') : String(total);
}

function createEmpresaModal(onCreate: (data: { empresa: { nome: string; cnpj?: string }; owner: { nome: string; email: string; senha: string } }) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' }); const panel = createElement('article', { className: 'client-card' }); const form = createElement('form', { className: 'client-form' });
  const nome = createInput(t('empresas.page.fieldNomeEmpresa'), 'text', '', true); const cnpj = createInput(t('empresas.page.fieldCnpj'), 'text', '', false); maskCnpjInput(cnpj.input); const owner = createInput(t('empresas.page.fieldNomeProprietario'), 'text', '', true); const email = createInput(t('empresas.page.fieldEmailProprietario'), 'email', '', true); const senha = createInput(t('empresas.page.fieldSenhaInicial'), 'password', '', true); senha.input.minLength = 6;
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('empresas.page.cancel') }); const submit = createElement('button', { type: 'submit', textContent: t('empresas.page.createButton') }); const close = () => overlay.remove(); cancel.addEventListener('click', close);
  form.append(createElement('h2', { textContent: t('empresas.page.newModalTitle') }), createFormSection(t('empresas.page.sectionDadosEmpresa'), nome.field, cnpj.field), createFormSection(t('empresas.page.sectionUsuarioResponsavel'), owner.field, email.field, senha.field), createElement('div', { className: 'form-actions' })); (form.lastElementChild as HTMLElement).append(cancel, submit);
  form.addEventListener('submit', async event => { event.preventDefault(); if (!form.reportValidity()) return; submit.disabled = true; try { await onCreate({ empresa: { nome: nome.input.value.trim(), cnpj: cnpj.input.value.trim() || undefined }, owner: { nome: owner.input.value.trim(), email: email.input.value.trim(), senha: senha.input.value } }); close(); } catch (error) { submit.disabled = false; useToast().error(error instanceof Error ? error.message : t('empresas.page.createError')); } }); panel.appendChild(form); overlay.appendChild(panel); return overlay;
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
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('empresas.page.editEyebrow') });
  const heading = createElement('h2', { textContent: empresa.nome });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: t('empresas.page.close'),
    type: 'button'
  });

  const fields = createElement('div', { className: 'form-grid' });

  const nome = createInput(t('empresas.page.fieldNome'), 'text', empresa.nome, true);
  const cnpj = createInput(t('empresas.page.fieldCnpj'), 'text', empresa.cnpj ?? '', true);
  maskCnpjInput(cnpj.input);

  const statusField = createElement('label', { className: 'form-field' });
  const statusLabel = createElement('span', { textContent: t('empresas.page.fieldStatus') });
  const statusSelect = createElement('select');
  const statusOptions: Array<[string, string]> = [
    ['ativa', t('empresas.page.statusAtiva')],
    ['inativa', t('empresas.page.statusInativa')],
    ['suspensa', t('empresas.page.statusSuspensa')]
  ];
  statusOptions.forEach(([value, label]) => {
    const option = createElement('option', { textContent: label }) as HTMLOptionElement;
    option.value = value;
    statusSelect.appendChild(option);
  });
  statusSelect.value = empresa.status ?? 'ativa';
  statusField.append(statusLabel, statusSelect);

  const slugInfo = createElement('div', { className: 'form-field form-field-wide slug-info' });
  const slugLabel = createElement('span', { textContent: t('empresas.page.fieldSlug') });
  const slugValue = createElement('span', {
    className: 'slug-value',
    textContent: empresa.slug
  });
  const slugNote = createElement('span', {
    className: 'slug-note',
    textContent: t('empresas.page.slugNote')
  });
  slugInfo.append(slugLabel, slugValue, slugNote);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', {
    className: 'button-with-icon',
    textContent: t('empresas.page.saveButton'),
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
