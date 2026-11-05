// frontend/src/components/CreateCompanyModal.ts
import { maskCnpjInput } from './cadastroFields';
import { createElement } from '../dom';
import { createEmpresa } from '../services/empresaService';
import { t } from '../services/i18nService';

type CreateCompanyModalOptions = {
  onCreated: () => void;
  onError: (message: string) => void;
};

export function createCompanyModal({ onCreated, onError }: CreateCompanyModalOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  titleText.append(
    createElement('span', { className: 'eyebrow', textContent: t('clients.company.eyebrow') }),
    createElement('h2', { textContent: t('clients.company.heading') })
  );
  const closeButton = createElement('button', { className: 'secondary-button', textContent: t('shared.modal.close'), type: 'button' });

  const field = (labelText: string, type: string, required: boolean): { wrap: HTMLElement; input: HTMLInputElement } => {
    const wrap = createElement('label', { className: 'form-field' });
    const input = createElement('input') as HTMLInputElement;
    input.type = type;
    input.required = required;
    wrap.append(createElement('span', { textContent: labelText }), input);
    return { wrap, input };
  };

  const nome = field(t('clients.company.fieldName'), 'text', true);
  const razaoSocial = field(t('clients.company.fieldLegalName'), 'text', false);
  const cnpj = field(t('clients.company.fieldCnpj'), 'text', false);
  maskCnpjInput(cnpj.input);
  const email = field(t('clients.company.fieldEmail'), 'email', false);
  const telefone = field(t('clients.company.fieldPhone'), 'text', false);

  const ownerNome = field(t('clients.company.fieldOwnerName'), 'text', true);
  const ownerEmail = field(t('clients.company.fieldOwnerEmail'), 'email', true);
  const ownerSenha = field(t('clients.company.fieldOwnerPassword'), 'password', true);
  ownerSenha.input.minLength = 8;

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('clients.company.saveButton'), type: 'submit' });

  closeButton.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (event) => { if (event.target === overlay) overlay.remove(); });
  document.addEventListener('keydown', function onKeyDown(event) {
    if (event.key !== 'Escape') return;
    overlay.remove();
    document.removeEventListener('keydown', onKeyDown);
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.checkValidity()) { form.reportValidity(); return; }

    saveButton.disabled = true;
    saveButton.textContent = t('clients.company.saving');
    try {
      await createEmpresa({
        empresa: {
          nome: nome.input.value.trim(),
          razao_social: razaoSocial.input.value.trim() || undefined,
          cnpj: cnpj.input.value.trim() || undefined,
          email: email.input.value.trim() || undefined,
          telefone: telefone.input.value.trim() || undefined
        },
        owner: {
          nome: ownerNome.input.value.trim(),
          email: ownerEmail.input.value.trim(),
          senha: ownerSenha.input.value
        }
      });
      overlay.remove();
      onCreated();
    } catch (error) {
      saveButton.disabled = false;
      saveButton.textContent = t('clients.company.saveButton');
      onError(error instanceof Error ? error.message : t('clients.company.error'));
    }
  });

  header.append(titleText, closeButton);
  form.append(
    header,
    nome.wrap, razaoSocial.wrap, cnpj.wrap, email.wrap, telefone.wrap,
    ownerNome.wrap, ownerEmail.wrap, ownerSenha.wrap,
    actions
  );
  actions.appendChild(saveButton);
  panel.appendChild(form);
  overlay.appendChild(panel);
  window.setTimeout(() => nome.input.focus());

  return overlay;
}
