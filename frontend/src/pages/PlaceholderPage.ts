import { createElement } from '../dom';
import { createBaseLayout } from '../layouts/BaseLayout';

export function createPlaceholderPage({
  eyebrow,
  title,
  message
}: {
  eyebrow: string;
  title: string;
  message: string;
}): HTMLElement {
  const content = createElement('section', { className: 'placeholder-panel' });
  const text = createElement('p', { textContent: message });

  content.appendChild(text);

  return createBaseLayout({ content, eyebrow, title });
}
