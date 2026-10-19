// frontend/src/components/CreateCompanyModal.ts
import { maskCnpjInput } from './cadastroFields';
import { createElement } from '../dom';
import { createEmpresa } from '../services/empresaService';

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
    createElement('span', { className: 'eyebrow', textContent: 'Plataforma' }),
    createElement('h2', { textContent: 'Nova empresa' })
  );
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });

  const field = (labelText: string, type: string, required: boolean): { wrap: HTMLElement; input: HTMLInputElement } => {
    const wrap = createElement('label', { className: 'form-field' });
    const input = createElement('input') as HTMLInputElement;
    input.type = type;
    input.required = required;
    wrap.append(createElement('span', { textContent: labelText }), input);
    return { wrap, input };
  };

  const nome = field('Nome da empresa', 'text', true);
  const razaoSocial = field('Razão social', 'text', false);
  const cnpj = field('CNPJ', 'text', false);
  maskCnpjInput(cnpj.input);
  const email = field('E-mail da empresa', 'email', false);
  const telefone = field('Telefone', 'text', false);

  const ownerNome = field('Nome do responsável', 'text', true);
  const ownerEmail = field('E-mail do responsável', 'email', true);
  const ownerSenha = field('Senha provisória', 'password', true);
  ownerSenha.input.minLength = 8;

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Criar empresa', type: 'submit' });

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
    saveButton.textContent = 'Criando...';
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
      saveButton.textContent = 'Criar empresa';
      onError(error instanceof Error ? error.message : 'Não foi possível criar a empresa.');
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
