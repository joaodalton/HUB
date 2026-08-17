import './styles/app.css';

import * as Sentry from '@sentry/browser';

import { createErrorBoundary } from './components/ErrorBoundary';
import { createRouter } from './services/router';
import { config } from './services/config';

// Sem DSN, Sentry.init com dsn vazio nao manda nada -- seguro em dev sem
// nenhuma variavel setada. sendDefaultPii false: mesma decisao consciente
// do backend, nao manda dado pessoal do cliente sem revisar isso depois.
if (config.sentryDsn) {
  Sentry.init({
    dsn: config.sentryDsn,
    environment: config.sentryEnvironment,
    tracesSampleRate: 0.1,
    // Nunca mandar dado pessoal de cliente pro Sentry sem revisar antes --
    // sendDefaultPii e a opcao de verdade do SDK v8 (@sentry/browser); nao
    // existe "dataCollection" nessa versao, foi engano de outra sessao.
    sendDefaultPii: false
  });
}

const app = document.querySelector<HTMLDivElement>('#app');

if (!app) {
  throw new Error('Elemento #app nao encontrado.');
}

const router = createRouter(app);

createErrorBoundary(() => router.start());