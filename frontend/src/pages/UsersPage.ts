import { createIcon } from '../components/Icon';
import { createInput, createSelectField } from '../components/formFields';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { createUser, getUsers, setUserActive, type UserPayload, type UserRole, type UserRow } from '../services/userService';

export function createUsersPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let users: UserRow[] = [];
  let loaded = false;
  let loadError = '';
  const layout = createBaseLayout({ content, eyebrow: 'Configurações', title: 'Gerenciar usuários' });
  renderContent();
  if (canManageUsers()) void loadUsers();
  return layout;

  function renderContent(): void {
    if (!canManageUsers()) {
      const denied = createElement('section', { className: 'data-panel empty-state' });
      denied.append(createIcon('lock', 'empty-state-icon'), createElement('strong', { textContent: 'Acesso não permitido' }), createElement('span', { textContent: 'Apenas proprietários e administradores podem gerenciar usuários.' }));
      content.replaceChildren(denied);
      return;
    }
    const pageActions = createElement('div', { className: 'page-actions' });
    const newUserButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newUserButton.append(createIcon('plus'), document.createTextNode('Criar acesso direto'));
    newUserButton.addEventListener('click', () => document.body.appendChild(createUserModal(handleCreate)));
    pageActions.appendChild(newUserButton);
    const panel = createElement('section', { className: 'data-panel' });
    if (!loaded) panel.appendChild(createElement('div', { className: 'loading-state', textContent: 'Carregando usuários...' }));
    else if (loadError) {
      const error = createElement('div', { className: 'empty-state' });
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
      retry.addEventListener('click', () => void loadUsers());
      error.append(createElement('strong', { textContent: 'Não foi possível carregar usuários' }), createElement('span', { textContent: loadError }), retry);
      panel.appendChild(error);
    } else if (users.length === 0) {
      const empty = createElement('div', { className: 'empty-state' });
      empty.append(createIcon('clients', 'empty-state-icon'), createElement('p', { textContent: 'Nenhum usuário encontrado' }), createElement('span', { textContent: 'Crie o primeiro acesso direto para esta empresa.' }));
      panel.appendChild(empty);
    } else panel.appendChild(createUsersTable(users, handleSetActive));
    content.replaceChildren(pageActions, panel);
  }

  async function loadUsers(): Promise<void> {
    loaded = false; loadError = ''; renderContent(); loading.show();
    try { users = await getUsers(); }
    catch (error) { users = []; loadError = error instanceof Error ? error.message : 'Tente novamente em instantes.'; }
    finally { loaded = true; loading.hide(); renderContent(); }
  }

  async function handleCreate(data: UserPayload): Promise<void> {
    loading.show();
    try { await createUser(data); toast.success('Usuário criado. Ele deverá trocar a senha no primeiro acesso.'); await loadUsers(); }
    catch (error) { throw error instanceof Error ? error : new Error('Não foi possível criar o usuário.'); }
    finally { loading.hide(); }
  }

  async function handleSetActive(user: UserRow, ativo: boolean): Promise<void> {
    const action = ativo ? 'ativar' : 'desativar';
    if (!window.confirm(`Deseja ${action} o acesso de ${user.nome}?`)) return;
    loading.show();
    try {
      const updated = await setUserActive(user.id, ativo);
      users = users.map((item) => item.id === updated.id ? updated : item);
      toast.success(ativo ? 'Usuário ativado.' : 'Usuário desativado.');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível alterar o acesso.'); }
    finally { loading.hide(); renderContent(); }
  }
}

function createUsersTable(users: UserRow[], onSetActive: (user: UserRow, ativo: boolean) => Promise<void>): HTMLElement {
  const wrapper = createElement('div', { className: 'table-wrap' });
  const table = createElement('table', { className: 'data-table' });
  const head = createElement('thead');
  const headRow = createElement('tr');
  ['Nome', 'E-mail', 'Papel', 'Status', 'Ações'].forEach((label) => headRow.appendChild(createElement('th', { textContent: label })));
  head.appendChild(headRow);
  const body = createElement('tbody');
  users.forEach((user) => {
    const row = createElement('tr');
    const role = createElement('span', { className: `status-badge ${getRoleBadgeClass(user.role)}`, textContent: roleLabel(user.role) });
    const roleCell = createElement('td'); roleCell.appendChild(role);
    const status = createElement('td'); status.append(createElement('span', { className: user.status === 'ativo' ? 'status-dot status-success' : 'status-dot status-danger' }), document.createTextNode(user.status === 'ativo' ? ' Ativo' : ' Inativo'));
    const actionCell = createElement('td');
    if (user.role === 'owner') actionCell.appendChild(createElement('span', { className: 'settings-hint', textContent: 'Protegido' }));
    else {
      const nextActive = user.status !== 'ativo';
      const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: nextActive ? 'Ativar' : 'Desativar' });
      button.addEventListener('click', () => void onSetActive(user, nextActive));
      actionCell.appendChild(button);
    }
    row.append(createElement('td', { textContent: user.nome }), createElement('td', { textContent: user.email }), roleCell, status, actionCell);
    body.appendChild(row);
  });
  table.append(head, body); wrapper.appendChild(table); return wrapper;
}

function createUserModal(onCreate: (data: UserPayload) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const title = createElement('div');
  title.append(createElement('span', { className: 'eyebrow', textContent: 'Usuários' }), createElement('h2', { textContent: 'Criar acesso direto' }));
  const close = createElement('button', { className: 'icon-button', type: 'button', title: 'Fechar' }); close.appendChild(createIcon('x'));
  header.append(title, close);
  const explanation = createElement('p', { className: 'settings-hint', textContent: 'Defina uma senha temporária segura. A pessoa deverá alterá-la no primeiro acesso; ela não será exibida novamente pelo HUB.' });
  const fields = createElement('div', { className: 'form-grid' });
  const nome = createInput('Nome', 'text', '', true);
  const email = createInput('E-mail', 'email', '', true);
  const senha = createInput('Senha temporária', 'password', '', true); senha.input.minLength = 6;
  const role = createSelectField('Papel', 'viewer', [{ value: 'viewer', label: 'Visualizador' }, { value: 'operator', label: 'Operacional' }, { value: 'financial', label: 'Financeiro' }, { value: 'admin', label: 'Administrador' }]);
  const actions = createElement('div', { className: 'form-actions' });
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
  const submit = createElement('button', { type: 'submit', textContent: 'Criar usuário' });
  actions.append(cancel, submit); fields.append(nome.field, email.field, senha.field, role.field); form.append(header, explanation, fields, actions); panel.appendChild(form); overlay.appendChild(panel);
  const closeModal = () => overlay.remove(); close.addEventListener('click', closeModal); cancel.addEventListener('click', closeModal); overlay.addEventListener('click', (event) => { if (event.target === overlay) closeModal(); });
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); if (!form.reportValidity()) return; submit.disabled = true; submit.textContent = 'Criando...';
    try { await onCreate({ nome: nome.input.value.trim(), email: email.input.value.trim(), senha: senha.input.value, role: role.select.value as UserPayload['role'] }); closeModal(); }
    catch (error) { submit.disabled = false; submit.textContent = 'Criar usuário'; useToast().error(error instanceof Error ? error.message : 'Não foi possível criar o usuário.'); }
  });
  return overlay;
}

function canManageUsers(): boolean { const role = getCurrentUser()?.role; return role === 'owner' || role === 'admin'; }
function getRoleBadgeClass(role: UserRole): string { return role === 'owner' || role === 'admin' ? 'tone-info' : role === 'operator' ? 'tone-warning' : role === 'financial' ? 'tone-success' : ''; }
function roleLabel(role: UserRole): string { return ({ owner: 'Proprietário', admin: 'Administrador', operator: 'Operacional', financial: 'Financeiro', viewer: 'Visualizador' })[role]; }
