import { createClientsPage } from '../pages/ClientsPage';
import { createDashboardPage } from '../pages/DashboardPage';
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
import { createTemplatesPage } from '../pages/TemplatesPage';
import { createChangePasswordPage } from '../pages/ChangePasswordPage';
import { createFaturasPage } from '../pages/FaturasPage';
import { createMessagesPage } from '../pages/MessagesPage';
import { createBillingRulesPage } from '../pages/BillingRulesPage';
import { createBillingRuleEditorPage } from '../pages/BillingRuleEditorPage';
import { createPlatformOverviewPage } from '../pages/PlatformOverviewPage';
import { createPlatformCompaniesPage } from '../pages/PlatformCompaniesPage';
import { ensureSession, getCurrentUser, isAuthenticated } from './authService';
import { loadSettings } from './settingsService';

type Route = {
  path: string;
  render: () => HTMLElement;
};

export function createRouter(root: HTMLElement) {
  const routes: Route[] = [
    { path: '/', render: createDashboardPage },
    { path: '/dashboard', render: createDashboardPage },
    { path: '/documentos', render: createDocumentsPage },
    { path: '/clientes', render: createClientsPage },
    { path: '/ucs', render: createUcsPage },
    { path: '/usinas', render: createPlantsPage },
    { path: '/rateio', render: createRateioPage },
    { path: '/faturas', render: createFaturasPage },
    { path: '/regras-cobranca', render: createBillingRulesPage },
    { path: '/regras-cobranca/nova', render: () => createBillingRuleEditorPage() },
    { path: '/pendencias', render: createPendenciasPage },
    { path: '/agenda', render: createAgendaPage },
    { path: '/usuarios', render: createUsersPage },
    { path: '/empresas', render: createEmpresasPage },
    { path: '/templates', render: createTemplatesPage },
    { path: '/mensagens', render: createMessagesPage },
    { path: '/trocar-senha', render: createChangePasswordPage },
    { path: '/configuracoes', render: createSettingsPage },
    { path: '/platform', render: createPlatformOverviewPage },
    { path: '/platform/companies', render: createPlatformCompaniesPage }
  ];

  let appearanceLoaded = false;

  function resolveRoute(): Route {
    const path = window.location.pathname;
    const exact = routes.find((route) => route.path === path);
    if (exact) return exact;
    const match = /^\/regras-cobranca\/([1-9]\d*)\/editar$/.exec(path);
    if (match) {
      const id = Number(match[1]);
      if (Number.isSafeInteger(id)) return { path, render: () => createBillingRuleEditorPage(id) };
    }
    return routes[0];
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

  window.addEventListener('hub:password-change-required', () => {
    if (isAuthenticated() && window.location.pathname !== '/trocar-senha') redirect('/trocar-senha');
  });

  window.addEventListener('hub:tenant-context-changed', () => {
    appearanceLoaded = false;
  });

  function render(): void {
    const path = window.location.pathname;
    const isPublicAuthPath = PUBLIC_AUTH_PATHS.has(path);

    const mustChangePassword = getCurrentUser()?.mustChangePassword === true;
    const platformAdmin = getCurrentUser()?.isPlatformAdmin === true;
    if (!isAuthenticated() && !isPublicAuthPath) {
      redirect('/login');
      return;
    }

    if (isAuthenticated() && mustChangePassword && path !== '/trocar-senha') {
      redirect('/trocar-senha');
      return;
    }

    if (isAuthenticated() && path === '/trocar-senha' && !mustChangePassword) {
      redirect('/dashboard');
      return;
    }

    if (isAuthenticated() && isPublicAuthPath) {
      redirect(platformAdmin ? '/platform' : '/');
      return;
    }

    if (isAuthenticated() && path.startsWith('/platform') && !platformAdmin) {
      redirect('/dashboard');
      return;
    }

    if (isAuthenticated() && platformAdmin && path.startsWith('/platform')
      && path !== '/platform' && path !== '/platform/companies') {
      redirect('/platform');
      return;
    }

    // O shell da plataforma nunca coexiste com um tenant administrativo ativo.
    // Para voltar à plataforma, o administrador usa "Sair da empresa", que
    // limpa o cookie no backend antes da navegação.
    if (isAuthenticated() && platformAdmin && getCurrentUser()?.platformViewEmpresaId
      && path.startsWith('/platform')) {
      redirect('/dashboard');
      return;
    }

    if (isAuthenticated() && platformAdmin && !getCurrentUser()?.platformViewEmpresaId
      && !path.startsWith('/platform') && path !== '/trocar-senha') {
      redirect('/platform');
      return;
    }

    if (path === '/login') {
      root.replaceChildren(createLoginPage((user) => {
        appearanceLoaded = false;
        redirect(user.isPlatformAdmin ? '/platform' : '/');
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

    // O shell global usa os tokens do HUB. Aparência customizada pertence
    // exclusivamente ao tenant operacional selecionado.
    if (!path.startsWith('/platform')) ensureAppearanceLoaded();

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
