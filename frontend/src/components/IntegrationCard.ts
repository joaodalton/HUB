import { createElement } from '../dom';
import { createIcon, type IconName } from './Icon';

export type IntegrationCardProps = {
  nome: string;
  descricao: string;
  icon: IconName;
  status: 'conectado' | 'nao_configurado';
  chipColor?: 'blue' | 'green' | 'amber' | 'red' | 'purple';
  onConfigurar: () => void;
};

// O card inteiro e o botao de configurar: o formulario so aparece (em modal) depois do clique.
export function createIntegrationCard({ nome, descricao, icon, status, chipColor = 'blue', onConfigurar }: IntegrationCardProps): HTMLElement {
  const card = createElement('button', { className: 'integration-card', type: 'button' });
  const heading = createElement('div', { className: 'integration-card-heading' });
  const chip = createElement('span', { className: `icon-stat-chip icon-stat-chip-${chipColor}` });
  const badge = createElement('span', {
    className: status === 'conectado' ? 'provider-badge success' : 'provider-badge warning',
    textContent: status === 'conectado' ? 'Conectado' : 'Não configurado'
  });
  const text = createElement('div', { className: 'integration-card-text' });

  chip.appendChild(createIcon(icon));
  heading.append(chip, badge);
  text.append(createElement('strong', { textContent: nome }), createElement('p', { textContent: descricao }));
  card.setAttribute('aria-label', `Configurar ${nome}`);
  card.addEventListener('click', onConfigurar);
  card.append(heading, text);
  return card;
}
