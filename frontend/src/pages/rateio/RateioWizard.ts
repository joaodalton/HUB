import { createElement } from '../../dom';
import { useGlobalLoading } from '../../hooks/useGlobalLoading';
import { useToast } from '../../hooks/useToast';
import { updatePlantRateioConfig, type PlantRow } from '../../services/plantService';
import { confirmarSelecaoRateio, getQualificacao, previewRateio, type RateioQualificacao, type RateioPreview } from '../../services/rateioService';
import { getUcs, type UcRow } from '../../services/ucsService';
import { renderRateioDistributionStage } from './RateioDistributionStage';
import { renderRateioPlantPicker } from './RateioPlantPicker';
import { renderRateioProductionStage } from './RateioProductionStage';
import { renderRateioQualificationStage } from './RateioQualificationStage';
import { createStepHeader, defaultCompetencia } from './shared';

type Stage = 'selecionar' | 'producao' | 'qualificacao' | 'distribuicao' | 'concluido';
type Props = { plants: PlantRow[]; ucs: UcRow[]; loadError: boolean; onOpenFormulario: (plantId: number | null) => void };

export function createRateioWizard(props: Props): HTMLElement {
  const root = createElement('section', { className: 'content-stack' });
  const toast = useToast(); const loading = useGlobalLoading();
  let plants = props.plants;
  let ucs = props.ucs;
  let stage: Stage = 'selecionar';
  let selectedPlantId: number | null = null;
  let preview: RateioPreview | null = null;
  let previewLoading = false;
  let reservaCustomMode = false;
  let qualificacao: RateioQualificacao | null = null;
  let qualificacaoLoading = false;
  let showingQualified = false;
  let competencia = defaultCompetencia();
  let confirming = false;
  let confirmation: { conexoesCriadas: number; conexoesAtualizadas: number } | null = null;
  const selectedUcIds = new Set<number>();
  const overrides = new Map<number, number>();

  render(); return root;

  function render(): void {
    if (stage === 'concluido') { root.replaceChildren(renderConcluido()); return; }
    const plant = plants.find((item) => item.id === selectedPlantId);
    if (stage !== 'selecionar' && !plant) stage = 'selecionar';
    if (stage === 'producao' && plant) {
      root.replaceChildren(createStepHeader(2, 'Produção'), renderRateioProductionStage({ plant, preview, previewLoading, reservaCustomMode, onBack: () => { stage = 'selecionar'; render(); }, onContinue: () => { stage = 'qualificacao'; render(); void loadQualificacao(plant.id); }, onCustomMode: () => { reservaCustomMode = true; render(); }, onSaveReserva: (value) => void saveReserva(plant.id, value) }));
      return;
    }
    if (stage === 'qualificacao' && plant) {
      root.replaceChildren(createStepHeader(3, 'Qualificação'), renderRateioQualificationStage({ plant, qualificacao, loading: qualificacaoLoading, showingQualified, selectedUcIds, onBack: () => { stage = 'producao'; render(); }, onContinue: continueToDistribution, onToggleList: () => { showingQualified = !showingQualified; render(); }, onToggleUc: (ucId, selected) => { if (selected) selectedUcIds.add(ucId); else selectedUcIds.delete(ucId); render(); } }));
      return;
    }
    if (stage === 'distribuicao' && plant && qualificacao) {
      root.replaceChildren(createStepHeader(4, 'Distribuição'), renderRateioDistributionStage({ plant, qualificacao, preview, selectedUcIds, overrides, competencia, confirming, onBack: () => { stage = 'qualificacao'; render(); }, onCompetenciaChange: (value) => { competencia = value; }, onApprove: (selecoes) => void confirmRateio(plant.id, selecoes) }));
      return;
    }
    root.replaceChildren(createStepHeader(1, 'Selecionar usina'), renderRateioPlantPicker({ plants, loadError: props.loadError, selectedPlantId, connectedUcsCount, onSelect: selectPlant }));
  }

  function selectPlant(plant: PlantRow): void {
    selectedPlantId = plant.id; stage = 'producao'; reservaCustomMode = ![0, 5, 10, 15].includes(plant.reservaPercentual); render(); void loadPreview(plant.id);
  }

  function connectedUcsCount(plantId: number): number {
    return ucs.reduce((count, uc) => count + uc.conexoes.filter((conexao) => conexao.plantId === plantId).length, 0);
  }

  async function loadPreview(plantId: number): Promise<void> {
    previewLoading = true; render();
    try { preview = await previewRateio(plantId); }
    catch { preview = null; toast.error('Não foi possível calcular a produção. Verifique se o backend está rodando.'); }
    finally { previewLoading = false; render(); }
  }

  async function loadQualificacao(plantId: number): Promise<void> {
    qualificacaoLoading = true; render();
    try { qualificacao = await getQualificacao(plantId); }
    catch { qualificacao = null; toast.error('Não foi possível calcular a qualificação. Verifique se o backend está rodando.'); }
    finally { qualificacaoLoading = false; render(); }
  }

  async function saveReserva(plantId: number, value: number): Promise<void> {
    loading.show();
    try {
      const updated = await updatePlantRateioConfig(plantId, { reservaPercentual: Math.min(100, Math.max(0, value)) });
      plants = plants.map((item) => item.id === plantId ? updated : item);
      toast.success('Reserva atualizada.'); await loadPreview(plantId);
    } catch { toast.error('Não foi possível salvar a reserva.'); }
    finally { loading.hide(); }
  }

  function continueToDistribution(): void {
    if (!selectedUcIds.size) { toast.error('Selecione pelo menos um cliente qualificado antes de continuar.'); return; }
    stage = 'distribuicao'; render();
  }

  async function confirmRateio(plantId: number, selecoes: Array<{ ucId: number; percentual: number }>): Promise<void> {
    if (!competencia) { toast.error('Escolha a competência (mês) antes de aprovar.'); return; }
    if (confirming) return;
    confirming = true; loading.show(); render();
    try {
      const result = await confirmarSelecaoRateio(plantId, competencia, selecoes);
      confirmation = { conexoesCriadas: result.conexoesCriadas, conexoesAtualizadas: result.conexoesAtualizadas };
      ucs = await getUcs(); selectedUcIds.clear(); overrides.clear(); toast.success('Rateio confirmado com sucesso.'); stage = 'concluido';
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível confirmar o rateio.'); }
    finally { confirming = false; loading.hide(); render(); }
  }

  function renderConcluido(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-summary-card' });
    panel.append(createElement('span', { className: 'eyebrow', textContent: 'Rateio aprovado' }), createElement('h2', { textContent: 'As conexões e o histórico foram atualizados' }), createElement('p', { className: 'settings-hint', textContent: `${confirmation?.conexoesCriadas ?? 0} conexão(ões) criada(s) e ${confirmation?.conexoesAtualizadas ?? 0} atualizada(s).` }));
    const actions = createElement('div', { className: 'form-actions' });
    const again = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Montar outro rateio' });
    const form = createElement('button', { type: 'button', textContent: 'Gerar Formulário Copel' });
    again.addEventListener('click', () => { stage = 'selecionar'; selectedPlantId = null; confirmation = null; render(); });
    form.addEventListener('click', () => props.onOpenFormulario(selectedPlantId)); actions.append(again, form); panel.appendChild(actions); return panel;
  }
}
