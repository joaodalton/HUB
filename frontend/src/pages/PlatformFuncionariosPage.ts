import { attachActionsRail, createDataTable } from '../components/DataTable';
import { createInput } from '../components/formFields';
import { createIcon } from '../components/Icon';
import { createStatusBadge } from '../components/StatusBadge';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { createPlatformWorker, getPlatformWorkers, revokePlatformWorker, updatePlatformWorker, type PlatformWorker } from '../services/platformWorkerService';

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
    const panel = createDataTable<PlatformWorker>({
      title: 'Funcionarios', eyebrow: 'Platform workers', rows: workers,
      state: loading ? 'loading' : failed ? 'error' : 'ready',
      stateTitle: failed ? 'Não foi possível carregar os funcionários.' : undefined,
      emptyMessage: 'Nenhum funcionário cadastrado.',
      errorAction: { label: 'Tentar novamente', onClick: load },
      columns: [
        { key: 'id', label: 'ID', render: (worker) => `#${worker.id}` },
        { key: 'nome', label: 'Nome' },
        { key: 'email', label: 'Email' },
        { key: 'status', label: 'Status', render: (row) => createStatusBadge(row.status, row.status.toLowerCase().startsWith('ativ') ? 'success' : 'warning') }
      ]
    });
    attachActionsRail(panel, workers, createActionButtons);
    tableHost.replaceChildren(panel);
  };

  const load = (): void => {
    failed = false; render(true);
    void getPlatformWorkers().then((data) => { workers = data; render(); }).catch(() => { failed = true; render(); });
  };

  const createRevokeButton = (worker: PlatformWorker): HTMLElement => {
    const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    button.append(createIcon('trash'), document.createTextNode('Excluir'));
    button.addEventListener('click', () => {
      button.disabled = true;
      void revokePlatformWorker(worker.id)
        .then(() => { useToast().success('Funcionário excluído.'); load(); })
        .catch((error) => { button.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível excluir o funcionário.'); });
    });
    return button;
  };

  const createEditButton = (worker: PlatformWorker): HTMLElement => {
    const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    button.append(createIcon('edit'), document.createTextNode('Editar'));
    button.addEventListener('click', () => document.body.appendChild(createEditModal(worker)));
    return button;
  };

  const createActionButtons = (worker: PlatformWorker): HTMLElement => {
    const wrap = createElement('div', { className: 'table-row-actions' });
    wrap.append(createEditButton(worker), createRevokeButton(worker));
    return wrap;
  };

  const createEditModal = (worker: PlatformWorker): HTMLElement => {
    const overlay = createElement('section', { className: 'modal-overlay' });
    const form = createElement('form', { className: 'client-card client-form' });
    const nome = createInput('Nome', 'text', worker.nome, true);
    const email = createInput('Email', 'email', worker.email, true);
    const senha = createInput('Nova senha (opcional)', 'password', '');
    senha.input.minLength = 6;

    const save = createElement('button', { type: 'submit', textContent: 'Salvar' });
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
    const close = (): void => overlay.remove();
    cancel.addEventListener('click', close);

    const formActions = createElement('div', { className: 'form-actions' });
    formActions.append(cancel, save);
    form.append(createElement('h2', { textContent: 'Editar funcionário' }), nome.field, email.field, senha.field, formActions);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      const data: { nome?: string; email?: string; senha?: string } = { nome: nome.input.value.trim(), email: email.input.value.trim() };
      if (senha.input.value) data.senha = senha.input.value;
      void updatePlatformWorker(worker.id, data)
        .then(() => { useToast().success('Funcionário atualizado.'); close(); load(); })
        .catch((error) => { save.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível atualizar o funcionário.'); });
    });

    overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
    overlay.appendChild(form);
    return overlay;
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
