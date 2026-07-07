import { createElement } from '../dom';
import { createBaseLayout } from '../layouts/BaseLayout';

const agendaItems = [
  { dia: '05', titulo: 'Enviar boleto', tipo: 'Financeiro' },
  { dia: '10', titulo: 'Mensagem de vencimento', tipo: 'Aviso' },
  { dia: '15', titulo: 'Novo contrato assinado', tipo: 'Cliente' }
];

export function createAgendaPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const panel = createElement('section', { className: 'settings-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Agenda' });
  const heading = createElement('h2', { textContent: 'Calendario operacional' });
  const calendar = createElement('div', { className: 'calendar-grid' });

  titleText.append(eyebrow, heading);
  title.appendChild(titleText);

  Array.from({ length: 30 }, (_, index) => String(index + 1).padStart(2, '0')).forEach((day) => {
    const cell = createElement('article', { className: 'calendar-day' });
    const number = createElement('strong', { textContent: day });
    const events = agendaItems.filter((item) => item.dia === day);

    cell.appendChild(number);
    events.forEach((item) => {
      cell.appendChild(createElement('span', { textContent: `${item.tipo}: ${item.titulo}` }));
    });
    calendar.appendChild(cell);
  });

  panel.append(title, calendar);
  content.appendChild(panel);

  return createBaseLayout({
    content,
    eyebrow: 'Agenda',
    title: 'Rascunho de lembretes e rotinas operacionais'
  });
}
