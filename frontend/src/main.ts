import './styles/app.css';

import { createErrorBoundary } from './components/ErrorBoundary';
import { createRouter } from './services/router';

const app = document.querySelector<HTMLDivElement>('#app');

if (!app) {
  throw new Error('Elemento #app nao encontrado.');
}

const router = createRouter(app);

createErrorBoundary(() => router.start());
