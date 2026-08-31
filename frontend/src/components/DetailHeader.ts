// frontend/src/components/DetailHeader.ts
import { createElement } from '../dom';

type DetailHeaderOptions = {
  backLabel: string;
  onBack: () => void;
  title: string;
  badge?: HTMLElement;
  actions?: HTMLElement[];
};

export function createDetailHeader({ backLabel, onBack, title, badge, actions = [] }: DetailHeaderOptions): HTMLElement {
  const wrapper = createElement('div');
  const backButton = createElement('button', { className: 'back-link', textContent: `← ${backLabel}`, type: 'button' });
  const header = createElement('div', { className: 'detail-header' });
  const titleRow = createElement('div', { className: 'detail-title-row' });
  const heading = createElement('h2', { textContent: title });
  const actionsWrap = createElement('div', { className: 'detail-header-actions' });

  backButton.addEventListener('click', onBack);

  titleRow.appendChild(heading);
  if (badge) titleRow.appendChild(badge);

  actions.forEach((action) => actionsWrap.appendChild(action));

  header.append(titleRow, actionsWrap);
  wrapper.append(backButton, header);
  return wrapper;
}