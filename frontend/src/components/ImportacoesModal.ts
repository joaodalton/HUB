import { createElement } from '../dom';
import { createImportacoesContent } from '../pages/ImportacoesPage';
import { createIcon } from './Icon';

export function createImportacoesModal(onImported: () => void): HTMLElement {
  const overlay = createElement('div', { className: 'modal-overlay importacoes-modal-overlay' });
  const card = createElement('section', { className: 'importacoes-modal-card' });
  const header = createElement('header', { className: 'modal-header' });
  const title = createElement('h2', { textContent: 'Importação/exportação' });
  const close = createElement('button', { className: 'modal-close', type: 'button' });
  close.appendChild(createIcon('x'));
  close.setAttribute('aria-label', 'Fechar importação/exportação');
  close.addEventListener('click', () => overlay.remove());
  header.append(title, close);
  card.append(header, createImportacoesContent(onImported));
  overlay.appendChild(card);
  return overlay;
}
