export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  // Prefixo de versao da API -- centralizado aqui pra so existir 1 lugar pra mudar
  // quando a v2 chegar. apiClient.ts e googleAccountService.ts (unicos lugares que
  // tocam config.apiBaseUrl direto) o aplicam antes do path de cada rota.
  apiPrefix: '/api/v1',
  // Vazio desliga o Sentry no frontend -- seguro rodar `npm run dev` local
  // sem nenhuma variavel setada.
  sentryDsn: import.meta.env.VITE_SENTRY_DSN ?? '',
  sentryEnvironment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? 'development'
};
