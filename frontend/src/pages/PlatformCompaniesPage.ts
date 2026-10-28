import { createCompanyModal } from '../components/CreateCompanyModal';
import { createEditCompanyModal } from '../components/EditCompanyModal';
import { attachActionsRail, createDataTable } from '../components/DataTable';
import { createIcon } from '../components/Icon';
import { createStatusBadge } from '../components/StatusBadge';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { refreshCurrentUser } from '../services/authService';
import { deletarEmpresa, entrarNaEmpresa, getPlatformEmpresas, type PlatformEmpresa } from '../services/platformService';
import { invalidateSettingsCache } from '../services/settingsService';
import { formatDate } from '../utils/date';

export function createPlatformCompaniesPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const search = createElement('input', { className: 'platform-search' });
  search.type = 'search'; search.placeholder = 'Buscar por nome ou slug'; search.setAttribute('aria-label', 'Buscar empresas');
  const newCompanyButton = createElement('button', { className: 'primary-button button-with-icon', type: 'button' });
  newCompanyButton.append(createIcon('plus'), document.createTextNode('Nova empresa'));
  newCompanyButton.addEventListener('click', () => {
    document.body.appendChild(createCompanyModal({
      onCreated: () => { useToast().success('Empresa criada.'); load(); },
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
      title: 'Empresas', eyebrow: 'Tenant context', rows,
      state: loading ? 'loading' : failed ? 'error' : term && !rows.length ? 'filtered' : 'ready',
      stateTitle: failed ? 'Não foi possível carregar as empresas.' : undefined,
      emptyMessage: 'Nenhuma empresa cadastrada.',
      errorAction: { label: 'Tentar novamente', onClick: load },
      emptyAction: { label: 'Limpar busca', onClick: () => { search.value = ''; render(); } },
      columns: [
        { key: 'nome', label: 'Nome' },
        { key: 'slug', label: 'Identificador' },
        { key: 'status', label: 'Status', render: (row) => createStatusBadge(row.status, row.status.toLowerCase().startsWith('ativ') ? 'success' : 'warning') },
        { key: 'totalClientes', label: 'Clientes', render: (row) => String(row.totalClientes ?? '—') },
        { key: 'totalUcs', label: 'UCs', render: (row) => String(row.totalUcs ?? '—') },
        { key: 'totalUsinas', label: 'Usinas', render: (row) => String(row.totalUsinas ?? '—') },
        { key: 'createdAt', label: 'Criada em', render: (row) => formatDate(row.createdAt) }
      ]
    });
    attachActionsRail(panel, rows, createActions);
    tableHost.replaceChildren(panel);
  };
  const load = (): void => { failed = false; render(true); void getPlatformEmpresas().then((data) => { companies = data; render(); }).catch(() => { failed = true; render(); }); };
  const createEnterButton = (company: PlatformEmpresa): HTMLElement => {
    const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    button.append(createIcon('login'), document.createTextNode('Entrar na empresa'));
    button.addEventListener('click', () => {
      button.disabled = true;
      void entrarNaEmpresa(company.id)
        .then(() => refreshCurrentUser())
        .then(() => {
          invalidateSettingsCache();
          window.dispatchEvent(new CustomEvent('hub:tenant-context-changed'));
          go('/dashboard');
        })
        .catch((error) => { button.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível entrar na empresa.'); });
    });
    return button;
  };
  const createDeleteButton = (company: PlatformEmpresa): HTMLElement => {
    const button = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
    button.append(createIcon('trash'), document.createTextNode('Excluir'));
    button.addEventListener('click', () => {
      const confirmed = window.confirm(`Excluir a empresa ${company.nome}? Essa acao nao pode ser desfeita.`);
      if (!confirmed) return;
      button.disabled = true;
      void deletarEmpresa(company.id)
        .then(() => { useToast().success('Empresa excluida.'); load(); })
        .catch((error) => {
          button.disabled = false;
          useToast().error(error instanceof Error ? error.message : 'Não foi possível excluir a empresa.');
        });
    });
    return button;
  };
  const createEditButton = (company: PlatformEmpresa): HTMLElement => {
    const button = createElement('button', { className: 'icon-button neutral', type: 'button' });
    button.appendChild(createIcon('edit'));
    button.title = 'Editar';
    button.setAttribute('aria-label', `Editar ${company.nome}`);
    button.addEventListener('click', () => {
      document.body.appendChild(createEditCompanyModal({
        empresa: company,
        onSaved: () => { useToast().success('Empresa atualizada.'); load(); },
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
  return createPlatformLayout({ content, title: 'Empresas', description: 'Escolha uma empresa para iniciar um contexto operacional explícito.' });
}

function go(path: string): void { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); }
