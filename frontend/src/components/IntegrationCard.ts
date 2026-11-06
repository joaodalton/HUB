import { createElement } from '../dom';
import { createBrandLogo, type BrandName } from './BrandLogo';

export type IntegrationCardProps = {
  nome: string;
  descricao: string;
  logo: BrandName;
  status: 'conectado' | 'nao_configurado';
  onConfigurar: () => void;
};

// O card inteiro e o botao de configurar: o formulario so aparece (em modal) depois do clique.
export function createIntegrationCard({ nome, descricao, logo, status, onConfigurar }: IntegrationCardProps): HTMLElement {
  const card = createElement('button', { className: 'integration-card', type: 'button' });
  const heading = createElement('div', { className: 'integration-card-heading' });
  const chip = createElement('span', { className: 'icon-stat-chip icon-stat-chip-logo' });
  const badge = createElement('span', {
    className: status === 'conectado' ? 'provider-badge success' : 'provider-badge warning',
    textContent: status === 'conectado' ? 'Conectado' : 'Não configurado'
  });
  const text = createElement('div', { className: 'integration-card-text' });

  chip.appendChild(createBrandLogo(logo));
  heading.append(chip, badge);
  text.append(createElement('strong', { textContent: nome }), createElement('p', { textContent: descricao }));
  card.setAttribute('aria-label', `Configurar ${nome}`);
  card.addEventListener('click', onConfigurar);
  card.append(heading, text);
  return card;
}
