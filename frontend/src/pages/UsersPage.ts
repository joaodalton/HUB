import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { createInput, createSelectField } from '../components/formFields';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createUser,
  deleteUser,
  getUsers,
  updateUser,
  type UserPayload,
  type UserRole,
  type UserRow
} from '../services/userService';

export function createUsersPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let users: UserRow[] = [];
  let loaded = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Configurações',
    title: 'Gerenciar usuários'
  });

  loadUsers();

  return layout;

  async function loadUsers(): Promise<void> {
    loading.show();
    try {
      users = await getUsers();
    } catch {
      users = [];
    } finally {
      loaded = true;
      loading.hide();
      renderContent();
    }
  }

  async function handleCreate(data: UserPayload): Promise<void> {
    try {
      await createUser(data);
      toast.success('Usuário criado com sucesso.');
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

  async function handleDelete(user: UserRow): Promise<void> {
    if (!confirm(`Tem certeza que deseja excluir o usuário "${user.nome}"?\n\nEsta ação não pode ser desfeita.`)) {
      return;
    }

    try {
      await deleteUser(user.id);
      toast.success('Usuário excluído com sucesso.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível excluir o usuário.');
    }
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
      panel.appendChild(createUsersTable(users, handleUpdate, handleDelete));
    }

    content.replaceChildren(pageActions, panel);
  }
}

function createUsersTable(
  users: UserRow[],
  onUpdate: (id: number, data: Partial<UserPayload>) => Promise<void>,
  onDelete: (user: UserRow) => Promise<void>
): HTMLElement {
  const wrapper = createElement('div', { className: 'table-wrap' });
  const table = createElement('table', { className: 'data-table' });

  const thead = createElement('thead');
  thead.innerHTML = `
    <tr>
      <th>Nome</th>
      <th>Email</th>
      <th>Senha</th>
      <th>Papel</th>
      <th>Status</th>
      <th class="align-right">Ações</th>
    </tr>
  `;

  const tbody = createElement('tbody');

  users.forEach((user) => {
    const row = createElement('tr');

    // Nome
    const nameCell = createElement('td', { textContent: user.nome });

    // Email
    const emailCell = createElement('td', { textContent: user.email });

    // Senha com toggle
    const passwordCell = createElement('td');
    const passwordWrapper = createElement('div', { className: 'password-cell' });

    const passwordText = createElement('span', {
      className: 'password-text',
      textContent: '••••••••'
    });

    const toggleBtn = createElement('button', {
      className: 'password-toggle',
      type: 'button',
      title: 'Mostrar senha'
    });
    toggleBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>`;

    toggleBtn.addEventListener('click', () => {
      const isHidden = passwordText.textContent === '••••••••';
      passwordText.textContent = isHidden ? 'Senha oculta' : '••••••••';
      toggleBtn.innerHTML = isHidden
        ? `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>`
        : `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>`;
      toggleBtn.title = isHidden ? 'Ocultar senha' : 'Mostrar senha';
    });

    passwordWrapper.append(passwordText, toggleBtn);
    passwordCell.appendChild(passwordWrapper);

    // Papel
    const roleCell = createElement('td');
    const roleBadge = createElement('span', {
      className: `status-badge ${getRoleBadgeClass(user.role)}`,
      textContent: roleLabel(user.role)
    });
    roleCell.appendChild(roleBadge);

    // Status
    const statusCell = createElement('td');
    const statusDot = createElement('span', {
      className: user.status === 'ativo' ? 'status-dot status-success' : 'status-dot status-danger'
    });
    const statusText = createElement('span', { textContent: user.status === 'ativo' ? 'Ativo' : 'Inativo' });
    statusCell.append(statusDot, statusText);

    // Ações
    const actionsCell = createElement('td');
    const actionsWrapper = createElement('div', { className: 'table-actions' });

    // Editar
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

    // Excluir
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
      deleteBtn.addEventListener('click', () => onDelete(user));
      actionsWrapper.append(editBtn, deleteBtn);
    } else {
      actionsWrapper.appendChild(editBtn);
    }

    actionsCell.appendChild(actionsWrapper);
    row.append(nameCell, emailCell, passwordCell, roleCell, statusCell, actionsCell);
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  wrapper.appendChild(table);
  return wrapper;
}

function createUserModal(
  user: UserRow | null,
  onCreate: ((data: UserPayload) => Promise<void>) | null,
  onUpdate: ((id: number, data: Partial<UserPayload>) => Promise<void>) | null
): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });

  const isEdit = user !== null;
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
  const role = createSelectField('Papel', user?.role || 'viewer', [
    { value: 'viewer', label: 'Visualizador' },
    { value: 'operator', label: 'Operacional' },
    { value: 'financial', label: 'Financeiro' },
    { value: 'admin', label: 'Administrador' }
  ]);

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
      useToast().error('Preencha todos os campos obrigatórios.');
      return;
    }

    if (!isEdit && !senha.input.value.trim()) {
      senha.input.reportValidity();
      return;
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
        await onUpdate(user.id, data);
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
      useToast().error(error instanceof Error ? error.message : 'Ocorreu um erro.');
    }
  });

  return overlay;
}

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
