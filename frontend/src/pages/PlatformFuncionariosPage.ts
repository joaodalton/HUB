import { createDataTable } from '../components/DataTable';
import { createInput } from '../components/formFields';
import { createIcon } from '../components/Icon';
import { createStatusBadge } from '../components/StatusBadge';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { createPlatformWorker, getPlatformWorkers, revokePlatformWorker, type PlatformWorker } from '../services/platformWorkerService';

export function createPlatformFuncionariosPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const toolbar = createElement('div', { className: 'platform-toolbar' });
  const newButton = createElement('button', { className: 'primary-button button-with-icon', type: 'button' });
  newButton.append(createIcon('plus'), document.createTextNode('Novo fiscal'));
  toolbar.appendChild(newButton);

  const formHost = createElement('div');
  const tableHost = createElement('div');
  content.append(toolbar, formHost, tableHost);

  let workers: PlatformWorker[] = [];
  let failed = false;

  const render = (loading = false): void => {
    tableHost.replaceChildren(createDataTable<PlatformWorker>({
      title: 'Funcionarios', eyebrow: 'Platform workers', rows: workers,
      state: loading ? 'loading' : failed ? 'error' : 'ready',
      stateTitle: failed ? 'Não foi possível carregar os funcionários.' : undefined,
      emptyMessage: 'Nenhum funcionário cadastrado.',
      errorAction: { label: 'Tentar novamente', onClick: load },
      columns: [
        { key: 'nome', label: 'Nome' },
        { key: 'email', label: 'Email' },
        { key: 'status', label: 'Status', render: (row) => createStatusBadge(row.status, row.status.toLowerCase().startsWith('ativ') ? 'success' : 'warning') },
        { key: 'action', label: 'Ação', align: 'right', render: createRevokeButton }
      ]
    }));
  };

  const load = (): void => {
    failed = false; render(true);
    void getPlatformWorkers().then((data) => { workers = data; render(); }).catch(() => { failed = true; render(); });
  };

  const createRevokeButton = (worker: PlatformWorker): HTMLElement => {
    const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    button.append(createIcon('trash'), document.createTextNode('Revogar'));
    button.addEventListener('click', () => {
      button.disabled = true;
      void revokePlatformWorker(worker.id)
        .then(() => { useToast().success('Funcionário revogado.'); load(); })
        .catch((error) => { button.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível revogar o funcionário.'); });
    });
    return button;
  };

  const openForm = (): void => {
    newButton.disabled = true;
    const form = createElement('form', { className: 'client-form' });
    const nome = createInput('Nome', 'text', '', true);
    nome.input.name = 'nome';
    const email = createInput('Email', 'email', '', true);
    email.input.name = 'email';
    const senha = createInput('Senha', 'password', '', true);
    senha.input.name = 'senha'; senha.input.minLength = 6;

    const submitButton = createElement('button', { type: 'submit', textContent: 'Criar' });
    const cancelButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
    cancelButton.addEventListener('click', closeForm);

    const actions = createElement('div', { className: 'form-actions' });
    actions.append(cancelButton, submitButton);
    form.append(nome.field, email.field, senha.field, actions);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      submitButton.disabled = true;
      void createPlatformWorker({ nome: nome.input.value, email: email.input.value, senha: senha.input.value })
        .then(() => { useToast().success('Funcionário criado.'); closeForm(); load(); })
        .catch((error) => { submitButton.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível criar o funcionário.'); });
    });

    formHost.replaceChildren(form);
  };

  const closeForm = (): void => { formHost.replaceChildren(); newButton.disabled = false; };

  newButton.addEventListener('click', openForm);
  load();

  return createPlatformLayout({ content, title: 'Funcionarios', description: 'Gerencie as contas de fiscais com acesso somente leitura à plataforma.' });
}
