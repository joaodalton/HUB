import { showToast, type ToastAction } from '../components/Toast';

export function useToast() {
  return {
    success: (message: string, action?: ToastAction) => showToast(message, 'success', action),
    error: (message: string) => showToast(message, 'error'),
    warning: (message: string) => showToast(message, 'warning'),
    info: (message: string) => showToast(message, 'info')
  };
}
