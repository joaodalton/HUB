import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { createInput, createSelectField } from '../components/formFields';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { createUser, getUsers, setUserActive, type UserPayload, type UserRole, type UserRow } from '../services/userService';

export function createUsersPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let users: UserRow[] = [];
  let loaded = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Configurações',
    title: 'Quem tem acesso ao HUB e com que papel'
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
      toast.success('Usuário criado.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível criar o usuário.');
    }
  }

  async function handleToggleActive(user: UserRow): Promise<void> {
    const willActivate = user.status !== 'ativo';

    try {
      await setUserActive(user.id, willActivate);
      toast.success(willActivate ? 'Usuário ativado.' : 'Usuário desativado.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar o usuário.');
    }
  }

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';

    // Modal so aparece ao clicar aqui -- antes o formulario de criacao ficava
    // sempre visivel embaixo da lista, mesmo sem ninguem pedir pra criar nada.
    const newUserButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newUserButton.append(createIcon('plus'), document.createTextNode('Novo usuário'));
    newUserButton.addEventListener('click', () => {
      document.body.appendChild(createUserModal(handleCreate));
    });

    pageActions.append(spacer, newUserButton);

    const panel = createElement('section', { className: 'settings-panel' });

    if (!loaded) {
      panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' }));
    } else if (users.length === 0) {
      panel.appendChild(createElement('p', {
        className: 'settings-hint',
        textContent: 'Nenhum usuário encontrado, ou sua conta não tem permissão pra ver essa lista (só administrador gerencia usuários).'
      }));
    } else {
      panel.appendChild(createUsersList(users, handleToggleActive));
    }

    content.replaceChildren(pageActions, panel);
  }
}

function createUsersList(users: UserRow[], onToggleActive: (user: UserRow) => void): HTMLElement {
  const list = createElement('dl', { className: 'settings-list compact' });

  users.forEach((user) => {
    const label = createElement('dt', { textContent: user.email });
    const valueRow = createElement('dd', { className: 'account-row' });
    const ativo = user.status === 'ativo';
    const roleBadge = createElement('span', {
      className: user.role === 'owner' || user.role === 'admin' ? 'provider-badge success' : 'provider-badge',
      textContent: roleLabel(user.role)
    });
    const statusBadge = createElement('span', {
      className: ativo ? 'provider-badge success' : 'provider-badge warning',
      textContent: ativo ? 'Ativo' : 'Inativo'
    });
    const toggleButton = createElement('button', {
      className: ativo ? 'danger-button' : 'secondary-button',
      textContent: ativo ? 'Desativar' : 'Ativar',
      type: 'button'
    });

    // Owner nao pode ser desativado (regra do backend tambem, ver
    // user_service.py::set_user_active) -- some o botao pra nao confundir.
    if (user.role === 'owner') toggleButton.remove();

    toggleButton.addEventListener('click', () => onToggleActive(user));

    valueRow.append(roleBadge, statusBadge);
    if (user.role !== 'owner') valueRow.appendChild(toggleButton);
    list.append(label, valueRow);
  });

  return list;
}

// Mesmo padrao de modal usado em Cliente/UC/Usina (overlay + client-form),
// pra ficar consistente com o resto do app em vez de inventar um estilo novo.
function createUserModal(onCreate: (data: UserPayload) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Novo usuário' });
  const heading = createElement('h2', { textContent: 'Criar usuário' });
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });
  const fields = createElement('div', { className: 'form-grid' });

  const nome = createInput('Nome', 'text', '', true);
  const email = createInput('Email', 'email', '', true);
  const senha = createInput('Senha provisória', 'password', '', true);
  const role = createSelectField('Papel', 'viewer', [
    { value: 'viewer', label: 'Visualizador' },
    { value: 'operator', label: 'Operacional' },
    { value: 'financial', label: 'Financeiro' },
    { value: 'admin', label: 'Administrador' }
  ]);

  const actions = createElement('div', { className: 'form-actions' });
  const submitButton = createElement('button', { textContent: 'Criar usuário', type: 'submit' });
  actions.appendChild(submitButton);

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(nome.field, email.field, senha.field, role.field);
  form.append(header, fields, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  closeButton.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) overlay.remove();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!nome.input.value.trim() || !email.input.value.trim() || !senha.input.value.trim()) {
      nome.input.reportValidity();
      email.input.reportValidity();
      senha.input.reportValidity();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Criando...';

    // Mesmo padrao ja usado em PlantCard/UcCard: onCreate trata seu proprio
    // erro (toast) e nao relança -- o modal fecha ao final independente do
    // resultado, consistente com o resto do app, nao e comportamento novo.
    await onCreate({
      nome: nome.input.value.trim(),
      email: email.input.value.trim(),
      senha: senha.input.value,
      role: role.select.value as UserPayload['role']
    });

    overlay.remove();
  });

  return overlay;
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
