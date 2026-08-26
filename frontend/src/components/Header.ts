import { createElement } from '../dom';
import { getCurrentUser } from '../services/authService';

type HeaderOptions = {
  eyebrow?: string;
  title?: string;
};

export function createHeader({
  eyebrow: eyebrowText = 'Central de documentos',
  title = 'Busque, separe e abra arquivos do Drive'
}: HeaderOptions = {}): HTMLElement {
  const header = createElement('header', { className: 'masthead' });
  const mark = createElement('div', { className: 'masthead-mark', textContent: 'HUB' });
  const text = createElement('div', { className: 'masthead-text' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: eyebrowText });

  const user = getCurrentUser();

  // Quando impersonando, mostrar o nome da empresa embaixo do logo
  if (user?.platformView) {
    const companyName = createElement('span', {
      className: 'masthead-company-name',
      textContent: user.platformView.empresaNome
    });
    text.append(companyName, eyebrow);
  } else {
    text.append(eyebrow);
  }

  const heading = createElement('h1', { textContent: title });
  text.append(heading);
  header.append(mark, text);
  return header;
}
