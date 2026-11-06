import './styles/app.css';
import { initializeTheme } from './services/themeService';
import { createErrorBoundary } from './components/ErrorBoundary';
import { createCadastroEmpresaPage } from './pages/CadastroEmpresaPage';

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) {
  throw new Error('Elemento #app nao encontrado.');
}

initializeTheme();
createErrorBoundary(() => {
  app.replaceChildren(createCadastroEmpresaPage());
});
