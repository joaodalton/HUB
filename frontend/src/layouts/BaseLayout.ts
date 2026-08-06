import { createElement } from '../dom';
import { createHeader } from '../components/Header';
import { createLoading } from '../components/Loading';
import { createSidebar } from '../components/Sidebar';
import { createToastContainer } from '../components/Toast';

type BaseLayoutOptions = {
  content: HTMLElement;
  eyebrow?: string;
  title?: string;
};

export function createBaseLayout({ content, eyebrow, title }: BaseLayoutOptions): HTMLElement {
  const shell = createElement('div', { className: 'app-shell' });
  const body = createElement('div', { className: 'app-body' });
  const main = createElement('main', { className: 'app-main' });

  main.append(createHeader({ eyebrow, title }), content);
  body.append(createSidebar(), main);
  shell.append(body, createLoading(), createToastContainer());

  return shell;
}