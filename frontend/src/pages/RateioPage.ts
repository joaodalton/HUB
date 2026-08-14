// frontend/src/pages/RateioPage.ts
// Tela 1 do wizard de Rateio: seleção de usina. Etapas 2-4 (Produção,
// Qualificado, Distribuição) ainda não existem -- "Continuar" leva pra um
// painel "em construção" só pra manter a sequência visível, como combinado
// com o João. Quando a Tela 2 for construída, troca renderEmConstrucao()
// pela etapa de verdade, sem mexer no resto do arquivo.
import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getPlants, plantStatusLabel, plantStatusTone, updatePlantRateioConfig, type PlantRow, type PlantStatusTone } from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';
import { getQualificado, previewRateio, type RateioQualificado, type RateioPreview } from '../services/rateioService';

type Stage = 'selecionar' | 'producao' | 'Qualificado' | 'em-construcao';

const RESERVA_PRESETS = [0, 5, 10, 15];

export function createRateioPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let plants: PlantRow[] = [];
  let ucs: UcRow[] = [];
  let loadError = false;
  let searchTerm = '';
  let selectedPlantId: number | null = null;
  let stage: Stage = 'selecionar';
  let preview: RateioPreview | null = null;
  let previewLoading = false;
  let reservaCustomMode = false;
  let Qualificado: RateioQualificado | null = null;
  let QualificadoLoading = false;
  let mostrandoQualificados = false;
  const selectedUcIds = new Set<number>();

  const layout = createBaseLayout({
    content,
    eyebrow: 'Rateio',
    title: 'Monte o rateio de energia passo a passo'
  });

  loadAll();

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
      renderContent();
    }
  }

  function connectedUcsCount(plantId: number): number {
    return ucs.reduce((count, uc) => count + uc.conexoes.filter((conexao) => conexao.plantId === plantId).length, 0);
  }

  function renderContent(): void {
    if (stage === 'em-construcao') {
      content.replaceChildren(renderEmConstrucao());
      return;
    }

    if (stage === 'producao') {
      const plant = plants.find((item) => item.id === selectedPlantId);
      if (!plant) {
        stage = 'selecionar';
      } else {
        content.replaceChildren(renderStepHeader(2, 'Produção'), renderProducaoStage(plant));
        return;
      }
    }

    if (stage === 'Qualificado') {
      const plant = plants.find((item) => item.id === selectedPlantId);
      if (!plant) {
        stage = 'selecionar';
      } else {
        content.replaceChildren(renderStepHeader(3, 'Qualificado'), renderQualificadoStage(plant));
        return;
      }
    }

    const selectedPlant = plants.find((plant) => plant.id === selectedPlantId) ?? null;

    content.replaceChildren(
      renderStepHeader(1, 'Usina selecionada'),
      selectedPlant ? renderSelectedSummary(selectedPlant) : renderPicker()
    );
  }

  async function loadPreview(plantId: number): Promise<void> {
    previewLoading = true;
    renderContent();

    try {
      preview = await previewRateio(plantId);
    } catch {
      preview = null;
      toast.error('Não foi possível calcular a produção. Verifique se o backend está rodando.');
    } finally {
      previewLoading = false;
      renderContent();
    }
  }

  async function loadQualificado(plantId: number): Promise<void> {
    QualificadoLoading = true;
    renderContent();

    try {
      Qualificado = await getQualificado(plantId);
    } catch {
      Qualificado = null;
      toast.error('Não foi possível calcular a Qualificado. Verifique se o backend está rodando.');
    } finally {
      QualificadoLoading = false;
      renderContent();
    }
  }

  function renderStepHeader(stepNumber: number, title: string): HTMLElement {
    const header = createElement('div', { className: 'rateio-step-header' });
    header.append(
      createElement('span', { className: 'rateio-step-badge', textContent: String(stepNumber) }),
      createElement('h2', { textContent: title })
    );
    return header;
  }

  function renderPicker(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-picker' });
    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Escolha' });
    const heading = createElement('h2', { textContent: 'Selecione a usina para iniciar o rateio' });

    titleText.append(eyebrow, heading);
    title.appendChild(titleText);

    const searchWrap = createElement('div', { className: 'page-actions' });
    const searchInput = createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Pesquisar por nome...';
    searchInput.value = searchTerm;
    searchWrap.appendChild(searchInput);

    const listHolder = createElement('div', { className: 'rateio-plant-list' });

    function refreshList(): void {
      listHolder.replaceChildren();

      if (loadError) {
        listHolder.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nao foi possivel carregar usinas.' }));
        return;
      }

      const filtered = plants.filter((plant) => normalize(plant.nome).includes(normalize(searchTerm)));

      if (filtered.length === 0) {
        listHolder.appendChild(createElement('p', {
          className: 'empty-state small',
          textContent: plants.length === 0 ? 'Nenhuma usina cadastrada ainda.' : 'Nenhuma usina encontrada para essa busca.'
        }));
        return;
      }

      filtered.forEach((plant) => listHolder.appendChild(createPlantPickRow(plant)));
    }

    function createPlantPickRow(plant: PlantRow): HTMLElement {
      const row = createElement('button', { className: 'rateio-plant-row', type: 'button' });
      const iconChip = createElement('span', { className: 'rateio-plant-icon' });
      iconChip.appendChild(createIcon('plants'));

      const info = createElement('div', { className: 'rateio-plant-row-info' });
      info.append(
        createElement('strong', { textContent: plant.nome }),
        createElement('span', { textContent: `${plant.kwPico} kWp · ${connectedUcsCount(plant.id)} UCs conectadas` })
      );

      row.append(iconChip, info, createStatusBadge(plant.status));
      row.addEventListener('click', () => {
        selectedPlantId = plant.id;
        renderContent();
      });

      return row;
    }

    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value;
      refreshList();
    });

    refreshList();
    panel.append(title, searchWrap, listHolder);
    return panel;
  }

  function renderSelectedSummary(plant: PlantRow): HTMLElement {
    const card = createElement('section', { className: 'data-panel rateio-summary-card' });

    const head = createElement('div', { className: 'rateio-summary-head' });
    const iconChip = createElement('span', { className: 'rateio-plant-icon large' });
    iconChip.appendChild(createIcon('plants'));

    const headText = createElement('div', { className: 'rateio-summary-head-text' });
    const nameRow = createElement('div', { className: 'rateio-summary-name-row' });
    nameRow.append(createElement('strong', { textContent: plant.nome }), createStatusBadge(plant.status));

    const sublineParts = [
      `${plant.kwPico} kWp`,
      plant.numModulos ? `${plant.numModulos} modulos` : null,
      plant.concessionaria
    ].filter((part): part is string => Boolean(part));

    const subline = createElement('span', { className: 'rateio-summary-subline', textContent: sublineParts.join(' · ') });

    headText.append(nameRow, subline);
    head.append(iconChip, headText);

    const stats = createElement('div', { className: 'rateio-summary-stats' });
    stats.append(
      createStatRow('Produção média (12m)', plant.producaoMedia != null ? `${plant.producaoMedia.toFixed(1)} kWh` : 'Não cadastrada'),
      createStatRow('UCs conectadas', String(connectedUcsCount(plant.id))),
      createStatRow('Reserva atual', `${plant.reservaPercentual}%`)
    );

    const actions = createElement('div', { className: 'form-actions' });
    const trocarButton = createElement('button', { className: 'secondary-button', textContent: 'Trocar usina', type: 'button' });
    const continuarButton = createElement('button', { textContent: 'Continuar →', type: 'button' });

    trocarButton.addEventListener('click', () => {
      selectedPlantId = null;
      renderContent();
    });

    continuarButton.addEventListener('click', () => {
      stage = 'producao';
      reservaCustomMode = !RESERVA_PRESETS.includes(plant.reservaPercentual);
      renderContent();
      loadPreview(plant.id);
    });

    actions.append(trocarButton, continuarButton);
    card.append(head, stats, actions);
    return card;
  }

  function renderProducaoStage(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const panel = createElement('section', { className: 'data-panel rateio-producao' });

    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    titleText.append(
      createElement('span', { className: 'eyebrow', textContent: plant.nome }),
      createElement('h2', { textContent: 'Produção disponível para o ciclo' })
    );
    title.appendChild(titleText);
    panel.appendChild(title);

    if (previewLoading || !preview) {
      panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Calculando...' }));
    } else {
      const statsGrid = createElement('div', { className: 'rateio-producao-stats' });
      const reservaKwh = round2(preview.producaoMedia - preview.producaoDisponivel);

      statsGrid.append(
        createProducaoStat('Disponível', `${formatNumber(preview.producaoMedia)} kWh`, 'neutral'),
        createProducaoStat(`Reserva (${preview.reservaPercentual}%)`, `${formatNumber(reservaKwh)} kWh`, 'warning'),
        createProducaoStat('Para rateio', `${formatNumber(preview.producaoDisponivel)} kWh`, 'success')
      );
      panel.appendChild(statsGrid);

      if (preview.warnings.length > 0) {
        const warningsBox = createElement('div', { className: 'rateio-warnings' });
        preview.warnings.forEach((warning) => {
          warningsBox.appendChild(createElement('p', { textContent: `⚠ ${warning}` }));
        });
        panel.appendChild(warningsBox);
      }
    }

    panel.append(createReservaField(plant), createProducaoMediaHint(plant));

    const actions = createElement('div', { className: 'form-actions' });
    const voltarButton = createElement('button', { className: 'secondary-button', textContent: '← Voltar', type: 'button' });
    const continuarButton = createElement('button', { textContent: 'Continuar →', type: 'button' });

    voltarButton.addEventListener('click', () => {
      stage = 'selecionar';
      renderContent();
    });
    continuarButton.addEventListener('click', () => {
      stage = 'Qualificado';
      renderContent();
      loadQualificado(plant.id);
    });

    actions.append(voltarButton, continuarButton);
    wrapper.append(panel, actions);
    return wrapper;
  }

  function createProducaoStat(label: string, value: string, tone: 'neutral' | 'warning' | 'success'): HTMLElement {
    const card = createElement('article', { className: `rateio-producao-stat tone-${tone}` });
    card.append(
      createElement('span', { className: 'rateio-producao-stat-label', textContent: label }),
      createElement('strong', { className: 'rateio-producao-stat-value', textContent: value })
    );
    return card;
  }

  function createReservaField(plant: PlantRow): HTMLElement {
    const field = createElement('div', { className: 'rateio-reserva-field' });
    field.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Estratégia de reserva' }));

    const buttonsRow = createElement('div', { className: 'rateio-reserva-buttons' });

    RESERVA_PRESETS.forEach((value) => {
      const isActive = !reservaCustomMode && plant.reservaPercentual === value;
      const button = createElement('button', {
        className: isActive ? 'small-button active' : 'small-button',
        textContent: `${value}%`,
        type: 'button'
      });
      button.addEventListener('click', () => saveReserva(plant.id, value));
      buttonsRow.appendChild(button);
    });

    const customButton = createElement('button', {
      className: reservaCustomMode ? 'small-button active' : 'small-button',
      textContent: 'Personalizado',
      type: 'button'
    });
    customButton.addEventListener('click', () => {
      reservaCustomMode = true;
      renderContent();
    });
    buttonsRow.appendChild(customButton);

    field.appendChild(buttonsRow);

    if (reservaCustomMode) {
      const customRow = createElement('div', { className: 'rateio-custom-row' });
      const input = createElement('input');
      input.type = 'number';
      input.min = '0';
      input.max = '100';
      input.step = '0.5';
      input.value = String(plant.reservaPercentual);
      input.placeholder = '0 a 100';

      const saveButton = createElement('button', { className: 'small-button', textContent: 'Salvar', type: 'button' });
      saveButton.addEventListener('click', () => saveReserva(plant.id, Number(input.value) || 0));

      customRow.append(input, saveButton);
      field.appendChild(customRow);
    }

    return field;
  }

  async function saveReserva(plantId: number, value: number): Promise<void> {
    const clamped = Math.min(100, Math.max(0, value));

    loading.show();
    try {
      const updated = await updatePlantRateioConfig(plantId, { reservaPercentual: clamped });
      plants = plants.map((item) => (item.id === plantId ? updated : item));
      toast.success('Reserva atualizada.');
      await loadPreview(plantId);
    } catch {
      toast.error('Não foi possível salvar a reserva.');
    } finally {
      loading.hide();
    }
  }

  function createProducaoMediaHint(plant: PlantRow): HTMLElement {
    const box = createElement('p', { className: 'settings-hint' });
    box.textContent = plant.producaoMediaManual != null
      ? `Produção média definida manualmente: ${formatNumber(plant.producaoMediaManual)} kWh. Para alterar, edite a usina em "Usinas".`
      : 'Produção média calculada pela média dos meses cadastrados. Para definir um valor manual ou cadastrar produção mensal, edite a usina em "Usinas".';
    return box;
  }

  function renderQualificadoStage(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const panel = createElement('section', { className: 'data-panel rateio-Qualificado' });

    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    titleText.append(
      createElement('span', { className: 'eyebrow', textContent: plant.nome }),
      createElement('h2', { textContent: 'Funil dos Qualificados' })
    );
    title.appendChild(titleText);
    panel.appendChild(title);

    if (QualificadoLoading || !Qualificado) {
      panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Calculando...' }));
    } else {
      const funilGrid = createElement('div', { className: 'rateio-funil-grid' });
      funilGrid.append(
        createFunilStat('Total de clientes', Qualificado.totalClientes),
        createFunilStat('Qualificados', Qualificado.qualificados)
      );
      panel.appendChild(funilGrid);

      const regras = createElement('div', { className: 'rateio-regras' });
      regras.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Regras aplicadas' }));
      const regrasList = createElement('ul', { className: 'rateio-regras-list' });
      ['Contrato dentro de 90 dias', 'Leitura posterior à usina'].forEach((regra) => {
        regrasList.appendChild(createElement('li', { textContent: regra }));
      });
      regras.appendChild(regrasList);
      panel.appendChild(regras);

      const verButton = createElement('button', {
        className: mostrandoQualificados ? 'secondary-button' : 'small-button',
        textContent: mostrandoQualificados ? 'Ocultar qualificados' : `Ver qualificados (${Qualificado.qualificados})`,
        type: 'button'
      });
      verButton.addEventListener('click', () => {
        mostrandoQualificados = !mostrandoQualificados;
        renderContent();
      });
      panel.appendChild(verButton);

      if (mostrandoQualificados) {
        panel.appendChild(renderQualificadosList(Qualificado));
      }
    }

    const actions = createElement('div', { className: 'form-actions' });
    const voltarButton = createElement('button', { className: 'secondary-button', textContent: '← Voltar', type: 'button' });
    const continuarButton = createElement('button', { textContent: 'Continuar →', type: 'button' });

    voltarButton.addEventListener('click', () => {
      stage = 'producao';
      renderContent();
    });
    continuarButton.addEventListener('click', () => {
      if (selectedUcIds.size === 0) {
        toast.error('Selecione pelo menos um cliente qualificado antes de continuar.');
        return;
      }
      stage = 'em-construcao';
      renderContent();
    });

    actions.append(voltarButton, continuarButton);
    wrapper.append(panel, actions);
    return wrapper;
  }

  function createFunilStat(label: string, value: number): HTMLElement {
    const card = createElement('article', { className: 'rateio-funil-stat' });
    card.append(
      createElement('span', { className: 'rateio-funil-stat-label', textContent: label }),
      createElement('strong', { className: 'rateio-funil-stat-value', textContent: String(value) })
    );
    return card;
  }

  function renderQualificadosList(data: RateioQualificado): HTMLElement {
    const list = createElement('div', { className: 'rateio-qualificados-list' });
    const qualificadas = data.ucs.filter((uc) => uc.qualificado);

    if (qualificadas.length === 0) {
      list.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhum cliente qualificado para esta usina no momento.' }));
      return list;
    }

    const header = createElement('div', { className: 'rateio-qualificado-row rateio-qualificado-header' });
    header.append(
      createElement('span', { textContent: 'Cliente' }),
      createElement('span', { textContent: 'Consumo' }),
      createElement('span', { textContent: '% sugerido' }),
      createElement('span', { textContent: '' })
    );
    list.appendChild(header);

    qualificadas.forEach((uc) => {
      const row = createElement('div', { className: 'rateio-qualificado-row' });
      const nomeInfo = createElement('div', { className: 'rateio-qualificado-nome' });
      nomeInfo.append(
        createElement('strong', { textContent: uc.clienteNome ?? uc.ucCodigo }),
        createElement('span', { textContent: uc.ucCodigo })
      );

      const consumo = createElement('span', { textContent: uc.consumo != null ? `${formatNumber(uc.consumo)} kWh` : '-' });
      const percentual = createElement('span', { textContent: `${formatNumber(uc.percentualSugerido)}%` });

      const checkbox = createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selectedUcIds.has(uc.ucId);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) selectedUcIds.add(uc.ucId);
        else selectedUcIds.delete(uc.ucId);
        renderContent();
      });

      row.append(nomeInfo, consumo, percentual, checkbox);
      list.appendChild(row);
    });

    return list;
  }

  function renderEmConstrucao(): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const plant = plants.find((item) => item.id === selectedPlantId);

    const panel = createElement('section', { className: 'placeholder-panel' });
    panel.append(
      createElement('p', { textContent: plant ? `Usina selecionada: ${plant.nome}` : 'Nenhuma usina selecionada.' }),
      createElement('p', { textContent: `${selectedUcIds.size} cliente(s) qualificado(s) selecionado(s) para a distribuição.` }),
      createElement('p', { textContent: 'A etapa de Distribuição chega na próxima sessão.' })
    );

    const actions = createElement('div', { className: 'form-actions' });
    const voltarButton = createElement('button', { className: 'secondary-button', textContent: '← Voltar', type: 'button' });
    voltarButton.addEventListener('click', () => {
      stage = 'Qualificado';
      renderContent();
    });
    actions.appendChild(voltarButton);

    wrapper.append(panel, actions);
    return wrapper;
  }

  function createStatusBadge(status: string): HTMLElement {
    const tone: PlantStatusTone = plantStatusTone(status);
    return createElement('span', {
      className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`,
      textContent: plantStatusLabel(status)
    });
  }
}

function createStatRow(label: string, value: string): HTMLElement {
  const row = createElement('div', { className: 'rateio-stat-row' });
  row.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
  return row;
}

function formatNumber(value: number): string {
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}