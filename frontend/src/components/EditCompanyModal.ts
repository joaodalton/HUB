// frontend/src/components/EditCompanyModal.ts
import { maskCnpjInput } from './cadastroFields';
import { createElement } from '../dom';
import { updateEmpresaPlatform } from '../services/empresaService';
import type { PlatformEmpresa } from '../platform/services/platformService';
import { t } from '../services/i18nService';

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
    createElement('span', { className: 'eyebrow', textContent: t('platform.companies.editModal.eyebrow') }),
    createElement('h2', { textContent: t('platform.companies.editModal.heading') })
  );
  const closeButton = createElement('button', { className: 'secondary-button', textContent: t('shared.modal.close'), type: 'button' });

  const field = (labelText: string, type: string, value: string, required: boolean): { wrap: HTMLElement; input: HTMLInputElement } => {
    const wrap = createElement('label', { className: 'form-field' });
    const input = createElement('input') as HTMLInputElement;
    input.type = type;
    input.required = required;
    input.value = value;
    wrap.append(createElement('span', { textContent: labelText }), input);
    return { wrap, input };
  };

  const nome = field(t('platform.companies.editModal.fieldName'), 'text', empresa.nome, true);
  const cnpj = field(t('platform.companies.editModal.fieldCnpj'), 'text', empresa.cnpj ?? '', false);
  maskCnpjInput(cnpj.input);

  const statusField = createElement('label', { className: 'form-field' });
  const statusSelect = createElement('select') as HTMLSelectElement;
  statusSelect.innerHTML = `
    <option value="ativa">${t('platform.companies.editModal.statusAtiva')}</option>
    <option value="inativa">${t('platform.companies.editModal.statusInativa')}</option>
    <option value="suspensa">${t('platform.companies.editModal.statusSuspensa')}</option>
  `;
  statusSelect.value = empresa.status ?? 'ativa';
  statusField.append(createElement('span', { textContent: t('platform.companies.editModal.fieldStatus') }), statusSelect);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('platform.companies.editModal.saveButton'), type: 'submit' });

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
    saveButton.textContent = t('platform.companies.editModal.saving');
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
      saveButton.textContent = t('platform.companies.editModal.saveButton');
      onError(error instanceof Error ? error.message : t('platform.companies.editModal.error'));
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
