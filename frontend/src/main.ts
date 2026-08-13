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
    // Mesma decisao de nunca mandar dado pessoal de cliente pro Sentry sem
    // revisar antes -- userInfo/httpBodies e a forma atual dessa opcao no
    // SDK (sendDefaultPii e o nome antigo, ainda funciona, mas o dashboard
    // do Sentry agora sugere esse formato).
    dataCollection: {
      userInfo: false,
      httpBodies: []
    }
  });
}

const app = document.querySelector<HTMLDivElement>('#app');

if (!app) {
  throw new Error('Elemento #app nao encontrado.');
}

const router = createRouter(app);

createErrorBoundary(() => router.start());