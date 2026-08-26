import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { createInput, createSelectField } from '../components/formFields';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createUser,
  deleteUser,
  getUsers,
  resetUserPassword,
  setUserActive,
  updateUser,
  type UserPayload,
  type UserRole,
  type UserRow
} from '../services/userService';

export function createUsersPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let users: UserRow[] = [];
  let loaded = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Configurações',
    title: 'Gerenciar usuários'
  });

  // ----------------------------------------------------------------------
  // Functions
  // ----------------------------------------------------------------------

  async function loadUsers(): Promise<void> {
    try {
      users = await getUsers();
      loaded = true;
    } catch {
      users = [];
      loaded = true;
    }
    renderContent();
  }

  async function handleCreate(data: UserPayload): Promise<void> {
    try {
      const result = await createUser(data);
      const msg = (result as any)?.message;
      const isInvite = !!(result as any)?.inviteId || !!(result as any)?.inviteCode;
      toast.success(isInvite ? (msg || 'Convite enviado. O usuário receberá um email para definir sua senha.') : 'Usuário criado com sucesso.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível criar o usuário.');
    }
  }

  async function handleUpdate(id: number, data: Partial<UserPayload>): Promise<void> {
    try {
      await updateUser(id, data);
      toast.success('Usuário atualizado com sucesso.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar o usuário.');
    }
  }

  async function handleDelete(user: UserRow, deleteBtn: HTMLElement): Promise<void> {
    const overlay = createConfirmDeleteOverlay(user, async () => {
      try {
        await deleteUser(user.id);
        toast.success('Usuário excluído com sucesso.');
        await loadUsers();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível excluir o usuário.');
      }
    }, deleteBtn);
    document.body.appendChild(overlay);
  }

  async function handleResetPassword(user: UserRow): Promise<void> {
    const overlay = createResetPasswordOverlay(user, async (novaSenha, confirmacao) => {
      try {
        await resetUserPassword(user.id, novaSenha, confirmacao);
        toast.success('Senha redefinida com sucesso.');
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível redefinir a senha.');
      }
    });
    document.body.appendChild(overlay);
  }

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });

    const newUserButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newUserButton.append(createIcon('plus'), document.createTextNode('Novo usuário'));
    newUserButton.addEventListener('click', () => {
      document.body.appendChild(createUserModal(null, handleCreate, handleUpdate));
    });

    pageActions.appendChild(newUserButton);

    const panel = createElement('section', { className: 'data-panel' });

    if (!loaded) {
      panel.appendChild(createElement('div', { className: 'loading-state', textContent: 'Carregando usuários...' }));
    } else if (users.length === 0) {
      panel.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">${createIcon('clients').outerHTML}</div>
          <p>Nenhum usuário encontrado</p>
          <span>Crie seu primeiro usuário clicando em "Novo usuário"</span>
        </div>
      `;
    } else {
      panel.appendChild(createUsersTable(users, handleUpdate, handleDelete, handleResetPassword));
    }

    content.replaceChildren(pageActions, panel);
  }

  loadUsers();
  return layout;
}

// ----------------------------------------------------------------------
// Tabela de usuários
// ----------------------------------------------------------------------

function createUsersTable(
  users: UserRow[],
  onUpdate: (id: number, data: Partial<UserPayload>) => Promise<void>,
  onDelete: (user: UserRow, deleteBtn: HTMLElement) => Promise<void>,
  onResetPassword: (user: UserRow) => Promise<void>
): HTMLElement {
  const wrapper = createElement('div', { className: 'table-wrap' });
  const table = createElement('table', { className: 'data-table' });

  const thead = createElement('thead');
  thead.innerHTML = `
    <tr>
      <th>Nome</th>
      <th>Email</th>
      <th>Papel</th>
      <th>Status</th>
      <th>Redefinir senha</th>
      <th class="align-right">Ações</th>
    </tr>
  `;

  const tbody = createElement('tbody');

  users.forEach((user) => {
    const row = createElement('tr');

    const tdNome = createElement('td', { textContent: user.nome });
    row.appendChild(tdNome);

    const tdEmail = createElement('td', { textContent: user.email });
    row.appendChild(tdEmail);

    const tdRole = createElement('td');
    const roleBadge = createElement('span', {
      className: `status-badge ${getRoleBadgeClass(user.role)}`,
      textContent: roleLabel(user.role)
    });
    tdRole.appendChild(roleBadge);
    row.appendChild(tdRole);

    const tdStatus = createElement('td');
    const statusText = user.status === 'ativo' ? 'Ativo' : 'Inativo';
    const statusDotClass = user.status === 'ativo' ? 'status-dot status-success' : 'status-dot status-danger';
    const statusDot = createElement('span', { className: statusDotClass });
    const statusLabel = createElement('span', { textContent: statusText });
    tdStatus.append(statusDot, statusLabel);
    row.appendChild(tdStatus);

    const tdReset = createElement('td');
    const resetBtn = createElement('button', {
      className: 'icon-button',
      type: 'button',
      title: 'Redefinir senha'
    });
    resetBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>`;
    resetBtn.addEventListener('click', () => onResetPassword(user));
    tdReset.appendChild(resetBtn);
    row.appendChild(tdReset);

    const tdActions = createElement('td');
    const actionsWrapper = createElement('div', { className: 'table-actions' });

    const editBtn = createElement('button', {
      className: 'icon-button',
      type: 'button',
      title: 'Editar usuário'
    });
    editBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>`;
    editBtn.addEventListener('click', () => {
      document.body.appendChild(createUserModal(user, null, onUpdate));
    });

    if (user.role !== 'owner') {
      const deleteBtn = createElement('button', {
        className: 'icon-button danger',
        type: 'button',
        title: 'Excluir usuário'
      });
      deleteBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
      </svg>`;
      deleteBtn.addEventListener('click', () => onDelete(user, deleteBtn));
      actionsWrapper.append(editBtn, deleteBtn);
    } else {
      actionsWrapper.appendChild(editBtn);
    }

    tdActions.appendChild(actionsWrapper);
    row.appendChild(tdActions);

    tbody.appendChild(row);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
  wrapper.appendChild(table);
  return wrapper;
}

// ----------------------------------------------------------------------
// Modal de usuário (criar/editar)
// ----------------------------------------------------------------------

function createUserModal(
  user: UserRow | null,
  onCreate: ((data: UserPayload) => Promise<void>) | null,
  onUpdate: ((id: number, data: Partial<UserPayload>) => Promise<void>) | null
): HTMLElement {
  const isEdit = user !== null;
  const toast = useToast();
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });

  const title = isEdit ? 'Editar usuário' : 'Novo usuário';

  const header = createElement('div', { className: 'form-header' });
  const titleDiv = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Usuários' });
  const heading = createElement('h2', { textContent: title });
  const closeButton = createElement('button', {
    className: 'icon-button',
    type: 'button',
    title: 'Fechar'
  });
  closeButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>`;

  const fields = createElement('div', { className: 'form-grid' });

  const nome = createInput('Nome', 'text', user?.nome || '', true);
  const email = createInput('Email', 'email', user?.email || '', true);
  const senha = createInput(
    isEdit ? 'Nova senha (opcional)' : 'Senha provisória',
    'password',
    '',
    !isEdit
  );

  // Campo de status (apenas em edição)
  if (isEdit) {
    const statusContainer = createElement('div', { className: 'form-field' });
    const statusLabel = createElement('span', { textContent: 'Status' });
    statusContainer.appendChild(statusLabel);

    const statusBadge = createElement('span', {
      className: `status-badge ${user.status === 'ativo' ? 'tone-success' : 'tone-danger'}`,
      textContent: user.status === 'ativo' ? 'Ativo' : 'Inativo'
    });
    statusContainer.appendChild(statusBadge);

    // Checkbox "desativar" (criado manualmente porque type checkbox não é suportado por createElement)
    const deactivateContainer = createElement('div', { className: 'checkbox-field' });
    const deactivateCheckbox = document.createElement('input');
    deactivateCheckbox.type = 'checkbox';
    deactivateCheckbox.id = 'deactivate-user-check';
    deactivateCheckbox.checked = user.status === 'inativo';
    const deactivateLabel = createElement('label', { className: 'checkbox-label' });
    deactivateLabel.htmlFor = 'deactivate-user-check';
    deactivateLabel.textContent = 'Desativar usuário (impede login)';
    deactivateContainer.append(deactivateCheckbox, deactivateLabel);
    statusContainer.appendChild(deactivateContainer);

    fields.appendChild(statusContainer);
  }

  const role = createSelectField(
    'Papel',
    user?.role || 'viewer',
    [
      { value: 'viewer', label: 'Visualizador' },
      { value: 'operator', label: 'Operacional' },
      { value: 'financial', label: 'Financeiro' },
      { value: 'admin', label: 'Administrador' }
    ]
  );

  // Ações do formulário
  const actions = createElement('div', { className: 'form-actions' });
  const cancelBtn = createElement('button', {
    className: 'secondary-button',
    textContent: 'Cancelar',
    type: 'button'
  });
  const submitBtn = createElement('button', {
    textContent: isEdit ? 'Salvar alterações' : 'Criar usuário',
    type: 'submit'
  });
  actions.append(cancelBtn, submitBtn);

  titleDiv.append(eyebrow, heading);
  header.append(titleDiv, closeButton);
  fields.append(nome.field, email.field, senha.field, role.field);
  form.append(header, fields, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  closeButton.addEventListener('click', () => overlay.remove());
  cancelBtn.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.remove();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!nome.input.value.trim() || !email.input.value.trim()) {
      toast.error('Preencha todos os campos obrigatórios.');
      return;
    }

    if (!isEdit && senha.input.value.trim()) {
      if (senha.input.value.length < 6) {
        senha.input.reportValidity();
        return;
      }
    }

    submitBtn.disabled = true;
    submitBtn.textContent = isEdit ? 'Salvando...' : 'Criando...';

    try {
      if (isEdit && onUpdate) {
        const data: Partial<UserPayload> = {
          nome: nome.input.value.trim(),
          email: email.input.value.trim(),
          role: role.select.value as UserPayload['role']
        };
        if (senha.input.value.trim()) {
          data.senha = senha.input.value;
        }

        // Desativar usuário usando endpoint específico
        const deactivateCheckbox = document.getElementById('deactivate-user-check') as HTMLInputElement | null;
        const ativo = deactivateCheckbox ? deactivateCheckbox.checked : user?.status === 'ativo';

        if (user && ativo === false) {
          await setUserActive(user.id, false);
          toast.success('Usuário desativado com sucesso.');
        } else if (user && ativo === true && user.status === 'inativo') {
          await setUserActive(user.id, true);
          toast.success('Usuário ativado com sucesso.');
        } else {
          await onUpdate(user.id, data);
          toast.success('Usuário atualizado com sucesso.');
        }
      } else if (onCreate) {
        await onCreate({
          nome: nome.input.value.trim(),
          email: email.input.value.trim(),
          senha: senha.input.value,
          role: role.select.value as UserPayload['role']
        });
      }
      overlay.remove();
    } catch (error) {
      submitBtn.disabled = false;
      submitBtn.textContent = isEdit ? 'Salvar alterações' : 'Criar usuário';
      toast.error(error instanceof Error ? error.message : 'Ocorreu um erro.');
    }
  });

  return overlay;
}

// ----------------------------------------------------------------------
// Overlay de confirmação de exclusão (em cima do botão, mais fail)
// ----------------------------------------------------------------------

function createConfirmDeleteOverlay(
  user: UserRow,
  onConfirm: () => Promise<void>,
  anchor: HTMLElement
): HTMLElement {
  const overlay = createElement('div', { className: 'confirm-overlay' });
  const toast = useToast();
  const box = createElement('div', { className: 'confirm-box danger' });
  const message = createElement('p', { textContent: `Tem certeza que deseja excluir o usuário "${user.nome}"?` });
  const subtitle = createElement('p', { className: 'confirm-subtitle', textContent: 'Esta ação não pode ser desfeita.' });
  const actions = createElement('div', { className: 'confirm-actions' });

  const cancelBtn = createElement('button', { className: 'secondary-button', textContent: 'Cancelar', type: 'button' });
  const confirmBtn = createElement('button', { className: 'danger-button fail', textContent: 'Confirmar exclusão', type: 'button' });

  cancelBtn.addEventListener('click', () => overlay.remove());

  confirmBtn.addEventListener('click', async () => {
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Excluindo...';
    try {
      await onConfirm();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível excluir.');
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Confirmar exclusão';
      overlay.remove();
    }
  });

  actions.append(cancelBtn, confirmBtn);
  box.append(message, subtitle, actions);
  overlay.appendChild(box);

  // Posicionar em cima do botão de excluir
  const rect = anchor.getBoundingClientRect();
  overlay.style.position = 'fixed';
  overlay.style.top = `${rect.top - 10}px`;
  overlay.style.left = `${rect.left + rect.width / 2}px`;
  overlay.style.transform = 'translate(-50%, -100%)';
  overlay.style.zIndex = '9999';
  overlay.style.pointerEvents = 'auto';

  return overlay;
}

// ----------------------------------------------------------------------
// Overlay de redefinição de senha
// ----------------------------------------------------------------------

function createResetPasswordOverlay(
  user: UserRow,
  onConfirm: (novaSenha: string, confirmacao: string) => Promise<void>
): HTMLElement {
  const overlay = createElement('div', { className: 'confirm-overlay' });
  const toast = useToast();
  const box = createElement('div', { className: 'confirm-box info' });
  const title = createElement('h3', { textContent: `Redefinir senha de ${user.nome}` });
  const message = createElement('p', { textContent: 'Digite a nova senha para este usuário.' });
  const form = createElement('form', { className: 'confirm-form' });

  const novaSenhaField = createElement('div', { className: 'form-field' });
  const novaSenhaLabel = createElement('label', { textContent: 'Nova senha', className: 'form-label' });
  const novaSenhaInput = document.createElement('input');
  novaSenhaInput.type = 'password';
  novaSenhaInput.className = 'form-input';
  novaSenhaField.append(novaSenhaLabel, novaSenhaInput);

  const confirmacaoField = createElement('div', { className: 'form-field' });
  const confirmacaoLabel = createElement('label', { textContent: 'Confirmar senha', className: 'form-label' });
  const confirmacaoInput = document.createElement('input');
  confirmacaoInput.type = 'password';
  confirmacaoInput.className = 'form-input';
  confirmacaoField.append(confirmacaoLabel, confirmacaoInput);

  const errorSpan = createElement('span', { className: 'confirm-error', textContent: '' });

  const actions = createElement('div', { className: 'confirm-actions' });
  const cancelBtn = createElement('button', { className: 'secondary-button', textContent: 'Cancelar', type: 'button' });
  const saveBtn = createElement('button', { className: 'primary-button', textContent: 'Salvar', type: 'submit' });
  actions.append(cancelBtn, saveBtn);

  form.append(novaSenhaField, confirmacaoField, errorSpan, actions);
  box.append(title, message, form);
  overlay.appendChild(box);

  overlay.style.position = 'fixed';
  overlay.style.top = '0';
  overlay.style.left = '0';
  overlay.style.right = '0';
  overlay.style.bottom = '0';
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';
  overlay.style.zIndex = '9999';

  cancelBtn.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.remove();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorSpan.textContent = '';

    const nova = novaSenhaInput.value.trim();
    const conf = confirmacaoInput.value.trim();

    if (!nova || !conf) {
      errorSpan.textContent = 'Preencha todos os campos.';
      return;
    }

    if (nova.length < 6) {
      errorSpan.textContent = 'A senha deve ter pelo menos 6 caracteres.';
      return;
    }

    if (nova !== conf) {
      errorSpan.textContent = 'As senhas não coincidem.';
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Salvando...';
    try {
      await onConfirm(nova, conf);
      toast.success('Senha redefinida com sucesso.');
      overlay.remove();
    } catch (err) {
      errorSpan.textContent = err instanceof Error ? err.message : 'Não foi possível redefinir.';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Salvar';
    }
  });

  return overlay;
}

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------

function getRoleBadgeClass(role: UserRole): string {
  switch (role) {
    case 'owner':
    case 'admin':
      return 'tone-info';
    case 'operator':
      return 'tone-warning';
    case 'financial':
      return 'tone-success';
    default:
      return '';
  }
}

function roleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    owner: 'Proprietário',
    admin: 'Administrador',
    operator: 'Operacional',
    financial: 'Financeiro',
    viewer: 'Visualizador'
  };
  return labels[role];
}
