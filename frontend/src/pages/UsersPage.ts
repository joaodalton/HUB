import { createIcon } from '../components/Icon';
import { createFormSection, createInput, createSelectField } from '../components/formFields';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { attachActionsRail, createDataTable } from '../components/DataTable';
import { createIconStatCard } from '../components/IconStatCard';
import { createInvitation, getInvitations, revokeInvitation, type InvitationRow } from '../services/invitationService';
import { getCurrentUser } from '../services/authService';
import { createPaginationNav } from '../components/PaginationNav';
import { readPositiveListParam, writeListState } from '../services/listState';
import type { Pagination } from '../services/apiClient';
import { createUser, deleteUser, getUsersPage, setUserActive, updateUser, type UserPayload, type UserRole, type UserRow, type UserUpdatePayload } from '../services/userService';
import { t } from '../services/i18nService';

const PAGE_SIZE = 50;

export function createUsersPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let users: UserRow[] = [];
  let pagination: Pagination = { page: 1, pageSize: PAGE_SIZE, total: 0, pages: 0 };
  let page: number = readPositiveListParam('pagina');
  let loaded = false;
  let loadError = '';
  let activeTab: 'users' | 'invitations' = 'users';
  let invitations: InvitationRow[] = [];
  const layout = createBaseLayout({ content, eyebrow: t('nav.item.configuracoes'), title: t('users.page.title') });
  renderContent();
  if (canManageUsers()) void loadUsers();
  return layout;

  function renderContent(): void {
    if (!canManageUsers()) {
      const denied = createElement('section', { className: 'data-panel empty-state' });
      denied.append(createIcon('lock', 'empty-state-icon'), createElement('strong', { textContent: t('users.page.accessDeniedTitle') }), createElement('span', { textContent: t('users.page.accessDeniedBody') }));
      content.replaceChildren(denied);
      return;
    }
    const tabs = createElement('div', { className: 'detail-tabs' });
    for (const [key, label] of [['users', t('users.page.tabUsers')], ['invitations', t('users.page.tabInvitations')]] as const) {
      const tab = createElement('button', { className: activeTab === key ? 'detail-tab active' : 'detail-tab', type: 'button', textContent: label });
      tab.addEventListener('click', () => { activeTab = key; if (key === 'invitations') void loadInvitations(); else renderContent(); }); tabs.appendChild(tab);
    }
    const pageActions = createElement('div', { className: 'page-actions' });
    const newUserButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newUserButton.append(createIcon('plus'), document.createTextNode(activeTab === 'users' ? t('users.page.createDirectAccess') : t('users.page.inviteByEmail')));
    newUserButton.addEventListener('click', () => document.body.appendChild(activeTab === 'users' ? createUserModal(handleCreate) : createInvitationModal(handleInvite)));
    pageActions.appendChild(newUserButton);
    const panel = createElement('section', { className: 'data-panel' });
    if (activeTab === 'invitations') panel.appendChild(createInvitationsTable(invitations, handleRevoke, handleResend));
    else if (!loaded) panel.appendChild(createElement('div', { className: 'loading-state', textContent: t('users.page.loadingUsers') }));
    else if (loadError) {
      const error = createElement('div', { className: 'empty-state' });
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.retry') });
      retry.addEventListener('click', () => void loadUsers());
      error.append(createElement('strong', { textContent: t('users.page.loadErrorTitle') }), createElement('span', { textContent: loadError }), retry);
      panel.appendChild(error);
    } else if (users.length === 0) {
      const empty = createElement('div', { className: 'empty-state' });
      empty.append(createIcon('clients', 'empty-state-icon'), createElement('p', { textContent: t('users.page.emptyTitle') }), createElement('span', { textContent: t('users.page.emptyBody') }));
      panel.appendChild(empty);
    } else panel.appendChild(createUsersTable(users, handleSetActive, handleEdit));
    const metrics = activeTab === 'users'
      ? createUserMetrics(users, pagination.total)
      : createInvitationMetrics(invitations);
    const pager = activeTab === 'users' && loaded && !loadError
      ? createPaginationNav(pagination, !loaded, (nextPage) => {
          page = nextPage; writeListState({ pagina: page }); void loadUsers();
        }, t('users.page.paginationLabel'))
      : null;
    content.replaceChildren(tabs, metrics, pageActions, panel, ...(pager ? [pager] : []));
  }

  async function loadUsers(): Promise<void> {
    loaded = false; loadError = ''; renderContent(); loading.show();
    try {
      const result = await getUsersPage(page, PAGE_SIZE);
      users = result.data;
      pagination = result.pagination;
      page = pagination.page;
    }
    catch (error) { users = []; loadError = error instanceof Error ? error.message : t('users.page.loadErrorFallback'); }
    finally { loaded = true; loading.hide(); renderContent(); }
  }

  async function handleCreate(data: UserPayload): Promise<void> {
    loading.show();
    try { await createUser(data); toast.success(t('users.page.createdSuccess')); await loadUsers(); }
    catch (error) { throw error instanceof Error ? error : new Error(t('users.page.createError')); }
    finally { loading.hide(); }
  }

  async function handleSetActive(user: UserRow, ativo: boolean): Promise<void> {
    const action = ativo ? t('users.page.actionActivate') : t('users.page.actionDeactivate');
    if (!window.confirm(t('users.page.confirmToggleTemplate').replace('{action}', action).replace('{name}', user.nome))) return;
    loading.show();
    try {
      const updated = await setUserActive(user.id, ativo);
      users = users.map((item) => item.id === updated.id ? updated : item);
      toast.success(ativo ? t('users.page.activatedSuccess') : t('users.page.deactivatedSuccess'));
    } catch (error) { toast.error(error instanceof Error ? error.message : t('users.page.toggleError')); }
    finally { loading.hide(); renderContent(); }
  }
  async function handleEdit(user: UserRow, data: UserUpdatePayload): Promise<void> { const updated = await updateUser(user.id, data); users = users.map(item => item.id === user.id ? updated : item); toast.success(t('users.page.updatedSuccess')); renderContent(); }
  async function loadInvitations(): Promise<void> { try { invitations = await getInvitations(); } catch (error) { toast.error(error instanceof Error ? error.message : t('users.page.loadInvitationsError')); } finally { renderContent(); } }
  async function handleInvite(data: { email: string; role: Exclude<UserRole, 'owner'> }): Promise<void> { await createInvitation(data); toast.success(t('users.page.inviteCreatedSuccess')); await loadInvitations(); }
  async function handleRevoke(invite: InvitationRow): Promise<void> { if (!window.confirm(t('users.page.confirmRevokeTemplate').replace('{email}', invite.email))) return; await revokeInvitation(invite.id); toast.success(t('users.page.revokedSuccess')); await loadInvitations(); }
  async function handleResend(invite: InvitationRow): Promise<void> { await createInvitation({ email: invite.email, role: invite.role as Exclude<UserRole, 'owner'> }); toast.success(t('users.page.resentSuccess')); await loadInvitations(); }
}

// total vem da paginacao do servidor (contagem real); ativo/admin sao
// calculados sobre a pagina carregada -- aproximacao aceitavel enquanto a
// maioria das empresas tiver poucas dezenas de usuarios (cabe numa pagina).
function createUserMetrics(users: UserRow[], total: number): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });
  grid.append(
    createIconStatCard({ icon: 'clients', chipColor: 'blue', value: String(total), label: t('users.page.metricUsuarios') }),
    createIconStatCard({ icon: 'check', chipColor: 'green', value: String(users.filter((user) => user.status === 'ativo').length), label: t('users.page.metricAcessosAtivos') }),
    createIconStatCard({ icon: 'lock', chipColor: 'purple', value: String(users.filter((user) => user.role === 'owner' || user.role === 'admin').length), label: t('users.page.metricAdministradores') })
  );
  return grid;
}

function createInvitationMetrics(invitations: InvitationRow[]): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });
  grid.append(
    createIconStatCard({ icon: 'mensagens', chipColor: 'blue', value: String(invitations.length), label: t('users.page.metricConvites') }),
    createIconStatCard({ icon: 'pending', chipColor: 'amber', value: String(invitations.filter((invite) => invite.status === 'pending').length), label: t('users.page.metricPendentes') })
  );
  return grid;
}

function createInvitationsTable(rows: InvitationRow[], onRevoke: (row: InvitationRow) => Promise<void>, onResend: (row: InvitationRow) => Promise<void>): HTMLElement {
  return createDataTable<InvitationRow>({ title: t('users.page.invitationsTableTitle'), eyebrow: t('users.page.invitationsTableEyebrow'), rows, emptyMessage: t('users.page.invitationsEmpty'), columns: [
    { key: 'email', label: t('users.page.colEmail'), render: row => row.email }, { key: 'role', label: t('users.page.colRole'), render: row => roleLabel(row.role) },
    { key: 'status', label: t('users.page.colStatus'), render: row => invitationStatusLabel(row.status) }, { key: 'expiresAt', label: t('users.page.colExpiresAt'), render: row => row.expiresAt ? new Date(row.expiresAt).toLocaleDateString('pt-BR') : '-' },
    { key: 'actions', label: t('users.page.colActions'), render: row => { const wrap = createElement('div', { className: 'table-row-actions' }); const resend = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('users.page.resendButton') }); resend.addEventListener('click', () => void onResend(row)); wrap.appendChild(resend); if (row.status === 'pending') { const revoke = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('users.page.revokeButton') }); revoke.addEventListener('click', () => void onRevoke(row)); wrap.appendChild(revoke); } return wrap; } }
  ] });
}

function createInvitationModal(onCreate: (data: { email: string; role: Exclude<UserRole, 'owner'> }) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const email = createInput(t('users.page.fieldEmail'), 'email', '', true);
  const role = createSelectField(t('users.page.fieldPapel'), 'viewer', [{ value: 'viewer', label: t('nav.role.viewer') }, { value: 'operator', label: t('nav.role.operator') }, { value: 'financial', label: t('nav.role.financial') }, { value: 'admin', label: t('nav.role.admin') }]);
  const close = () => overlay.remove();
  const actions = createElement('div', { className: 'form-actions' });
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('users.page.cancel') });
  const submit = createElement('button', { type: 'submit', textContent: t('users.page.sendInviteButton') });
  cancel.addEventListener('click', close); actions.append(cancel, submit);
  form.append(createElement('h2', { textContent: t('users.page.inviteByEmail') }), createElement('p', { className: 'settings-hint', textContent: t('users.page.inviteHint') }), email.field, role.field, actions);
  form.addEventListener('submit', async event => { event.preventDefault(); if (!form.reportValidity()) return; submit.disabled = true; try { await onCreate({ email: email.input.value.trim(), role: role.select.value as Exclude<UserRole, 'owner'> }); close(); } catch (error) { submit.disabled = false; useToast().error(error instanceof Error ? error.message : t('users.page.inviteCreateError')); } });
  overlay.addEventListener('click', event => { if (event.target === overlay) close(); }); panel.appendChild(form); overlay.appendChild(panel); return overlay;
}

function createUsersTable(users: UserRow[], onSetActive: (user: UserRow, ativo: boolean) => Promise<void>, onEdit: (user: UserRow, data: UserUpdatePayload) => Promise<void>): HTMLElement {
  const createUserActionButtons = (user: UserRow): HTMLElement => {
    const wrap = createElement('div', { className: 'table-row-actions' });
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('users.page.editButton') });
    edit.addEventListener('click', () => document.body.appendChild(createUserEditModal(user, data => onEdit(user, data))));
    wrap.appendChild(edit);
    if (user.role !== 'owner') {
      const nextActive = user.status !== 'ativo';
      const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: nextActive ? t('users.page.activateButton') : t('users.page.deactivateButton') });
      button.addEventListener('click', () => void onSetActive(user, nextActive));
      wrap.appendChild(button);
    }
    return wrap;
  };

  const panel = createDataTable<UserRow>({
    title: t('users.page.usersTableTitle'),
    eyebrow: t('users.page.usersTableEyebrow'),
    rows: users,
    emptyMessage: t('users.page.usersEmpty'),
    columns: [
      { key: 'id', label: t('users.page.colId'), render: (user) => `#${user.id}` },
      { key: 'nome', label: t('users.page.colNome') },
      { key: 'email', label: t('users.page.colEmail') },
      { key: 'role', label: t('users.page.colRole'), render: (user) => createElement('span', { className: `status-badge ${getRoleBadgeClass(user.role)}`, textContent: roleLabel(user.role) }) },
      {
        key: 'status',
        label: t('users.page.colStatus'),
        render: (user) => {
          const el = createElement('span');
          el.append(
            createElement('span', { className: user.status === 'ativo' ? 'status-dot status-success' : 'status-dot status-danger' }),
            document.createTextNode(user.status === 'ativo' ? ` ${t('users.page.statusAtivo')}` : ` ${t('users.page.statusInativo')}`)
          );
          return el;
        }
      }
    ]
  });

  attachActionsRail(panel, users, createUserActionButtons);
  return panel;
}

function createUserEditModal(user: UserRow, onSave: (data: UserUpdatePayload) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const form = createElement('form', { className: 'client-card client-form' });
  const nome = createInput(t('users.page.fieldNome'), 'text', user.nome, true);
  const email = createInput(t('users.page.fieldEmail'), 'email', user.email, true);
  const senha = createInput(t('users.page.fieldNovaSenha'), 'password', '');
  senha.input.minLength = 6;
  const roleOptions = user.role === 'owner'
    ? [{ value: 'owner', label: t('nav.role.owner') }]
    : [{ value: 'viewer', label: t('nav.role.viewer') }, { value: 'operator', label: t('nav.role.operator') }, { value: 'financial', label: t('nav.role.financial') }, { value: 'admin', label: t('nav.role.admin') }];
  const role = createSelectField(t('users.page.fieldPapel'), user.role, roleOptions);
  role.select.disabled = user.role === 'owner';
  const save = createElement('button', { type: 'submit', textContent: t('common.save') });
  const formActions = createElement('div', { className: 'form-actions' });
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('users.page.cancel') });
  const destroy = createElement('button', { className: 'danger-button small-button', type: 'button', textContent: t('users.page.deleteButton') });
  formActions.append(cancel, save, destroy);
  form.append(createElement('h2', { textContent: t('users.page.editUserTitle') }), nome.field, email.field, senha.field, role.field, formActions);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data: UserUpdatePayload = { nome: nome.input.value.trim(), email: email.input.value.trim() };
    if (user.role !== 'owner') data.role = role.select.value as UserRole;
    if (senha.input.value) data.senha = senha.input.value;
    await onSave(data);
    overlay.remove();
  });
  destroy.addEventListener('click', async () => {
    const confirmed = window.confirm(t('users.page.confirmDeleteTemplate').replace('{name}', user.nome));
    if (!confirmed) return;
    try {
      await deleteUser(user.id);
      overlay.remove();
    } catch (error) {
      useToast().error(error instanceof Error ? error.message : t('users.page.deleteError'));
    }
  });
  overlay.addEventListener('click', event => { if (event.target === overlay) overlay.remove(); });
  overlay.appendChild(form);
  return overlay;
}

function createUserModal(onCreate: (data: UserPayload) => Promise<void>): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const title = createElement('div');
  title.append(createElement('span', { className: 'eyebrow', textContent: t('nav.item.usuarios') }), createElement('h2', { textContent: t('users.page.createDirectAccess') }));
  const close = createElement('button', { className: 'icon-button', type: 'button', title: t('users.page.close') }); close.appendChild(createIcon('x'));
  header.append(title, close);
  const explanation = createElement('p', { className: 'settings-hint', textContent: t('users.page.explanation') });
  const nome = createInput(t('users.page.fieldNome'), 'text', '', true);
  const email = createInput(t('users.page.fieldEmail'), 'email', '', true);
  const senha = createInput(t('users.page.fieldSenhaTemporaria'), 'password', '', true); senha.input.minLength = 6;
  const role = createSelectField(t('users.page.fieldPapel'), 'viewer', [{ value: 'viewer', label: t('nav.role.viewer') }, { value: 'operator', label: t('nav.role.operator') }, { value: 'financial', label: t('nav.role.financial') }, { value: 'admin', label: t('nav.role.admin') }]);
  const actions = createElement('div', { className: 'form-actions' });
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('users.page.cancel') });
  const submit = createElement('button', { type: 'submit', textContent: t('users.page.createUserButton') });
  actions.append(cancel, submit); form.append(header, explanation, createFormSection(t('users.page.sectionInfoPessoal'), nome.field, email.field), createFormSection(t('users.page.sectionAcessoPermissoes'), role.field, senha.field), actions); panel.appendChild(form); overlay.appendChild(panel);
  const closeModal = () => overlay.remove(); close.addEventListener('click', closeModal); cancel.addEventListener('click', closeModal); overlay.addEventListener('click', (event) => { if (event.target === overlay) closeModal(); });
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); if (!form.reportValidity()) return; submit.disabled = true; submit.textContent = t('users.page.creating');
    try { await onCreate({ nome: nome.input.value.trim(), email: email.input.value.trim(), senha: senha.input.value, role: role.select.value as UserPayload['role'] }); closeModal(); }
    catch (error) { submit.disabled = false; submit.textContent = t('users.page.createUserButton'); useToast().error(error instanceof Error ? error.message : t('users.page.createError')); }
  });
  return overlay;
}

function canManageUsers(): boolean { const role = getCurrentUser()?.role; return role === 'owner' || role === 'admin'; }
function getRoleBadgeClass(role: UserRole): string { return role === 'owner' || role === 'admin' ? 'tone-info' : role === 'operator' ? 'tone-warning' : role === 'financial' ? 'tone-success' : ''; }
function roleLabel(role: UserRole): string { return ({ owner: t('nav.role.owner'), admin: t('nav.role.admin'), operator: t('nav.role.operator'), financial: t('nav.role.financial'), viewer: t('nav.role.viewer') })[role]; }
function invitationStatusLabel(status: InvitationRow['status']): string { return ({ pending: t('users.page.inviteStatusPending'), accepted: t('users.page.inviteStatusAccepted'), expired: t('users.page.inviteStatusExpired'), revoked: t('users.page.inviteStatusRevoked') })[status]; }
