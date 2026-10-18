import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { getCurrentUser } from '../services/authService';
import { getConcessionariaPassword } from '../services/ucsService';
import { createInput } from './formFields';

type PasswordSource = {
  id: number | string;
  senhaConcessionariaConfigurada?: boolean;
};

export function createConcessionariaPasswordField(source: PasswordSource) {
  const field = createInput('Senha da concessionaria', 'password', '', false);
  const toast = useToast();
  field.input.autocomplete = 'new-password';
  field.input.placeholder = 'Identificador automatico: CPF/CNPJ da UC';

  const user = getCurrentUser();
  const canReveal = user?.isPlatformAdmin || user?.role === 'owner' || user?.role === 'admin';
  const ucId = source.id;
  if (!canReveal || !source.senhaConcessionariaConfigurada || typeof ucId !== 'number') return field;

  const actions = createElement('div', { className: 'form-actions' });
  const revealButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Mostrar senha' });
  const copyButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Copiar' });
  copyButton.disabled = true;

  revealButton.addEventListener('click', async () => {
    revealButton.disabled = true;
    try {
      field.input.value = await getConcessionariaPassword(ucId);
      field.input.type = 'text';
      copyButton.disabled = false;
      revealButton.textContent = 'Senha exibida';
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel revelar a senha.');
      revealButton.disabled = false;
    }
  });

  copyButton.addEventListener('click', async () => {
    try {
      if (navigator.clipboard) await navigator.clipboard.writeText(field.input.value);
      else {
        field.input.select();
        document.execCommand('copy');
      }
      toast.success('Senha copiada.');
    } catch {
      toast.error('Nao foi possivel copiar a senha.');
    }
  });

  actions.append(revealButton, copyButton);
  field.field.appendChild(actions);
  return field;
}
