import { createElement } from '../dom';
import { createIcon, type IconName } from './Icon';

export type IntegrationCardProps = {
  nome: string;
  descricao: string;
  icon: IconName;
  status: 'conectado' | 'nao_configurado';
  onConfigurar: () => void;
};

export function createIntegrationCard({ nome, descricao, icon, status, onConfigurar }: IntegrationCardProps): HTMLElement {
  const card = createElement('article', { className: 'integration-card' });
  const heading = createElement('div', { className: 'integration-card-heading' });
  const badge = createElement('span', {
    className: status === 'conectado' ? 'provider-badge success' : 'provider-badge warning',
    textContent: status === 'conectado' ? 'Conectado' : 'Não configurado'
  });
  const configure = createElement('button', { className: 'secondary-button', textContent: 'Configurar', type: 'button' });

  heading.append(createIcon(icon), createElement('strong', { textContent: nome }));
  configure.addEventListener('click', onConfigurar);
  card.append(heading, createElement('p', { textContent: descricao }), badge, configure);
  return card;
}
