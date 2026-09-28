import { createElement } from '../dom';

let nextHelpId = 0;

export function createContextHelp(label: string, explanation: string): HTMLElement {
  const wrapper = createElement('span', { className: 'context-help' });
  const button = createElement('button', { className: 'context-help-button', type: 'button', textContent: '?' });
  const tip = createElement('span', { className: 'context-help-text', textContent: explanation });
  const id = `context-help-${++nextHelpId}`;
  let pinned = false;

  Object.assign(tip, { id, hidden: true });
  tip.setAttribute('role', 'tooltip');
  Object.entries({
    'aria-label': `Ajuda: ${label}`,
    'aria-controls': id,
    'aria-describedby': id,
    'aria-expanded': 'false'
  }).forEach(([name, value]) => button.setAttribute(name, value));

  const show = () => {
    tip.hidden = false;
    button.setAttribute('aria-expanded', 'true');
  };
  const hide = () => {
    if (pinned) return;
    tip.hidden = true;
    button.setAttribute('aria-expanded', 'false');
  };
  const closeOnOutside = (event: PointerEvent) => {
    if (wrapper.contains(event.target as Node)) return;
    pinned = false;
    hide();
    document.removeEventListener('pointerdown', closeOnOutside);
  };

  button.addEventListener('mouseenter', show);
  button.addEventListener('mouseleave', hide);
  button.addEventListener('focus', show);
  button.addEventListener('blur', hide);
  button.addEventListener('click', () => {
    pinned = !pinned;
    if (pinned) {
      show();
      document.addEventListener('pointerdown', closeOnOutside);
    } else {
      hide();
      document.removeEventListener('pointerdown', closeOnOutside);
    }
  });
  button.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      pinned = false;
      hide();
      button.blur();
      document.removeEventListener('pointerdown', closeOnOutside);
    }
  });

  wrapper.append(button, tip);
  return wrapper;
}
