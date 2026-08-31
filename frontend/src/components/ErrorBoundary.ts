import * as Sentry from '@sentry/browser';

import { showToast } from './Toast';

export function createErrorBoundary(render: () => void): void {
  window.addEventListener('error', (event) => {
    Sentry.captureException(event.error ?? event.message);
    showToast('Ocorreu um erro inesperado na interface.', 'error');
  });

  window.addEventListener('unhandledrejection', (event) => {
    Sentry.captureException(event.reason);
    showToast('Nao foi possivel concluir a operacao.', 'error');
  });

  try {
    render();
  } catch (error) {
    Sentry.captureException(error);
    showToast('Nao foi possivel carregar o HUB.', 'error');
  }
}
