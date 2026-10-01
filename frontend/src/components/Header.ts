import { createElement } from '../dom';

type HeaderOptions = {
  eyebrow?: string;
  title?: string;
  description?: string;
};

export function createHeader({
  eyebrow: eyebrowText = 'Central de documentos',
  title = 'Busque, separe e abra arquivos do Drive',
  description
}: HeaderOptions = {}): HTMLElement {
  const header = createElement('header', { className: 'masthead' });
  const mark = createElement('div', { className: 'masthead-mark', textContent: 'HUB' });
  const text = createElement('div', { className: 'masthead-text' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: eyebrowText });
  const heading = createElement('h1', { textContent: title });
  const context = description
    ? createElement('p', { className: 'masthead-description', textContent: description })
    : null;
  text.append(eyebrow, heading);
  if (context) text.appendChild(context);
  header.append(mark, text);
  return header;
}
