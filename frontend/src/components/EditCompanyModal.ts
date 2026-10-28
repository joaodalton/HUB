// frontend/src/components/EditCompanyModal.ts
import { maskCnpjInput } from './cadastroFields';
import { createElement } from '../dom';
import { updateEmpresaPlatform } from '../services/empresaService';
import type { PlatformEmpresa } from '../services/platformService';

type EditCompanyModalOptions = {
  empresa: PlatformEmpresa;
  onSaved: () => void;
  onError: (message: string) => void;
};

export function createEditCompanyModal({ empresa, onSaved, onError }: EditCompanyModalOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  titleText.append(
    createElement('span', { className: 'eyebrow', textContent: 'Plataforma' }),
    createElement('h2', { textContent: 'Editar empresa' })
  );
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });

  const field = (labelText: string, type: string, value: string, required: boolean): { wrap: HTMLElement; input: HTMLInputElement } => {
    const wrap = createElement('label', { className: 'form-field' });
    const input = createElement('input') as HTMLInputElement;
    input.type = type;
    input.required = required;
    input.value = value;
    wrap.append(createElement('span', { textContent: labelText }), input);
    return { wrap, input };
  };

  const nome = field('Nome da empresa', 'text', empresa.nome, true);
  const cnpj = field('CNPJ', 'text', empresa.cnpj ?? '', false);
  maskCnpjInput(cnpj.input);

  const statusField = createElement('label', { className: 'form-field' });
  const statusSelect = createElement('select') as HTMLSelectElement;
  statusSelect.innerHTML = `
    <option value="ativa">Ativa</option>
    <option value="inativa">Inativa</option>
    <option value="suspensa">Suspensa</option>
  `;
  statusSelect.value = empresa.status ?? 'ativa';
  statusField.append(createElement('span', { textContent: 'Status' }), statusSelect);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar empresa', type: 'submit' });

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
    saveButton.textContent = 'Salvando...';
    try {
      await updateEmpresaPlatform(empresa.id, {
        nome: nome.input.value.trim(),
        cnpj: cnpj.input.value.trim() || undefined,
        status: statusSelect.value
      });
      overlay.remove();
      onSaved();
    } catch (error) {
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar empresa';
      onError(error instanceof Error ? error.message : 'Não foi possível salvar a empresa.');
    }
  });

  header.append(titleText, closeButton);
  form.append(header, nome.wrap, cnpj.wrap, statusField, actions);
  actions.appendChild(saveButton);
  panel.appendChild(form);
  overlay.appendChild(panel);
  window.setTimeout(() => nome.input.focus());

  return overlay;
}
