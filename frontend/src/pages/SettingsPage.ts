import { createElement } from '../dom';
import { createBaseLayout } from '../layouts/BaseLayout';

export function createSettingsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const databasePanel = createSettingsPanel({
    eyebrow: 'Banco de dados',
    title: 'Fonte de dados operacional',
    rows: [
      ['Provedor atual', 'Google Drive'],
      ['Modo de uso', 'Documentos e dados iniciais'],
      ['Migracao planejada', 'SQL em servidor'],
      ['Status', 'Configurado por variaveis de ambiente']
    ]
  });
  const appPanel = createSettingsPanel({
    eyebrow: 'Aplicativo',
    title: 'Configuracoes gerais',
    rows: [
      ['API base', import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'],
      ['Interface', 'Web app preparado para empacotamento desktop'],
      ['Instalavel futuro', 'Electron ou Tauri com backend Python embutido']
    ]
  });

  content.append(databasePanel, appPanel);

  return createBaseLayout({
    content,
    eyebrow: 'Configuracoes',
    title: 'Organize integrações, banco de dados e parametros do HUB'
  });
}

function createSettingsPanel({
  eyebrow,
  title,
  rows
}: {
  eyebrow: string;
  title: string;
  rows: Array<[string, string]>;
}): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  const panelTitle = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrowElement = createElement('span', { className: 'eyebrow', textContent: eyebrow });
  const heading = createElement('h2', { textContent: title });
  const list = createElement('dl', { className: 'settings-list' });

  rows.forEach(([label, value]) => {
    const term = createElement('dt', { textContent: label });
    const detail = createElement('dd', { textContent: value });

    list.append(term, detail);
  });

  titleText.append(eyebrowElement, heading);
  panelTitle.appendChild(titleText);
  panel.append(panelTitle, list);

  return panel;
}
