import { createIcon } from '../components/Icon';
import { createInput, createSelectField } from '../components/formFields';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { createDataTable } from '../components/DataTable';
import { createInvitation, getInvitations, revokeInvitation, type InvitationRow } from '../services/invitationService';
import { getCurrentUser } from '../services/authService';
import { createUser, getUsers, setUserActive, updateUser, type UserPayload, type UserRole, type UserRow } from '../services/userService';

export function createUsersPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let users: UserRow[] = [];
  let loaded = false;
  let loadError = '';
  let activeTab: 'users' | 'invitations' = 'users';
  let invitations: InvitationRow[] = [];
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
    const tabs = createElement('div', { className: 'detail-tabs' });
    for (const [key, label] of [['users', 'Usuários'], ['invitations', 'Convites']] as const) {
      const tab = createElement('button', { className: activeTab === key ? 'detail-tab active' : 'detail-tab', type: 'button', textContent: label });
      tab.addEventListener('click', () => { activeTab = key; if (key === 'invitations') void loadInvitations(); else renderContent(); }); tabs.appendChild(tab);
    }
    const pageActions = createElement('div', { className: 'page-actions' });
    const newUserButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newUserButton.append(createIcon('plus'), document.createTextNode(activeTab === 'users' ? 'Criar acesso direto' : 'Convidar por e-mail'));
    newUserButton.addEventListener('click', () => document.body.appendChild(activeTab === 'users' ? createUserModal(handleCreate) : createInvitationModal(handleInvite)));
    pageActions.appendChild(newUserButton);
    const panel = createElement('section', { className: 'data-panel' });
    if (activeTab === 'invitations') panel.appendChild(createInvitationsTable(invitations, handleRevoke, handleResend));
    else if (!loaded) panel.appendChild(createElement('div', { className: 'loading-state', textContent: 'Carregando usuários...' }));
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
    } else panel.appendChild(createUsersTable(users, handleSetActive, handleEdit));
    content.replaceChildren(tabs, pageActions, panel);
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
  async function handleEdit(user: UserRow, data: Partial<Pick<UserRow, 'nome' | 'email' | 'role'>>): Promise<void> { const updated = await updateUser(user.id, data); users = users.map(item => item.id === user.id ? updated : item); toast.success('Usuário atualizado.'); renderContent(); }
  async function loadInvitations(): Promise<void> { try { invitations = await getInvitations(); } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível carregar convites.'); } finally { renderContent(); } }
  async function handleInvite(data: { email: string; role: Exclude<UserRole, 'owner'> }): Promise<void> { await createInvitation(data); toast.success('Convite criado.'); await loadInvitations(); }
  async function handleRevoke(invite: InvitationRow): Promise<void> { if (!window.confirm(`Revogar convite para ${invite.email}?`)) return; await revokeInvitation(invite.id); toast.success('Convite revogado.'); await loadInvitations(); }
  async function handleResend(invite: InvitationRow): Promise<void> { await createInvitation({ email: invite.email, role: invite.role as Exclude<UserRole, 'owner'> }); toast.success('Novo convite criado.'); await loadInvitations(); }
}

function createInvitationsTable(rows: InvitationRow[], onRevoke: (row: InvitationRow) => Promise<void>, onResend: (row: InvitationRow) => Promise<void>): HTMLElement {
  return createDataTable<InvitationRow>({ title: 'Convites', eyebrow: 'Acessos pendentes e históricos', rows, emptyMessage: 'Nenhum convite encontrado.', columns: [
    { key: 'email', label: 'E-mail', render: row => row.email }, { key: 'role', label: 'Papel', render: row => roleLabel(row.role) },
    { key: 'status', label: 'Status', render: row => row.status }, { key: 'expiresAt', label: 'Expira em', render: row => row.expiresAt ? new Date(row.expiresAt).toLocaleDateString('pt-BR') : '-' },
    { key: 'actions', label: 'Ações', render: row => { const wrap = createElement('div', { className: 'table-row-actions' }); const resend = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Reenviar' }); resend.addEventListener('click', () => void onResend(row)); wrap.appendChild(resend); if (row.status === 'pending') { const revoke = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Revogar' }); revoke.addEventListener('click', () => void onRevoke(row)); wrap.appendChild(revoke); } return wrap; } }
  ] });
}

function createInvitationModal(onCreate: (data: { email: string; role: Exclude<UserRole, 'owner'> }) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const email = createInput('E-mail', 'email', '', true);
  const role = createSelectField('Papel', 'viewer', [{ value: 'viewer', label: 'Visualizador' }, { value: 'operator', label: 'Operacional' }, { value: 'financial', label: 'Financeiro' }, { value: 'admin', label: 'Administrador' }]);
  const close = () => overlay.remove();
  const actions = createElement('div', { className: 'form-actions' });
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
  const submit = createElement('button', { type: 'submit', textContent: 'Enviar convite' });
  cancel.addEventListener('click', close); actions.append(cancel, submit);
  form.append(createElement('h2', { textContent: 'Convidar por e-mail' }), createElement('p', { className: 'settings-hint', textContent: 'A pessoa definirá nome e senha ao aceitar o convite.' }), email.field, role.field, actions);
  form.addEventListener('submit', async event => { event.preventDefault(); if (!form.reportValidity()) return; submit.disabled = true; try { await onCreate({ email: email.input.value.trim(), role: role.select.value as Exclude<UserRole, 'owner'> }); close(); } catch (error) { submit.disabled = false; useToast().error(error instanceof Error ? error.message : 'Não foi possível criar o convite.'); } });
  overlay.addEventListener('click', event => { if (event.target === overlay) close(); }); panel.appendChild(form); overlay.appendChild(panel); return overlay;
}

function createUsersTable(users: UserRow[], onSetActive: (user: UserRow, ativo: boolean) => Promise<void>, onEdit: (user: UserRow, data: Partial<Pick<UserRow, 'nome' | 'email' | 'role'>>) => Promise<void>): HTMLElement {
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
      const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Editar' }); edit.addEventListener('click', () => document.body.appendChild(createUserEditModal(user, data => onEdit(user, data)))); actionCell.appendChild(edit);
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

function createUserEditModal(user: UserRow, onSave: (data: Partial<Pick<UserRow, 'nome' | 'email' | 'role'>>) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' }); const form = createElement('form', { className: 'client-card client-form' }); const nome = createInput('Nome', 'text', user.nome, true); const email = createInput('E-mail', 'email', user.email, true); const role = createSelectField('Papel', user.role, [{ value: 'viewer', label: 'Visualizador' }, { value: 'operator', label: 'Operacional' }, { value: 'financial', label: 'Financeiro' }, { value: 'admin', label: 'Administrador' }]); const save = createElement('button', { type: 'submit', textContent: 'Salvar' }); form.append(createElement('h2', { textContent: 'Editar usuário' }), nome.field, email.field, role.field, save); form.addEventListener('submit', async event => { event.preventDefault(); if (!form.reportValidity()) return; await onSave({ nome: nome.input.value.trim(), email: email.input.value.trim(), role: role.select.value as UserRole }); overlay.remove(); }); overlay.appendChild(form); return overlay;
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
