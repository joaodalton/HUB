import { showToast } from './Toast';

export function createErrorBoundary(render: () => void): void {
  window.addEventListener('error', () => {
    showToast('Ocorreu um erro inesperado na interface.', 'error');
  });

  window.addEventListener('unhandledrejection', () => {
    showToast('Nao foi possivel concluir a operacao.', 'error');
  });

  try {
    render();
  } catch {
    showToast('Nao foi possivel carregar o HUB.', 'error');
  }
}
