import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getPlants, type PlantRow } from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';
import { createRateioFormularioView } from './rateio/RateioFormularioView';
import { createRateioWizard } from './rateio/RateioWizard';

type RateioTab = 'montar' | 'formulario';

export function createRateioPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let plants: PlantRow[] = [];
  let ucs: UcRow[] = [];
  let loadError = false;
  let activeTab: RateioTab = 'montar';
  let wizard: HTMLElement | null = null;
  const formulario = createRateioFormularioView(() => plants);

  const layout = createBaseLayout({
    content,
    eyebrow: 'Rateio',
    title: 'Monte o rateio de energia passo a passo'
  });
  void loadAll();
  return layout;

  async function loadAll(): Promise<void> {
    loading.show();
    try {
      [plants, ucs] = await Promise.all([getPlants(), getUcs()]);
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Nao foi possivel carregar as usinas. Verifique se o backend esta rodando.');
    } finally {
      loading.hide();
      wizard = createRateioWizard({ plants, ucs, loadError, onOpenFormulario });
      renderContent();
    }
  }

  function onOpenFormulario(plantId: number | null): void {
    formulario.selectPlant(plantId);
    activeTab = 'formulario';
    renderContent();
  }

  function renderContent(): void {
    const tabs = renderTabs();
    content.replaceChildren(tabs, activeTab === 'formulario' ? formulario.element : wizard ?? createElement('p', { className: 'loading-state', textContent: 'Carregando...' }));
  }

  function renderTabs(): HTMLElement {
    const tabs = createElement('div', { className: 'rateio-tabs' });
    tabs.setAttribute('role', 'tablist');
    const montar = createElement('button', { className: activeTab === 'montar' ? 'active' : '', type: 'button', textContent: 'Montar Rateio' });
    const formularioTab = createElement('button', { className: activeTab === 'formulario' ? 'active' : '', type: 'button', textContent: 'Gerar Formulário Copel' });
    montar.addEventListener('click', () => { activeTab = 'montar'; renderContent(); });
    formularioTab.addEventListener('click', () => { activeTab = 'formulario'; renderContent(); });
    tabs.append(montar, formularioTab);
    return tabs;
  }
}
