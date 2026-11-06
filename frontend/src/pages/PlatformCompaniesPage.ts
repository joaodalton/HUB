import { createDataTable } from '../components/DataTable';
import { createIcon } from '../components/Icon';
import { createStatusBadge } from '../components/StatusBadge';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { refreshCurrentUser } from '../services/authService';
import { entrarNaEmpresa, getPlatformEmpresas, type PlatformEmpresa } from '../services/platformService';
import { invalidateSettingsCache } from '../services/settingsService';

export function createPlatformCompaniesPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const search = createElement('input', { className: 'platform-search' });
  search.type = 'search'; search.placeholder = 'Buscar por nome ou slug'; search.setAttribute('aria-label', 'Buscar empresas');
  const toolbar = createElement('div', { className: 'platform-toolbar' }); toolbar.appendChild(search);
  const tableHost = createElement('div'); content.append(toolbar, tableHost);
  let companies: PlatformEmpresa[] = [];
  let failed = false;

  const render = (loading = false): void => {
    const term = search.value.trim().toLocaleLowerCase('pt-BR');
    const rows = companies.filter((item) => !term || [item.nome, item.slug].some((value) => value.toLocaleLowerCase('pt-BR').includes(term)));
    tableHost.replaceChildren(createDataTable<PlatformEmpresa>({
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
        { key: 'totalUsuarios', label: 'Usuários', render: (row) => String(row.totalUsuarios ?? '—') },
        { key: 'createdAt', label: 'Criada em', render: (row) => formatDate(row.createdAt) },
        { key: 'action', label: 'Ação', align: 'right', render: createEnterButton }
      ]
    }));
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
  search.addEventListener('input', () => render()); load();
  return createPlatformLayout({ content, title: 'Empresas', description: 'Escolha uma empresa para iniciar um contexto operacional explícito.' });
}

function go(path: string): void { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); }
function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('pt-BR').format(date);
}
