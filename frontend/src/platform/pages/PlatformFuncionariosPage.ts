import { attachActionsRail, createDataTable } from '../../components/DataTable';
import { createInput } from '../../components/formFields';
import { createIcon } from '../../components/Icon';
import { createStatusBadge } from '../../components/StatusBadge';
import { createElement } from '../../dom';
import { useToast } from '../../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { createPlatformWorker, getPlatformWorkers, revokePlatformWorker, updatePlatformWorker, type PlatformWorker } from '../services/platformWorkerService';
import { t } from '../../services/i18nService';

function workerStatusLabel(status: string): string {
  return ({
    ativo: t('platform.funcionarios.statusAtivo'),
    inativo: t('platform.funcionarios.statusInativo')
  } as Record<string, string>)[status.toLowerCase()] ?? status;
}

export function createPlatformFuncionariosPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const toolbar = createElement('div', { className: 'platform-toolbar' });
  const newButton = createElement('button', { className: 'primary-button button-with-icon', type: 'button' });
  newButton.append(createIcon('plus'), document.createTextNode(t('platform.funcionarios.newButton')));
  toolbar.appendChild(newButton);

  const formHost = createElement('div');
  const tableHost = createElement('div');
  content.append(toolbar, formHost, tableHost);

  let workers: PlatformWorker[] = [];
  let failed = false;

  const render = (loading = false): void => {
    const panel = createDataTable<PlatformWorker>({
      title: t('platform.funcionarios.tableTitle'), eyebrow: t('platform.funcionarios.tableEyebrow'), rows: workers,
      state: loading ? 'loading' : failed ? 'error' : 'ready',
      stateTitle: failed ? t('platform.funcionarios.loadError') : undefined,
      emptyMessage: t('platform.funcionarios.emptyMessage'),
      errorAction: { label: t('platform.funcionarios.retry'), onClick: load },
      columns: [
        { key: 'id', label: t('platform.funcionarios.colId'), render: (worker) => `#${worker.id}` },
        { key: 'nome', label: t('platform.funcionarios.colNome') },
        { key: 'email', label: t('platform.funcionarios.colEmail') },
        { key: 'status', label: t('platform.funcionarios.colStatus'), render: (row) => createStatusBadge(workerStatusLabel(row.status), row.status.toLowerCase().startsWith('ativ') ? 'success' : 'warning') }
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
    button.append(createIcon('trash'), document.createTextNode(t('platform.funcionarios.deleteButton')));
    button.addEventListener('click', () => {
      button.disabled = true;
      void revokePlatformWorker(worker.id)
        .then(() => { useToast().success(t('platform.funcionarios.deletedSuccess')); load(); })
        .catch((error) => { button.disabled = false; useToast().error(error instanceof Error ? error.message : t('platform.funcionarios.deleteError')); });
    });
    return button;
  };

  const createEditButton = (worker: PlatformWorker): HTMLElement => {
    const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    button.append(createIcon('edit'), document.createTextNode(t('platform.funcionarios.editButton')));
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
    const nome = createInput(t('platform.funcionarios.fieldNome'), 'text', worker.nome, true);
    const email = createInput(t('platform.funcionarios.fieldEmail'), 'email', worker.email, true);
    const senha = createInput(t('platform.funcionarios.fieldSenhaOpcional'), 'password', '');
    senha.input.minLength = 6;

    const save = createElement('button', { type: 'submit', textContent: t('platform.funcionarios.saveButton') });
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('platform.funcionarios.cancelButton') });
    const close = (): void => overlay.remove();
    cancel.addEventListener('click', close);

    const formActions = createElement('div', { className: 'form-actions' });
    formActions.append(cancel, save);
    form.append(createElement('h2', { textContent: t('platform.funcionarios.editModalTitle') }), nome.field, email.field, senha.field, formActions);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      const data: { nome?: string; email?: string; senha?: string } = { nome: nome.input.value.trim(), email: email.input.value.trim() };
      if (senha.input.value) data.senha = senha.input.value;
      void updatePlatformWorker(worker.id, data)
        .then(() => { useToast().success(t('platform.funcionarios.updatedSuccess')); close(); load(); })
        .catch((error) => { save.disabled = false; useToast().error(error instanceof Error ? error.message : t('platform.funcionarios.updateError')); });
    });

    overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
    overlay.appendChild(form);
    return overlay;
  };

  const openForm = (): void => {
    newButton.disabled = true;
    const form = createElement('form', { className: 'client-form' });
    const nome = createInput(t('platform.funcionarios.fieldNome'), 'text', '', true);
    nome.input.name = 'nome';
    const email = createInput(t('platform.funcionarios.fieldEmail'), 'email', '', true);
    email.input.name = 'email';
    const senha = createInput(t('platform.funcionarios.fieldSenha'), 'password', '', true);
    senha.input.name = 'senha'; senha.input.minLength = 6;

    const submitButton = createElement('button', { type: 'submit', textContent: t('platform.funcionarios.createButton') });
    const cancelButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('platform.funcionarios.cancelButton') });
    cancelButton.addEventListener('click', closeForm);

    const actions = createElement('div', { className: 'form-actions' });
    actions.append(cancelButton, submitButton);
    form.append(nome.field, email.field, senha.field, actions);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      submitButton.disabled = true;
      void createPlatformWorker({ nome: nome.input.value, email: email.input.value, senha: senha.input.value })
        .then(() => { useToast().success(t('platform.funcionarios.createdSuccess')); closeForm(); load(); })
        .catch((error) => { submitButton.disabled = false; useToast().error(error instanceof Error ? error.message : t('platform.funcionarios.createError')); });
    });

    formHost.replaceChildren(form);
  };

  const closeForm = (): void => { formHost.replaceChildren(); newButton.disabled = false; };

  newButton.addEventListener('click', openForm);
  load();

  return createPlatformLayout({ content, title: t('platform.funcionarios.title'), description: t('platform.funcionarios.description') });
}
