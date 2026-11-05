import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { getCurrentUser } from '../services/authService';
import { getConcessionariaPassword } from '../services/ucsService';
import { createInput } from './formFields';
import { t } from '../services/i18nService';

type PasswordSource = {
  id: number | string;
  senhaConcessionariaConfigurada?: boolean;
};

export function createConcessionariaPasswordField(source: PasswordSource) {
  const field = createInput(t('faturas.concessionariaPassword.label'), 'password', '', false);
  const toast = useToast();
  field.input.autocomplete = 'new-password';
  field.input.placeholder = t('faturas.concessionariaPassword.placeholder');

  const user = getCurrentUser();
  const canReveal = user?.isPlatformAdmin || user?.role === 'owner' || user?.role === 'admin';
  const ucId = source.id;
  if (!canReveal || !source.senhaConcessionariaConfigurada || typeof ucId !== 'number') return field;

  const actions = createElement('div', { className: 'form-actions' });
  const revealButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.concessionariaPassword.show') });
  const copyButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.concessionariaPassword.copy') });
  copyButton.disabled = true;

  revealButton.addEventListener('click', async () => {
    revealButton.disabled = true;
    try {
      field.input.value = await getConcessionariaPassword(ucId);
      field.input.type = 'text';
      copyButton.disabled = false;
      revealButton.textContent = t('faturas.concessionariaPassword.shown');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('faturas.concessionariaPassword.revealError'));
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
      toast.success(t('faturas.concessionariaPassword.copied'));
    } catch {
      toast.error(t('faturas.concessionariaPassword.copyError'));
    }
  });

  actions.append(revealButton, copyButton);
  field.field.appendChild(actions);
  return field;
}
