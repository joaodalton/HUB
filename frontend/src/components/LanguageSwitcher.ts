import { createElement } from '../dom';
import { attachTooltip } from './Tooltip';
import { getLanguage, setLanguage, t, type Language } from '../services/i18nService';
import flagBr from '../assets/flags/br.svg';
import flagUs from '../assets/flags/us.svg';
import flagFr from '../assets/flags/fr.svg';

const OPTIONS: Array<{ value: Language; flagUrl: string; key: string }> = [
  { value: 'pt', flagUrl: flagBr, key: 'nav.languageSwitcher.pt' },
  { value: 'en', flagUrl: flagUs, key: 'nav.languageSwitcher.en' },
  { value: 'fr', flagUrl: flagFr, key: 'nav.languageSwitcher.fr' }
];

export function createLanguageSwitcher(): HTMLElement {
  const group = createElement('div', { className: 'language-switcher' });
  group.setAttribute('role', 'group');
  group.setAttribute('aria-label', t('nav.languageSwitcher.label'));

  function renderOptions(): void {
    const current = getLanguage();
    group.replaceChildren(
      ...OPTIONS.map(({ value, flagUrl, key }) => {
        const label = t(key);
        const button = createElement('button', {
          className: 'language-switcher-option'
        });
        const img = createElement('img', { className: 'language-switcher-flag' });
        img.src = flagUrl;
        img.alt = '';
        img.loading = 'lazy';
        button.appendChild(img);
        button.type = 'button';
        button.setAttribute('aria-label', label);
        attachTooltip(button, label);
        const isActive = value === current;
        button.setAttribute('aria-pressed', String(isActive));
        button.classList.toggle('is-active', isActive);
        button.addEventListener('click', () => {
          setLanguage(value);
          window.dispatchEvent(new PopStateEvent('popstate'));
        });
        return button;
      })
    );
  }

  window.addEventListener('languagechange', renderOptions);

  // Cleanup: callers re-render the header on every navigation, detaching this
  // group without a lifecycle hook. Watch for detachment and stop listening.
  const observer = new MutationObserver(() => {
    if (!group.isConnected) {
      window.removeEventListener('languagechange', renderOptions);
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  renderOptions();
  return group;
}
