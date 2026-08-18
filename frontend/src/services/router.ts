import { createClientsPage } from '../pages/ClientsPage';
import { createAgendaPage } from '../pages/AgendaPage';
import { createDocumentsPage } from '../pages/DocumentsPage';
import { createLoginPage } from '../pages/LoginPage';
import { createPendenciasPage } from '../pages/PendenciasPage';
import { createPlantsPage } from '../pages/PlantsPage';
import { createRateioPage } from '../pages/RateioPage';
import { createSettingsPage } from '../pages/SettingsPage';
import { createUcsPage } from '../pages/UcsPage';
import { createUsersPage } from '../pages/UsersPage';
import { createEmpresasPage } from '../pages/EmpresasPage';
import { ensureSession, isAuthenticated } from './authService';
import { loadSettings } from './settingsService';

type Route = {
  path: string;
  render: () => HTMLElement;
};

export function createRouter(root: HTMLElement) {
  const routes: Route[] = [
    { path: '/', render: createDocumentsPage },
    { path: '/documentos', render: createDocumentsPage },
    { path: '/clientes', render: createClientsPage },
    { path: '/ucs', render: createUcsPage },
    { path: '/usinas', render: createPlantsPage },
    { path: '/rateio', render: createRateioPage },
    { path: '/pendencias', render: createPendenciasPage },
    { path: '/agenda', render: createAgendaPage },
    { path: '/usuarios', render: createUsersPage },
    { path: '/empresas', render: createEmpresasPage },
    { path: '/configuracoes', render: createSettingsPage }
  ];

  let appearanceLoaded = false;

  function resolveRoute(): Route {
    return routes.find((route) => route.path === window.location.pathname) ?? routes[0];
  }

  function redirect(path: string): void {
    window.history.replaceState({}, '', path);
    render();
  }

  function ensureAppearanceLoaded(): void {
    if (appearanceLoaded) return;
    appearanceLoaded = true;

    loadSettings().catch(() => {
      // Aparencia fica no padrao se o backend estiver fora do ar; nao trava a navegacao.
    });
  }

  function render(): void {
    const isLoginPath = window.location.pathname === '/login';

    if (!isAuthenticated() && !isLoginPath) {
      redirect('/login');
      return;
    }

    if (isAuthenticated() && isLoginPath) {
      redirect('/');
      return;
    }

    if (isLoginPath) {
      root.replaceChildren(createLoginPage(() => {
        appearanceLoaded = false;
        redirect('/');
      }));
      return;
    }

    ensureAppearanceLoaded();

    const route = resolveRoute();
    root.replaceChildren(route.render());
  }

  return {
    start() {
      window.addEventListener('popstate', render);
      ensureSession().finally(render);
    }
  };
}
