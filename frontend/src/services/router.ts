import { createClientsPage } from '../pages/ClientsPage';
import { createAgendaPage } from '../pages/AgendaPage';
import { createDocumentsPage } from '../pages/DocumentsPage';
import { createForgotPasswordPage } from '../pages/ForgotPasswordPage';
import { createLoginPage } from '../pages/LoginPage';
import { createResetPasswordPage } from '../pages/ResetPasswordPage';
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

  // Rotas publicas alem de /login -- acessiveis sem sessao, e um usuario
  // ja logado que cair nelas e redirecionado pra home (mesmo comportamento
  // que /login ja tinha).
  const PUBLIC_AUTH_PATHS = new Set(['/login', '/esqueci-senha', '/redefinir-senha']);

  function render(): void {
    const path = window.location.pathname;
    const isPublicAuthPath = PUBLIC_AUTH_PATHS.has(path);

    if (!isAuthenticated() && !isPublicAuthPath) {
      redirect('/login');
      return;
    }

    if (isAuthenticated() && isPublicAuthPath) {
      redirect('/');
      return;
    }

    if (path === '/login') {
      root.replaceChildren(createLoginPage(() => {
        appearanceLoaded = false;
        redirect('/');
      }));
      return;
    }

    if (path === '/esqueci-senha') {
      root.replaceChildren(createForgotPasswordPage());
      return;
    }

    if (path === '/redefinir-senha') {
      root.replaceChildren(createResetPasswordPage());
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
