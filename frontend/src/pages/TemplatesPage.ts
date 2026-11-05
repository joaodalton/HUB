import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import {
  createMessageTemplate,
  deleteMessageTemplate,
  getMessageTemplates,
  restoreMessageTemplate,
  updateMessageTemplate,
  type MessageTemplateInput,
  type MessageTemplateRow,
  type TemplateCanal
} from '../services/messageTemplatesService';
import { submitWhatsappTemplate, syncWhatsappTemplates } from '../services/whatsappService';
import { t } from '../services/i18nService';

type CanalFiltro = 'todos' | TemplateCanal;

function canalLabel(canal: TemplateCanal): string {
  return canal === 'email' ? t('templates.page.canalEmail') : t('templates.page.canalWhatsapp');
}

export function createTemplatesPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  const toast = useToast();
  let templates: MessageTemplateRow[] = [];
  let filtro: CanalFiltro = 'todos';
  let loaded = false;
  let loadError = '';
  let editing: MessageTemplateRow | null | undefined;
  let busy = false;

  const layout = createBaseLayout({
    content,
    eyebrow: t('templates.page.eyebrow'),
    title: t('templates.page.title')
  });
  render();
  if (canManageTemplates()) void loadTemplates();
  return layout;

  function render(): void {
    if (!canManageTemplates()) {
      content.replaceChildren(createDenied());
      return;
    }
    if (editing !== undefined) {
      content.replaceChildren(createEditor(editing));
      return;
    }
    content.replaceChildren(createList());
  }

  function createDenied(): HTMLElement {
    const panel = createElement('section', { className: 'templates-panel empty-state' });
    panel.append(
      createElement('strong', { textContent: t('templates.page.deniedTitle') }),
      createElement('span', { textContent: t('templates.page.deniedBody') })
    );
    return panel;
  }

  function createList(): HTMLElement {
    const panel = createElement('section', { className: 'templates-panel' });
    const header = createElement('div', { className: 'templates-header' });
    const headerText = createElement('div');
    headerText.append(
      createElement('p', { className: 'templates-description', textContent: t('templates.page.description') }),
      createElement('p', { className: 'settings-hint', textContent: t('templates.page.hint') })
    );
    const actions = createElement('div', { className: 'templates-actions' });
    const filter = createElement('select');
    ([['todos', t('templates.page.filterAll')], ['email', t('templates.page.canalEmail')], ['whatsapp', t('templates.page.canalWhatsapp')]] as const).forEach(([value, label]) => {
      const option = createElement('option', { textContent: label }); option.value = value; filter.appendChild(option);
    });
    filter.value = filtro;
    filter.addEventListener('change', () => { filtro = filter.value as CanalFiltro; void loadTemplates(); });
    const create = createElement('button', { type: 'button', textContent: t('templates.page.newButton') });
    create.addEventListener('click', () => { editing = null; render(); });
    const sync = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('templates.page.syncButton') });
    sync.addEventListener('click', () => void syncMetaTemplates());
    actions.append(filter, sync, create);
    header.append(headerText, actions);
    panel.appendChild(header);

    if (!loaded) {
      panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('templates.page.loading') }));
      return panel;
    }
    if (loadError) {
      const error = createElement('div', { className: 'templates-error' });
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.retry') });
      retry.addEventListener('click', () => void loadTemplates());
      error.append(createElement('span', { textContent: loadError }), retry);
      panel.appendChild(error);
      return panel;
    }
    panel.appendChild(createDataTable<MessageTemplateRow>({
      title: t('templates.page.tableTitle'),
      eyebrow: filtro === 'todos' ? t('templates.page.filterAllShort') : canalLabel(filtro),
      rows: templates,
      emptyMessage: t('templates.page.emptyMessage'),
      columns: [
        { key: 'nome', label: t('templates.page.colNome') },
        { key: 'canal', label: t('templates.page.colCanal'), render: (item) => canalLabel(item.canal) },
        { key: 'meta', label: t('templates.page.colMeta'), render: (item) => item.canal === 'whatsapp' ? metaLabel(item.metaStatus) : '—' },
        { key: 'variaveis', label: t('templates.page.colVariaveis'), render: (item) => item.variaveisPermitidas.map((name) => `{{${name}}}`).join(', ') || t('templates.page.noneVariables') },
        { key: 'acoes', label: t('templates.page.colAcoes'), align: 'right', render: createRowActions }
      ]
    }));
    return panel;
  }

  function createRowActions(item: MessageTemplateRow): HTMLElement {
    const actions = createElement('div', { className: 'templates-row-actions' });
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('templates.page.editButton') });
    edit.addEventListener('click', (event) => { event.stopPropagation(); editing = item; render(); });
    actions.appendChild(edit);
    if (item.canal === 'whatsapp' && item.metaStatus !== 'approved' && item.metaStatus !== 'pending') {
      const submit = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('templates.page.submitMetaButton') });
      submit.addEventListener('click', (event) => { event.stopPropagation(); void submitMetaTemplate(item); });
      actions.appendChild(submit);
    }
    if (item.padrao) {
      const restoreButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('templates.page.restoreButton') });
      restoreButton.addEventListener('click', (event) => { event.stopPropagation(); void restore(item); });
      actions.appendChild(restoreButton);
    } else {
      const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: t('common.remove') });
      remove.addEventListener('click', (event) => { event.stopPropagation(); void removeTemplate(item); });
      actions.appendChild(remove);
    }
    return actions;
  }

  function createEditor(template: MessageTemplateRow | null): HTMLElement {
    const isNew = template === null;
    const canalInicial = template?.canal ?? 'email';
    const panel = createElement('section', { className: 'templates-panel templates-editor' });
    panel.append(
      createElement('h2', { textContent: isNew ? t('templates.page.newTitle') : t('templates.page.editTitleTemplate').replace('{name}', template.nome) }),
      createElement('p', { className: 'settings-hint', textContent: t('templates.page.editorHint') })
    );
    const form = createElement('form', { className: 'settings-form templates-form' });
    const nameField = createField(t('templates.page.fieldNome'), 'text', template?.nome ?? '', true);
    const keyField = createField(t('templates.page.fieldChave'), 'text', template?.chave ?? '', true);
    keyField.input.placeholder = t('templates.page.fieldChavePlaceholder');
    keyField.field.hidden = !isNew;
    const canalField = createElement('label', { className: 'form-field' });
    const canalSelect = createElement('select');
    (['email', 'whatsapp'] as TemplateCanal[]).forEach((value) => { const option = createElement('option', { textContent: canalLabel(value) }); option.value = value; canalSelect.appendChild(option); });
    canalSelect.value = canalInicial;
    canalSelect.disabled = !isNew;
    canalField.append(createElement('span', { textContent: t('templates.page.fieldCanal') }), canalSelect);
    const subjectField = createField(t('templates.page.fieldAssunto'), 'text', template?.assunto ?? '', false);
    const metaCategoryField = createElement('label', { className: 'form-field' });
    const metaCategory = createElement('select');
    ([['UTILITY', t('templates.page.categoryUtility')], ['MARKETING', t('templates.page.categoryMarketing')], ['AUTHENTICATION', t('templates.page.categoryAuthentication')]] as const).forEach(([value, label]) => {
      const option = createElement('option', { textContent: label }); option.value = value; metaCategory.appendChild(option);
    });
    metaCategory.value = template?.metaCategory ?? 'UTILITY';
    metaCategoryField.append(createElement('span', { textContent: t('templates.page.fieldMetaCategory') }), metaCategory);
    const bodyField = createElement('label', { className: 'form-field' });
    const body = createElement('textarea'); body.rows = 10; body.required = true; body.value = template?.corpo ?? '';
    bodyField.append(createElement('span', { textContent: t('templates.page.fieldCorpo') }), body);
    const variableHint = createElement('p', { className: 'templates-variables' });
    const preview = createElement('section', { className: 'templates-preview' });
    const variablesField = createElement('fieldset', { className: 'templates-variable-picker' });
    variablesField.appendChild(createElement('legend', { textContent: t('templates.page.fieldVariaveisPermitidas') }));
    const variableCheckboxes = createVariableCheckboxes(template?.variaveisPermitidas ?? defaultVariables(canalInicial));
    variableCheckboxes.forEach(({ label }) => variablesField.appendChild(label));

    function refreshCanal(): void {
      const canal = canalSelect.value as TemplateCanal;
      subjectField.field.hidden = canal !== 'email';
      metaCategoryField.hidden = canal !== 'whatsapp';
      subjectField.input.required = canal === 'email';
      const allowed = variableCheckboxes.filter(({ input }) => input.checked).map(({ name }) => name);
      variableHint.replaceChildren(createElement('strong', { textContent: t('templates.page.allowedVariablesPrefix') }));
      if (allowed.length === 0) variableHint.appendChild(document.createTextNode(t('templates.page.noneAllowed')));
      allowed.forEach((variable, index) => {
        const insert = createElement('button', { className: 'template-variable', type: 'button', textContent: `{{${variable}}}` });
        insert.addEventListener('click', () => insertVariable(body, `{{${variable}}}`));
        variableHint.append(index ? document.createTextNode(', ') : document.createTextNode(' '), insert);
      });
      renderPreview(preview, canal, subjectField.input.value, body.value);
    }
    canalSelect.addEventListener('change', refreshCanal);
    subjectField.input.addEventListener('input', refreshCanal);
    body.addEventListener('input', refreshCanal);
    refreshCanal();

    const buttons = createElement('div', { className: 'form-actions' });
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('templates.page.cancel') });
    cancel.addEventListener('click', () => { editing = undefined; render(); });
    const save = createElement('button', { type: 'submit', textContent: isNew ? t('templates.page.createButton') : t('templates.page.saveChangesButton') });
    save.disabled = busy;
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const input: MessageTemplateInput = {
        nome: nameField.input.value.trim(),
        canal: canalSelect.value as TemplateCanal,
        corpo: body.value,
        variaveisPermitidas: variableCheckboxes.filter(({ input }) => input.checked).map(({ name }) => name)
      };
      if (isNew) input.chave = keyField.input.value.trim();
      if (input.canal === 'email') input.assunto = subjectField.input.value.trim();
      if (input.canal === 'whatsapp') input.metaCategory = metaCategory.value as 'MARKETING' | 'UTILITY' | 'AUTHENTICATION';
      void saveTemplate(template, input);
    });
    buttons.append(cancel, save);
    variableCheckboxes.forEach(({ input }) => input.addEventListener('change', refreshCanal));
    form.append(nameField.field, keyField.field, canalField, subjectField.field, metaCategoryField, bodyField, variablesField, variableHint, preview, buttons);
    panel.appendChild(form);
    return panel;
  }

  async function loadTemplates(): Promise<void> {
    loaded = false; loadError = ''; render();
    try {
      templates = await getMessageTemplates(filtro === 'todos' ? undefined : filtro);
    } catch (error) {
      templates = [];
      loadError = error instanceof Error ? error.message : t('templates.page.loadError');
    } finally { loaded = true; render(); }
  }

  async function saveTemplate(existing: MessageTemplateRow | null, input: MessageTemplateInput): Promise<void> {
    busy = true; loading.show(); render();
    try {
      const saved = existing ? await updateMessageTemplate(existing.id, input) : await createMessageTemplate(input);
      templates = existing ? templates.map((item) => item.id === saved.id ? saved : item) : [saved, ...templates];
      editing = undefined;
      toast.success(existing ? t('templates.page.updatedSuccess') : t('templates.page.createdSuccess'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('templates.page.saveError'));
    } finally { busy = false; loading.hide(); render(); }
  }

  async function removeTemplate(template: MessageTemplateRow): Promise<void> {
    if (!window.confirm(t('templates.page.confirmRemoveTemplate').replace('{name}', template.nome))) return;
    loading.show();
    try { await deleteMessageTemplate(template.id); templates = templates.filter((item) => item.id !== template.id); toast.success(t('templates.page.removedSuccess')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('templates.page.removeError')); }
    finally { loading.hide(); render(); }
  }

  async function restore(template: MessageTemplateRow): Promise<void> {
    if (!window.confirm(t('templates.page.confirmRestoreTemplate').replace('{name}', template.nome))) return;
    loading.show();
    try { const restored = await restoreMessageTemplate(template.id); templates = templates.map((item) => item.id === restored.id ? restored : item); toast.success(t('templates.page.restoredSuccess')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('templates.page.restoreError')); }
    finally { loading.hide(); render(); }
  }

  async function submitMetaTemplate(template: MessageTemplateRow): Promise<void> {
    loading.show();
    try {
      const saved = await submitWhatsappTemplate(template.id) as MessageTemplateRow;
      templates = templates.map((item) => item.id === saved.id ? saved : item);
      toast.success(t('templates.page.submittedToMetaSuccess'));
    } catch (error) { toast.error(error instanceof Error ? error.message : t('templates.page.submitMetaError')); }
    finally { loading.hide(); render(); }
  }

  async function syncMetaTemplates(): Promise<void> {
    loading.show();
    try { await syncWhatsappTemplates(); await loadTemplates(); toast.success(t('templates.page.syncedSuccess')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('templates.page.syncError')); }
    finally { loading.hide(); }
  }
}

function canManageTemplates(): boolean { const role = getCurrentUser()?.role; return role === 'owner' || role === 'admin'; }

function createField(label: string, type: string, value: string, required: boolean) {
  const field = createElement('label', { className: 'form-field' });
  const input = createElement('input'); input.type = type; input.value = value; input.required = required;
  field.append(createElement('span', { textContent: label }), input);
  return { field, input };
}

function defaultVariables(canal: TemplateCanal): string[] { return canal === 'email' ? ['nome', 'empresa', 'link'] : ['nome', 'empresa']; }

function createVariableCheckboxes(selected: string[]): Array<{ name: string; input: HTMLInputElement; label: HTMLLabelElement }> {
  return ['nome', 'link', 'papel', 'empresa'].map((name) => {
    const label = createElement('label', { className: 'templates-variable-option' });
    const input = createElement('input'); input.type = 'checkbox'; input.checked = selected.includes(name);
    label.append(input, createElement('span', { textContent: `{{${name}}}` }));
    return { name, input, label };
  });
}

function insertVariable(input: HTMLTextAreaElement, variable: string): void {
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? start;
  input.setRangeText(variable, start, end, 'end'); input.dispatchEvent(new Event('input'));
  input.focus();
}

function renderPreview(target: HTMLElement, canal: TemplateCanal, subject: string, body: string): void {
  target.replaceChildren();
  target.appendChild(createElement('h3', { textContent: t('templates.page.previewTitle') }));
  if (canal === 'email') target.appendChild(createElement('p', { className: 'templates-preview-subject', textContent: subject || t('templates.page.noSubjectPlaceholder') }));
  target.appendChild(createElement('p', { className: 'templates-preview-body', textContent: body || t('templates.page.noBodyPlaceholder') }));
}

function metaLabel(status: MessageTemplateRow['metaStatus']): string {
  return ({ draft: t('templates.page.metaDraft'), pending: t('templates.page.metaPending'), approved: t('templates.page.metaApproved'), rejected: t('templates.page.metaRejected') } as Record<string, string>)[status ?? 'draft'];
}
