// frontend/src/components/PlantDistribuicaoModal.ts
// Modal "Editar distribuição" -- aberto a partir da tela de Usina (aba "UCs
// conectadas"). Mostra, por UC já conectada: consumo, % sugerida (calculada
// pelo motor via GET /rateio/preview, só leitura) e % atual (editável).
// Salvar chama PUT /rateio/distribuicao, que só ATUALIZA conexões que já
// existem -- criar conexão nova continua sendo papel exclusivo do wizard de
// Rateio (Tela 4 -> "Aprovar proposta"), não deste modal.
import { createElement } from '../dom';
import { atualizarDistribuicao, previewRateio } from '../services/rateioService';
import type { PlantRow } from '../services/plantService';

export type PlantDistribuicaoModalUc = {
  ucId: number;
  connectionId: number;
  codigo: string;
  clienteNome: string;
  consumo: number | null;
  percentualAtual: number;
};

type PlantDistribuicaoModalOptions = {
  plant: PlantRow;
  ucs: PlantDistribuicaoModalUc[];
  onSaved: () => void;
  onError: (message: string) => void;
};

export function createPlantDistribuicaoModal({ plant, ucs, onSaved, onError }: PlantDistribuicaoModalOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });

  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  titleText.append(
    createElement('span', { className: 'eyebrow', textContent: plant.nome }),
    createElement('h2', { textContent: 'Editar distribuição' })
  );
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });
  header.append(titleText, closeButton);

  const body = createElement('div', { className: 'rateio-distribuicao' });
  body.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Calculando sugestões...' }));

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar distribuição', type: 'submit' });
  saveButton.disabled = true;
  actions.appendChild(saveButton);

  closeButton.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) overlay.remove();
  });

  let inputs: Array<{ connectionId: number; input: HTMLInputElement }> = [];
  let saving = false;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (saving) return;

    saving = true;
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    try {
      await atualizarDistribuicao(plant.id, inputs.map(({ connectionId, input }) => ({
        connectionId,
        percentual: Number(input.value) || 0
      })));
      overlay.remove();
      onSaved();
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Não foi possível salvar a distribuição.');
    } finally {
      saving = false;
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar distribuição';
    }
  });

  form.append(header, body, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  loadSuggestionsAndRender();

  async function loadSuggestionsAndRender(): Promise<void> {
    let sugeridoPorUc = new Map<number, number>();
    let avisoCarregamento: string | null = null;

    try {
      const preview = await previewRateio(plant.id);
      sugeridoPorUc = new Map(preview.ucs.map((uc) => [uc.ucId, uc.percentualCalculado]));
    } catch {
      avisoCarregamento = 'Não foi possível calcular as sugestões agora. Você ainda pode editar o percentual manualmente.';
    }

    renderBody(sugeridoPorUc, avisoCarregamento);
  }

  function renderBody(sugeridoPorUc: Map<number, number>, avisoCarregamento: string | null): void {
    body.replaceChildren();

    if (avisoCarregamento) {
      body.appendChild(createElement('p', { className: 'empty-state small', textContent: avisoCarregamento }));
    }

    if (ucs.length === 0) {
      body.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhuma UC conectada a esta usina.' }));
      return;
    }

    const list = createElement('div', { className: 'rateio-distribuicao-list' });
    const headerRow = createElement('div', { className: 'rateio-distribuicao-row rateio-distribuicao-header' });
    headerRow.append(
      createElement('span', { textContent: 'Cliente' }),
      createElement('span', { textContent: 'Consumo' }),
      createElement('span', { textContent: '% sugerida' }),
      createElement('span', { textContent: '% atual' })
    );
    list.appendChild(headerRow);

    inputs = [];

    ucs.forEach((uc) => {
      const row = createElement('div', { className: 'rateio-distribuicao-row' });
      const nomeInfo = createElement('div', { className: 'rateio-qualificado-nome' });
      nomeInfo.append(
        createElement('strong', { textContent: uc.clienteNome || uc.codigo }),
        createElement('span', { textContent: uc.codigo })
      );

      const consumoText = createElement('span', {
        textContent: uc.consumo != null ? `${formatNumber(uc.consumo)} kWh` : '-'
      });

      const sugerido = sugeridoPorUc.get(uc.ucId);
      const sugeridaText = createElement('span', {
        className: 'rateio-percentual-sugerido',
        textContent: sugerido != null ? `${formatNumber(sugerido)}%` : '-'
      });

      const input = createElement('input');
      input.type = 'number';
      input.min = '0';
      input.max = '100';
      input.step = '0.01';
      input.value = String(uc.percentualAtual);
      input.addEventListener('input', recalcTotal);

      inputs.push({ connectionId: uc.connectionId, input });

      row.append(nomeInfo, consumoText, sugeridaText, input);
      list.appendChild(row);
    });

    const totalRow = createElement('p', { className: 'settings-hint' });
    body.append(list, totalRow);
    recalcTotal();
    saveButton.disabled = false;

    function recalcTotal(): void {
      const total = inputs.reduce((sum, { input }) => sum + (Number(input.value) || 0), 0);
      totalRow.textContent = `Total desta usina: ${formatNumber(total)}%`;
      totalRow.classList.toggle('rateio-total-excede', total > 100);
    }
  }

  return overlay;
}

function formatNumber(value: number): string {
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}