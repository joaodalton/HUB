import { createClientsPage } from '../pages/ClientsPage';
import { createAgendaPage } from '../pages/AgendaPage';
import { createDocumentsPage } from '../pages/DocumentsPage';
import { createLoginPage } from '../pages/LoginPage';
import { createPlaceholderPage } from '../pages/PlaceholderPage';
import { createPlantsPage } from '../pages/PlantsPage';
import { createSettingsPage } from '../pages/SettingsPage';
import { isAuthenticated } from './authService';

type Route = {
  path: string;
  render: () => HTMLElement;
};

export function createRouter(root: HTMLElement) {
  const routes: Route[] = [
    { path: '/', render: createDocumentsPage },
    { path: '/documentos', render: createDocumentsPage },
    { path: '/clientes', render: createClientsPage },
    {
      path: '/ucs',
      render: () => createPlaceholderPage({
        eyebrow: 'UCs',
        title: 'Unidades consumidoras',
        message: 'A tela de UCs sera conectada aos clientes e usinas nas proximas fases.'
      })
    },
    { path: '/usinas', render: createPlantsPage },
    {
      path: '/pendencias',
      render: () => createPlaceholderPage({
        eyebrow: 'Pendencias',
        title: 'Pendencias operacionais',
        message: 'A listagem de pendencias sera adicionada quando os fluxos de cliente e rateio estiverem definidos.'
      })
    },
    {
      path: '/agenda',
      render: createAgendaPage
    },
    { path: '/configuracoes', render: createSettingsPage }
  ];

  function resolveRoute(): Route {
    return routes.find((route) => route.path === window.location.pathname) ?? routes[0];
  }

  function redirect(path: string): void {
    window.history.replaceState({}, '', path);
    render();
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
      root.replaceChildren(createLoginPage(() => redirect('/')));
      return;
    }

    const route = resolveRoute();
    root.replaceChildren(route.render());
  }

  return {
    start() {
      window.addEventListener('popstate', render);
      render();
    }
  };
}