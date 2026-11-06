import './styles/app.css';
import { initializeTheme } from './services/themeService';
import { createErrorBoundary } from './components/ErrorBoundary';
import { createCheckoutPage } from './pages/CheckoutPage';

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) {
  throw new Error('Elemento #app nao encontrado.');
}

initializeTheme();
createErrorBoundary(() => {
  app.replaceChildren(createCheckoutPage());
});
