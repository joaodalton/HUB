import { createCompanyModal } from '../../components/CreateCompanyModal';
import { createEditCompanyModal } from '../../components/EditCompanyModal';
import { attachActionsRail, createDataTable } from '../../components/DataTable';
import { createIcon } from '../../components/Icon';
import { createStatusBadge } from '../../components/StatusBadge';
import { createElement } from '../../dom';
import { useToast } from '../../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { refreshCurrentUser } from '../../services/authService';
import { deletarEmpresa, entrarNaEmpresa, getPlatformEmpresas, type PlatformEmpresa } from '../services/platformService';
import { invalidateSettingsCache } from '../../services/settingsService';
import { formatDate } from '../../utils/date';
import { t } from '../../services/i18nService';

function companyStatusLabel(status: string): string {
  return ({
    ativa: t('platform.companies.statusAtiva'),
    inativa: t('platform.companies.statusInativa'),
    suspensa: t('platform.companies.statusSuspensa'),
    trial: t('platform.companies.statusTrial')
  } as Record<string, string>)[status.toLowerCase()] ?? status;
}

export function createPlatformCompaniesPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const search = createElement('input', { className: 'platform-search' });
  search.type = 'search'; search.placeholder = t('platform.companies.searchPlaceholder'); search.setAttribute('aria-label', t('platform.companies.searchAriaLabel'));
  const newCompanyButton = createElement('button', { className: 'primary-button button-with-icon', type: 'button' });
  newCompanyButton.append(createIcon('plus'), document.createTextNode(t('platform.companies.newButton')));
  newCompanyButton.addEventListener('click', () => {
    document.body.appendChild(createCompanyModal({
      onCreated: () => { useToast().success(t('platform.companies.createdSuccess')); load(); },
      onError: (message) => useToast().error(message)
    }));
  });
  const toolbar = createElement('div', { className: 'platform-toolbar' }); toolbar.append(search, newCompanyButton);
  const tableHost = createElement('div'); content.append(toolbar, tableHost);
  let companies: PlatformEmpresa[] = [];
  let failed = false;

  const render = (loading = false): void => {
    const term = search.value.trim().toLocaleLowerCase('pt-BR');
    const rows = companies.filter((item) => !term || [item.nome, item.slug].some((value) => value.toLocaleLowerCase('pt-BR').includes(term)));
    const panel = createDataTable<PlatformEmpresa>({
      title: t('platform.companies.tableTitle'), eyebrow: t('platform.companies.tableEyebrow'), rows,
      state: loading ? 'loading' : failed ? 'error' : term && !rows.length ? 'filtered' : 'ready',
      stateTitle: failed ? t('platform.companies.loadError') : undefined,
      emptyMessage: t('platform.companies.emptyMessage'),
      errorAction: { label: t('platform.companies.retry'), onClick: load },
      emptyAction: { label: t('platform.companies.clearSearch'), onClick: () => { search.value = ''; render(); } },
      columns: [
        { key: 'nome', label: t('platform.companies.colNome') },
        { key: 'slug', label: t('platform.companies.colIdentificador') },
        { key: 'status', label: t('platform.companies.colStatus'), render: (row) => createStatusBadge(companyStatusLabel(row.status), row.status.toLowerCase().startsWith('ativ') ? 'success' : 'warning') },
        { key: 'totalClientes', label: t('platform.companies.colClientes'), render: (row) => String(row.totalClientes ?? '—') },
        { key: 'totalUcs', label: t('platform.companies.colUcs'), render: (row) => String(row.totalUcs ?? '—') },
        { key: 'totalUsinas', label: t('platform.companies.colUsinas'), render: (row) => String(row.totalUsinas ?? '—') },
        { key: 'createdAt', label: t('platform.companies.colCriadaEm'), render: (row) => formatDate(row.createdAt) }
      ]
    });
    attachActionsRail(panel, rows, createActions);
    tableHost.replaceChildren(panel);
  };
  const load = (): void => { failed = false; render(true); void getPlatformEmpresas().then((data) => { companies = data; render(); }).catch(() => { failed = true; render(); }); };
  const createEnterButton = (company: PlatformEmpresa): HTMLElement => {
    const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    button.append(createIcon('login'), document.createTextNode(t('platform.companies.enterButton')));
    button.addEventListener('click', () => {
      button.disabled = true;
      void entrarNaEmpresa(company.id)
        .then(() => refreshCurrentUser())
        .then(() => {
          invalidateSettingsCache();
          window.dispatchEvent(new CustomEvent('hub:tenant-context-changed'));
          go('/dashboard');
        })
        .catch((error) => { button.disabled = false; useToast().error(error instanceof Error ? error.message : t('platform.companies.enterError')); });
    });
    return button;
  };
  const createDeleteButton = (company: PlatformEmpresa): HTMLElement => {
    const button = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
    button.append(createIcon('trash'), document.createTextNode(t('platform.companies.deleteButton')));
    button.addEventListener('click', () => {
      const confirmed = window.confirm(t('platform.companies.deleteConfirmTemplate').replace('{name}', company.nome));
      if (!confirmed) return;
      button.disabled = true;
      void deletarEmpresa(company.id)
        .then(() => { useToast().success(t('platform.companies.deletedSuccess')); load(); })
        .catch((error) => {
          button.disabled = false;
          useToast().error(error instanceof Error ? error.message : t('platform.companies.deleteError'));
        });
    });
    return button;
  };
  const createEditButton = (company: PlatformEmpresa): HTMLElement => {
    const button = createElement('button', { className: 'icon-button neutral', type: 'button' });
    button.appendChild(createIcon('edit'));
    button.title = t('platform.companies.editTitle');
    button.setAttribute('aria-label', t('platform.companies.editAriaTemplate').replace('{name}', company.nome));
    button.addEventListener('click', () => {
      document.body.appendChild(createEditCompanyModal({
        empresa: company,
        onSaved: () => { useToast().success(t('platform.companies.updatedSuccess')); load(); },
        onError: (message) => useToast().error(message)
      }));
    });
    return button;
  };
  const createActions = (company: PlatformEmpresa): HTMLElement => {
    const wrapper = createElement('div', { className: 'table-row-actions' });
    wrapper.append(createEditButton(company), createEnterButton(company), createDeleteButton(company));
    return wrapper;
  };
  search.addEventListener('input', () => render()); load();
  return createPlatformLayout({ content, title: t('platform.companies.title'), description: t('platform.companies.description') });
}

function go(path: string): void { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); }
