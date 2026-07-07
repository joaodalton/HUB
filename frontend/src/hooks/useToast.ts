import { showToast } from '../components/Toast';

export function useToast() {
  return {
    success: (message: string) => showToast(message, 'success'),
    error: (message: string) => showToast(message, 'error'),
    info: (message: string) => showToast(message, 'info')
  };
}
