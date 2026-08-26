import { createElement } from '../dom';
import { createBaseLayout } from '../layouts/BaseLayout';
import { useToast } from '../hooks/useToast';
import { getEmailTemplates, updateEmailTemplate, restoreEmailTemplate, sendTestEmail, type EmailTemplateRow } from '../services/emailTemplatesService';

export function createTemplatePage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let templates: EmailTemplateRow[] = [];
  let loaded = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Templates de e-mail',
    title: 'Edite os textos enviados automaticamente pelo sistema'
  });

  loadTemplates();

  return layout;

  async function loadTemplates(): Promise<void> {
    try {
      templates = await getEmailTemplates();
      loaded = true;
    } catch {
      toast.error('Não foi possível carregar os templates.');
    } finally {
      renderContent();
    }
  }

  function renderContent(): void {
    if (!loaded) {
      content.replaceChildren(
        createElement('p', { textContent: 'Carregando...' })
      );
      return;
    }

    if (!templates.length) {
      content.replaceChildren(
        createElement('p', { textContent: 'Nenhum template disponível.' })
      );
      return;
    }

    const list = createElement('div', { className: 'settings-list' });
    templates.forEach(template => list.appendChild(createTemplateCard(template)));
    content.replaceChildren(list);
  }

  function createTemplateCard(template: EmailTemplateRow): HTMLElement {
    const card = createElement('details', { className: 'uc-editor-card' });
    const summary = createElement('summary', { className: 'uc-summary' });
    const titleGroup = createElement('div', { className: 'uc-summary-title' });

    titleGroup.append(
      createElement('strong', { textContent: template.nome }),
      createElement('span', {
        textContent: `Variáveis: ${(template.variaveisDisponiveis ?? []).length > 0
          ? template.variaveisDisponiveis.map(v => `{{${v}}}`).join(', ')
          : '-'}`
      })
    );
    summary.appendChild(titleGroup);

    const body = createElement('div', { className: 'uc-editor-body settings-form' });

    const assuntoField = createElement('label', { className: 'form-field' });
    const assuntoInput = createElement('input');
    assuntoInput.type = 'text';
    assuntoInput.value = template.assunto;
    assuntoField.append(createElement('span', { textContent: 'Assunto' }), assuntoInput);

    const corpoField = createElement('label', { className: 'form-field' });
    const corpoInput = createElement('textarea');
    corpoInput.rows = 8;
    corpoInput.value = template.corpo;
    corpoField.append(createElement('span', { textContent: 'Corpo' }), corpoInput);

    const hint = createElement('p', {
      className: 'settings-hint',
      textContent: 'Use {{variavel}} pra inserir dados dinâmicos. Quando "{{link}}" aparece sozinho numa linha, vira um botão no e-mail.'
    });

    const actions = createElement('div', { className: 'form-actions' });
    const saveButton = createElement('button', { textContent: 'Salvar', type: 'button' });
    const restoreButton = createElement('button', { className: 'secondary-button', textContent: 'Restaurar padrão', type: 'button' });
    const testButton = createElement('button', { className: 'secondary-button', textContent: 'Enviar teste pra mim', type: 'button' });

    saveButton.addEventListener('click', async () => {
      saveButton.disabled = true;
      saveButton.textContent = 'Salvando...';
      try {
        const updated = await updateEmailTemplate(template.chave, assuntoInput.value, corpoInput.value);
        templates = templates.map(t => t.chave === template.chave ? updated : t);
        toast.success('Template salvo.');
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Falha ao salvar.');
      } finally {
        saveButton.disabled = false;
        saveButton.textContent = 'Salvar';
      }
    });

    restoreButton.addEventListener('click', async () => {
      if (!window.confirm('Restaurar ao texto padrão? Edições atuais serão perdidas.')) return;
      restoreButton.disabled = true;
      try {
        const updated = await restoreEmailTemplate(template.chave);
        templates = templates.map(t => t.chave === template.chave ? updated : t);
        toast.success('Template restaurado.');
      } catch {
        toast.error('Falha ao restaurar.');
      } finally {
        restoreButton.disabled = false;
      }
    });

    testButton.addEventListener('click', async () => {
      testButton.disabled = true;
      testButton.textContent = 'Enviando...';
      try {
        const message = await sendTestEmail(template.chave);
        toast.success(message);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Falha ao enviar teste.');
      } finally {
        testButton.disabled = false;
        testButton.textContent = 'Enviar teste pra mim';
      }
    });

    actions.append(saveButton, restoreButton, testButton);
    body.append(assuntoField, corpoField, hint, actions);
    card.append(summary, body);
    return card;
  }
}
