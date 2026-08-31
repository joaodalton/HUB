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

type CanalFiltro = 'todos' | TemplateCanal;

const CANAL_LABEL: Record<TemplateCanal, string> = { email: 'E-mail', whatsapp: 'WhatsApp' };

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
    eyebrow: 'Automações',
    title: 'Templates'
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
      createElement('strong', { textContent: 'Acesso não permitido' }),
      createElement('span', { textContent: 'Apenas proprietários e administradores podem administrar templates.' })
    );
    return panel;
  }

  function createList(): HTMLElement {
    const panel = createElement('section', { className: 'templates-panel' });
    const header = createElement('div', { className: 'templates-header' });
    const headerText = createElement('div');
    headerText.append(
      createElement('p', { className: 'templates-description', textContent: 'Textos reutilizáveis por empresa. Editar um template não envia mensagens nem altera conversas.' }),
      createElement('p', { className: 'settings-hint', textContent: 'E-mail usa assunto e corpo. WhatsApp usa somente corpo; o envio e a inbox ficam fora desta tela.' })
    );
    const actions = createElement('div', { className: 'templates-actions' });
    const filter = createElement('select');
    ([['todos', 'Todos os canais'], ['email', 'E-mail'], ['whatsapp', 'WhatsApp']] as const).forEach(([value, label]) => {
      const option = createElement('option', { textContent: label }); option.value = value; filter.appendChild(option);
    });
    filter.value = filtro;
    filter.addEventListener('change', () => { filtro = filter.value as CanalFiltro; void loadTemplates(); });
    const create = createElement('button', { type: 'button', textContent: 'Novo template' });
    create.addEventListener('click', () => { editing = null; render(); });
    actions.append(filter, create);
    header.append(headerText, actions);
    panel.appendChild(header);

    if (!loaded) {
      panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando templates...' }));
      return panel;
    }
    if (loadError) {
      const error = createElement('div', { className: 'templates-error' });
      const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
      retry.addEventListener('click', () => void loadTemplates());
      error.append(createElement('span', { textContent: loadError }), retry);
      panel.appendChild(error);
      return panel;
    }
    panel.appendChild(createDataTable<MessageTemplateRow>({
      title: 'Templates da empresa',
      eyebrow: filtro === 'todos' ? 'Todos' : CANAL_LABEL[filtro],
      rows: templates,
      emptyMessage: 'Nenhum template neste canal. Crie o primeiro para reutilizar em futuras automações.',
      columns: [
        { key: 'nome', label: 'Nome' },
        { key: 'canal', label: 'Canal', render: (item) => CANAL_LABEL[item.canal] },
        { key: 'variaveis', label: 'Variáveis', render: (item) => item.variaveisPermitidas.map((name) => `{{${name}}}`).join(', ') || 'Nenhuma' },
        { key: 'acoes', label: 'Ações', align: 'right', render: createRowActions }
      ]
    }));
    return panel;
  }

  function createRowActions(item: MessageTemplateRow): HTMLElement {
    const actions = createElement('div', { className: 'templates-row-actions' });
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Editar' });
    edit.addEventListener('click', (event) => { event.stopPropagation(); editing = item; render(); });
    actions.appendChild(edit);
    if (item.padrao) {
      const restoreButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Restaurar' });
      restoreButton.addEventListener('click', (event) => { event.stopPropagation(); void restore(item); });
      actions.appendChild(restoreButton);
    } else {
      const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: 'Remover' });
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
      createElement('h2', { textContent: isNew ? 'Novo template' : `Editar: ${template.nome}` }),
      createElement('p', { className: 'settings-hint', textContent: 'Use somente as variáveis permitidas. A prévia abaixo é textual e não realiza nenhum envio.' })
    );
    const form = createElement('form', { className: 'settings-form templates-form' });
    const nameField = createField('Nome', 'text', template?.nome ?? '', true);
    const keyField = createField('Chave', 'text', template?.chave ?? '', true);
    keyField.input.placeholder = 'ex.: aviso-rateio';
    keyField.field.hidden = !isNew;
    const canalField = createElement('label', { className: 'form-field' });
    const canalSelect = createElement('select');
    (Object.entries(CANAL_LABEL) as Array<[TemplateCanal, string]>).forEach(([value, label]) => { const option = createElement('option', { textContent: label }); option.value = value; canalSelect.appendChild(option); });
    canalSelect.value = canalInicial;
    canalSelect.disabled = !isNew;
    canalField.append(createElement('span', { textContent: 'Canal' }), canalSelect);
    const subjectField = createField('Assunto', 'text', template?.assunto ?? '', false);
    const bodyField = createElement('label', { className: 'form-field' });
    const body = createElement('textarea'); body.rows = 10; body.required = true; body.value = template?.corpo ?? '';
    bodyField.append(createElement('span', { textContent: 'Corpo' }), body);
    const variableHint = createElement('p', { className: 'templates-variables' });
    const preview = createElement('section', { className: 'templates-preview' });
    const variablesField = createElement('fieldset', { className: 'templates-variable-picker' });
    variablesField.appendChild(createElement('legend', { textContent: 'Variáveis permitidas' }));
    const variableCheckboxes = createVariableCheckboxes(template?.variaveisPermitidas ?? defaultVariables(canalInicial));
    variableCheckboxes.forEach(({ label }) => variablesField.appendChild(label));

    function refreshCanal(): void {
      const canal = canalSelect.value as TemplateCanal;
      subjectField.field.hidden = canal !== 'email';
      subjectField.input.required = canal === 'email';
      const allowed = variableCheckboxes.filter(({ input }) => input.checked).map(({ name }) => name);
      variableHint.replaceChildren(createElement('strong', { textContent: 'Variáveis permitidas: ' }));
      if (allowed.length === 0) variableHint.appendChild(document.createTextNode('nenhuma.'));
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
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
    cancel.addEventListener('click', () => { editing = undefined; render(); });
    const save = createElement('button', { type: 'submit', textContent: isNew ? 'Criar template' : 'Salvar alterações' });
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
      void saveTemplate(template, input);
    });
    buttons.append(cancel, save);
    variableCheckboxes.forEach(({ input }) => input.addEventListener('change', refreshCanal));
    form.append(nameField.field, keyField.field, canalField, subjectField.field, bodyField, variablesField, variableHint, preview, buttons);
    panel.appendChild(form);
    return panel;
  }

  async function loadTemplates(): Promise<void> {
    loaded = false; loadError = ''; render();
    try {
      templates = await getMessageTemplates(filtro === 'todos' ? undefined : filtro);
    } catch (error) {
      templates = [];
      loadError = error instanceof Error ? error.message : 'Não foi possível carregar os templates.';
    } finally { loaded = true; render(); }
  }

  async function saveTemplate(existing: MessageTemplateRow | null, input: MessageTemplateInput): Promise<void> {
    busy = true; loading.show(); render();
    try {
      const saved = existing ? await updateMessageTemplate(existing.id, input) : await createMessageTemplate(input);
      templates = existing ? templates.map((item) => item.id === saved.id ? saved : item) : [saved, ...templates];
      editing = undefined;
      toast.success(existing ? 'Template atualizado.' : 'Template criado.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível salvar o template.');
    } finally { busy = false; loading.hide(); render(); }
  }

  async function removeTemplate(template: MessageTemplateRow): Promise<void> {
    if (!window.confirm(`Remover o template “${template.nome}”? Esta ação não envia mensagens.`)) return;
    loading.show();
    try { await deleteMessageTemplate(template.id); templates = templates.filter((item) => item.id !== template.id); toast.success('Template removido.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível remover o template.'); }
    finally { loading.hide(); render(); }
  }

  async function restore(template: MessageTemplateRow): Promise<void> {
    if (!window.confirm(`Restaurar “${template.nome}” ao texto padrão?`)) return;
    loading.show();
    try { const restored = await restoreMessageTemplate(template.id); templates = templates.map((item) => item.id === restored.id ? restored : item); toast.success('Template restaurado ao padrão.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível restaurar o template.'); }
    finally { loading.hide(); render(); }
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
  target.appendChild(createElement('h3', { textContent: 'Prévia textual' }));
  if (canal === 'email') target.appendChild(createElement('p', { className: 'templates-preview-subject', textContent: subject || '(sem assunto)' }));
  target.appendChild(createElement('p', { className: 'templates-preview-body', textContent: body || '(sem conteúdo)' }));
}
