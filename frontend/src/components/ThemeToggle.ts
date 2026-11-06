import { createElement } from '../dom';
import { attachTooltip } from './Tooltip';
import { t } from '../services/i18nService';
import { getResolvedTheme, setThemePreference } from '../services/themeService';

const SUN_PATH =
  '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>';
const MOON_PATH = '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>';

function markup(resolved: 'dark' | 'light'): string {
  const path = resolved === 'dark' ? MOON_PATH : SUN_PATH;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

export function createThemeToggle(): HTMLElement {
  const button = createElement('button', { className: 'theme-toggle-button' });
  button.type = 'button';

  function render(): void {
    const resolved = getResolvedTheme();
    const label = t(resolved === 'dark' ? 'nav.themeToggle.toLight' : 'nav.themeToggle.toDark');
    button.innerHTML = markup(resolved);
    button.setAttribute('aria-label', label);
    attachTooltip(button, label);
  }

  button.addEventListener('click', () => {
    const next = getResolvedTheme() === 'dark' ? 'light' : 'dark';
    setThemePreference(next);
  });

  window.addEventListener('hub-theme-change', render);

  // Cleanup: callers re-render the header on every navigation, detaching this
  // button without a lifecycle hook. Watch for detachment and stop listening.
  const observer = new MutationObserver(() => {
    if (!button.isConnected) {
      window.removeEventListener('hub-theme-change', render);
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  render();
  return button;
}
