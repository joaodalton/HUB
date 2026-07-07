import { setGlobalLoading } from '../components/Loading';

export function useGlobalLoading() {
  return {
    show: () => setGlobalLoading(true),
    hide: () => setGlobalLoading(false),
    set: setGlobalLoading
  };
}
