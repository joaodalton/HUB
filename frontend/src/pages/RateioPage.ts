// frontend/src/pages/RateioPage.ts
// Wizard de Rateio: Tela 1 (seleção de usina) → Tela 2 (produção) →
// Tela 3 (qualificação) → Tela 4 (distribuição) → confirmação.
// "Aprovar proposta" chama POST /rateio/confirmar (rateioService.ts), que
// cria as PlantConnection novas com o % escolhido -- ver renderConcluido()
// no fim do arquivo.
import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getPlants, plantStatusLabel, plantStatusTone, updatePlantRateioConfig, type PlantRow, type PlantStatusTone } from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';
import { confirmarSelecaoRateio, getQualificacao, previewRateio, type RateioQualificacao, type RateioPreview } from '../services/rateioService';
import {
  gerarFormularioPdf,
  gerarTermosAdesaoPdf,
  getFormularioTabela,
  verificarDocumentosFormulario,
  type FormularioLinha,
  type FormularioTabela
} from '../services/rateioFormularioService';
import { config } from '../services/config';
import { getEmpresaDocumentos, type EmpresaDocumentos } from '../services/empresaService';

type Stage = 'selecionar' | 'producao' | 'qualificacao' | 'distribuicao' | 'concluido';
type RateioTab = 'montar' | 'formulario';

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
  let selectedFormularioPlantId: number | null = null;
  let activeTab: RateioTab = 'montar';
  let stage: Stage = 'selecionar';
  let preview: RateioPreview | null = null;
  let previewLoading = false;
  let reservaCustomMode = false;
  let qualificacao: RateioQualificacao | null = null;
  let qualificacaoLoading = false;
  let mostrandoQualificados = false;
  let competencia = defaultCompetencia();
  let confirmando = false;
  let resultadoConfirmacao: { conexoesCriadas: number; conexoesAtualizadas: number } | null = null;
  const selectedUcIds = new Set<number>();
  const percentualRealOverrides = new Map<number, number>();

  let formularioGerando = false;
  let formularioArquivosGerados: { formulario: string; termos: string } | null = null;
  let empresaDocumentos: EmpresaDocumentos | null = null;
  let formularioTabela: FormularioTabela | null = null;
  let formularioTabelaPlantId: number | null = null;
  let formularioTabelaCarregando = false;
  let formularioTabelaErro = '';
  let formularioTabelaRequestId = 0;
  let formularioVerificando = false;
  let formularioVerificacao: { ok: boolean; faltando: Array<{ clienteId: number | null; ucId: number | null; nome: string }> } | null = null;
  let responsavelNome = '';
  let responsavelCpf = '';

  getEmpresaDocumentos().then((data) => {
    empresaDocumentos = data;
    if (activeTab === 'formulario') renderContent();
  }).catch(() => { empresaDocumentos = null; });

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
    const tabs = renderTabs();
    if (activeTab === 'formulario') {
      const plant = plants.find((item) => item.id === selectedFormularioPlantId);
      content.replaceChildren(tabs, plant ? renderFormularioRevisao(plant) : renderFormularioPicker());
      return;
    }

    if (stage === 'concluido') {
      content.replaceChildren(tabs, renderConcluido());
      return;
    }

    if (stage === 'producao') {
      const plant = plants.find((item) => item.id === selectedPlantId);
      if (!plant) {
        stage = 'selecionar';
      } else {
        content.replaceChildren(tabs, renderStepHeader(2, 'Produção'), renderProducaoStage(plant));
        return;
      }
    }

    if (stage === 'qualificacao') {
      const plant = plants.find((item) => item.id === selectedPlantId);
      if (!plant) {
        stage = 'selecionar';
      } else {
        content.replaceChildren(tabs, renderStepHeader(3, 'Qualificação'), renderQualificacaoStage(plant));
        return;
      }
    }

    if (stage === 'distribuicao') {
      const plant = plants.find((item) => item.id === selectedPlantId);
      if (!plant || !qualificacao) {
        stage = 'selecionar';
      } else {
        content.replaceChildren(tabs, renderStepHeader(4, 'Distribuição'), renderDistribuicaoStage(plant, qualificacao));
        return;
      }
    }

    content.replaceChildren(tabs, renderStepHeader(1, 'Selecionar usina'), renderPicker());
  }

  function renderTabs(): HTMLElement {
    const tabs = createElement('div', { className: 'rateio-tabs' });
    tabs.setAttribute('role', 'tablist');
    const montar = createElement('button', { className: activeTab === 'montar' ? 'active' : '', type: 'button', textContent: 'Montar Rateio' });
    const formulario = createElement('button', { className: activeTab === 'formulario' ? 'active' : '', type: 'button', textContent: 'Gerar Formulário Copel' });
    montar.addEventListener('click', () => { activeTab = 'montar'; renderContent(); });
    formulario.addEventListener('click', () => { activeTab = 'formulario'; renderContent(); });
    tabs.append(montar, formulario);
    return tabs;
  }

  function renderFormularioPicker(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-picker' });
    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    titleText.append(
      createElement('span', { className: 'eyebrow', textContent: 'Formulário Copel' }),
      createElement('h2', { textContent: 'Selecione a usina com rateio aprovado' })
    );
    title.appendChild(titleText);
    const select = createElement('select');
    select.setAttribute('aria-label', 'Usina com rateio aprovado');
    const placeholder = createElement('option', { textContent: 'Selecione uma usina...' });
    placeholder.value = '';
    select.appendChild(placeholder);
    plants.forEach((plant) => {
      const option = createElement('option', { textContent: `${plant.nome} — UC ${plant.uc ?? 'não informada'}` });
      option.value = String(plant.id);
      select.appendChild(option);
    });
    select.addEventListener('change', () => {
      selectedFormularioPlantId = Number(select.value) || null;
      limparFormulario();
      renderContent();
    });
    panel.append(title, createElement('label', {
      className: 'rateio-field-label',
      textContent: 'Usina'
    }), select, createElement('p', {
      className: 'settings-hint',
      textContent: 'Esta etapa apenas lê as conexões confirmadas; nenhum rateio será recalculado.'
    }));
    return panel;
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

  async function loadQualificacao(plantId: number): Promise<void> {
    qualificacaoLoading = true;
    renderContent();

    try {
      qualificacao = await getQualificacao(plantId);
    } catch {
      qualificacao = null;
      toast.error('Não foi possível calcular a qualificação. Verifique se o backend está rodando.');
    } finally {
      qualificacaoLoading = false;
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
      const isActive = plant.id === selectedPlantId;
      const row = createElement('button', { className: isActive ? 'rateio-plant-row active' : 'rateio-plant-row', type: 'button' });
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
        stage = 'producao';
        reservaCustomMode = !RESERVA_PRESETS.includes(plant.reservaPercentual);
        renderContent();
        loadPreview(plant.id);
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
      stage = 'qualificacao';
      renderContent();
      loadQualificacao(plant.id);
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

  function renderQualificacaoStage(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const panel = createElement('section', { className: 'data-panel rateio-qualificacao-panel' });

    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    titleText.append(
      createElement('span', { className: 'eyebrow', textContent: plant.nome }),
      createElement('h2', { textContent: 'Funil dos Qualificados' })
    );
    title.appendChild(titleText);
    panel.appendChild(title);

    if (qualificacaoLoading || !qualificacao) {
      panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Calculando...' }));
    } else {
      const funilGrid = createElement('div', { className: 'rateio-funil-grid' });
      funilGrid.append(
        createFunilStat('Total de clientes', qualificacao.totalClientes),
        createFunilStat('Qualificados', qualificacao.qualificados)
      );
      panel.appendChild(funilGrid);

      const regras = createElement('div', { className: 'rateio-regras' });
      regras.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Regras aplicadas' }));
      const regrasList = createElement('ul', { className: 'rateio-regras-list' });
      // Só a regra que o backend calcula de verdade -- "Contrato dentro de
      // 90 dias" saiu daqui porque nunca foi implementada, era só decorativa.
      ['Leitura posterior à usina'].forEach((regra) => {
        regrasList.appendChild(createElement('li', { textContent: regra }));
      });
      regras.appendChild(regrasList);
      panel.appendChild(regras);

      const verButton = createElement('button', {
        className: mostrandoQualificados ? 'secondary-button' : 'small-button',
        textContent: mostrandoQualificados ? 'Ocultar qualificados' : `Ver qualificados (${qualificacao.qualificados})`,
        type: 'button'
      });
      verButton.addEventListener('click', () => {
        mostrandoQualificados = !mostrandoQualificados;
        renderContent();
      });
      panel.appendChild(verButton);

      if (mostrandoQualificados) {
        panel.appendChild(renderQualificadosList(qualificacao));
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
      stage = 'distribuicao';
      renderContent();
    });

    actions.append(voltarButton, continuarButton);
    wrapper.append(panel, actions);
    return wrapper;
  }

  function renderDistribuicaoStage(plant: PlantRow, qualificacaoData: RateioQualificacao): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const panel = createElement('section', { className: 'data-panel rateio-distribuicao' });

    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    titleText.append(
      createElement('span', { className: 'eyebrow', textContent: plant.nome }),
      createElement('h2', { textContent: 'Proposta de distribuição' })
    );
    title.appendChild(titleText);
    panel.appendChild(title);

    const selecionados = qualificacaoData.ucs.filter((uc) => selectedUcIds.has(uc.ucId));

    if (selecionados.length === 0) {
      panel.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhum cliente selecionado. Volte pra etapa anterior.' }));
      wrapper.appendChild(panel);
      return wrapper;
    }

    const summary = createElement('div', { className: 'rateio-funil-grid' });
    const energiaStat = createFunilStat('Energia distribuída', '—');
    const saldoStat = createFunilStat('Saldo restante', '—');
    summary.append(energiaStat, saldoStat);
    panel.appendChild(summary);

    const list = createElement('div', { className: 'rateio-distribuicao-list' });
    const header = createElement('div', { className: 'rateio-distribuicao-row rateio-distribuicao-header' });
    header.append(
      createElement('span', { textContent: 'Cliente' }),
      createElement('span', { textContent: 'Consumo' }),
      createElement('span', { textContent: '% sugerida' }),
      createElement('span', { textContent: '% real' })
    );
    list.appendChild(header);

    const inputs: Array<{ ucId: number; input: HTMLInputElement }> = [];

    selecionados.forEach((uc) => {
      const row = createElement('div', { className: 'rateio-distribuicao-row' });
      const nomeInfo = createElement('div', { className: 'rateio-qualificado-nome' });
      nomeInfo.append(
        createElement('strong', { textContent: uc.clienteNome ?? uc.ucCodigo }),
        createElement('span', { textContent: uc.ucCodigo })
      );

      const consumo = createElement('span', { textContent: uc.consumo != null ? `${formatNumber(uc.consumo)} kWh` : '-' });
      const sugerida = createElement('span', { className: 'rateio-percentual-sugerido', textContent: `${formatNumber(uc.percentualSugerido)}%` });

      const realInput = createElement('input');
      realInput.type = 'number';
      realInput.min = '0';
      realInput.max = '100';
      realInput.step = '0.01';
      const valorInicial = percentualRealOverrides.get(uc.ucId) ?? uc.percentualSugerido;
      realInput.value = String(valorInicial);
      percentualRealOverrides.set(uc.ucId, valorInicial);

      realInput.addEventListener('input', () => {
        const value = Number(realInput.value) || 0;
        percentualRealOverrides.set(uc.ucId, value);
        recalcSummary();
      });

      inputs.push({ ucId: uc.ucId, input: realInput });

      row.append(nomeInfo, consumo, sugerida, realInput);
      list.appendChild(row);
    });

    panel.appendChild(list);

    function recalcSummary(): void {
      const producaoDisponivel = preview?.producaoDisponivel ?? 0;
      const percentualTotal = inputs.reduce((sum, { input }) => sum + (Number(input.value) || 0), 0);
      const energiaDistribuida = round2((percentualTotal / 100) * producaoDisponivel);
      const saldoRestante = round2(producaoDisponivel - energiaDistribuida);

      energiaStat.querySelector('strong')!.textContent = `${formatNumber(energiaDistribuida)} kWh`;
      saldoStat.querySelector('strong')!.textContent = `${formatNumber(saldoRestante)} kWh`;
      saldoStat.classList.toggle('tone-danger', saldoRestante < 0);
    }

    recalcSummary();

    const competenciaField = createElement('label', { className: 'form-field' });
    const competenciaLabel = createElement('span', { textContent: 'Competência (mês de referência)' });
    const competenciaInput = createElement('input');
    competenciaInput.type = 'month';
    competenciaInput.value = competencia;
    competenciaInput.addEventListener('input', () => { competencia = competenciaInput.value; });
    competenciaField.append(competenciaLabel, competenciaInput);
    panel.appendChild(competenciaField);

    const actions = createElement('div', { className: 'form-actions' });
    const voltarButton = createElement('button', { className: 'secondary-button', textContent: '← Voltar', type: 'button' });
    const aprovarButton = createElement('button', { textContent: 'Aprovar proposta', type: 'button' });

    voltarButton.addEventListener('click', () => {
      stage = 'qualificacao';
      renderContent();
    });
    aprovarButton.addEventListener('click', async () => {
      if (!competencia) {
        toast.error('Escolha a competência (mês) antes de aprovar.');
        return;
      }
      if (confirmando) return;

      confirmando = true;
      aprovarButton.disabled = true;
      aprovarButton.textContent = 'Salvando...';
      loading.show();

      try {
        const selecoes = inputs.map(({ ucId, input }) => ({ ucId, percentual: Number(input.value) || 0 }));
        const resultado = await confirmarSelecaoRateio(plant.id, competencia, selecoes);

        resultadoConfirmacao = {
          conexoesCriadas: resultado.conexoesCriadas,
          conexoesAtualizadas: resultado.conexoesAtualizadas
        };

        // Recarrega UCs pra "UCs conectadas" (Tela 1/resumo) já refletir as
        // conexões novas -- sem isso o número ficaria desatualizado até um F5.
        ucs = await getUcs();
        selectedUcIds.clear();
        percentualRealOverrides.clear();

        toast.success('Rateio confirmado com sucesso.');
        stage = 'concluido';
        renderContent();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível confirmar o rateio.');
      } finally {
        confirmando = false;
        aprovarButton.disabled = false;
        aprovarButton.textContent = 'Aprovar proposta';
        loading.hide();
      }
    });

    actions.append(voltarButton, aprovarButton);
    wrapper.append(panel, actions);
    return wrapper;
  }

  function createFunilStat(label: string, value: number | string): HTMLElement {
    const card = createElement('article', { className: 'rateio-funil-stat' });
    card.append(
      createElement('span', { className: 'rateio-funil-stat-label', textContent: label }),
      createElement('strong', { className: 'rateio-funil-stat-value', textContent: String(value) })
    );
    return card;
  }

  function renderConcluido(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-summary-card' });
    panel.append(
      createElement('span', { className: 'eyebrow', textContent: 'Rateio aprovado' }),
      createElement('h2', { textContent: 'As conexões e o histórico foram atualizados' }),
      createElement('p', {
        className: 'settings-hint',
        textContent: `${resultadoConfirmacao?.conexoesCriadas ?? 0} conexão(ões) criada(s) e ${resultadoConfirmacao?.conexoesAtualizadas ?? 0} atualizada(s).`
      })
    );
    const actions = createElement('div', { className: 'form-actions' });
    const novo = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Montar outro rateio' });
    const formulario = createElement('button', { type: 'button', textContent: 'Gerar Formulário Copel' });
    novo.addEventListener('click', () => { stage = 'selecionar'; selectedPlantId = null; resultadoConfirmacao = null; renderContent(); });
    formulario.addEventListener('click', () => {
      selectedFormularioPlantId = selectedPlantId;
      activeTab = 'formulario';
      renderContent();
    });
    actions.append(novo, formulario);
    panel.appendChild(actions);
    return panel;
  }

  function renderQualificadosList(data: RateioQualificacao): HTMLElement {
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

  function createEditableTable<T extends { ordem: number }>({ columns, rows, emptyMessage, getRowKey, onChange }: {
    columns: Array<{ key: keyof T; label: string; align?: 'right'; render?: (row: T) => string; editable?: boolean; onChange?: (row: T, value: string) => void }>;
    rows: T[];
    emptyMessage?: string;
    getRowKey: (row: T) => number | string;
    onChange?: (row: T, value: string) => void;
  }): HTMLElement {
    const table = createElement('div', { className: 'rateio-table' });
    const header = createElement('div', { className: 'rateio-table-header' });
    columns.forEach((col) => {
      const th = createElement('div', { className: `rateio-table-cell ${col.align === 'right' ? 'right' : ''}`, textContent: col.label });
      header.appendChild(th);
    });
    table.appendChild(header);

    if (rows.length === 0) {
      table.appendChild(createElement('p', { className: 'empty-state small', textContent: emptyMessage ?? 'Nenhum registro.' }));
    } else {
      rows.forEach((row) => {
        const tr = createElement('div', { className: 'rateio-table-row' });
        tr.dataset.rowKey = String(getRowKey(row));
        columns.forEach((col) => {
          const cell = createElement('div', { className: `rateio-table-cell ${col.align === 'right' ? 'right' : ''}` });
          if (col.render) {
            cell.textContent = col.render!(row);
          } else {
            const val = row[col.key];
            cell.textContent = val != null ? String(val) : '';
          }
          if (col.editable && col.onChange) {
            const input = createElement('input');
            input.type = 'text';
            input.value = (row[col.key] as string) ?? '';
            input.addEventListener('change', () => {
              col.onChange!(row, input.value);
              onChange?.(row, input.value);
            });
            cell.replaceChildren(input);
          }
          tr.appendChild(cell);
        });
        table.appendChild(tr);
      });
    }
    return table;
  }

  function createResponsavelField(label: string, value: string, onChange: (value: string) => void): HTMLElement {
    const field = createElement('div', { className: 'rateio-form-field' });
    field.appendChild(createElement('label', { className: 'settings-subheading', textContent: label }));
    const input = createElement('input');
    input.type = 'text';
    input.value = value;
    input.addEventListener('input', () => onChange(input.value));
    field.appendChild(input);
    return field;
  }

  function createTermoAdesaoBadge(row: FormularioLinha): HTMLElement {
    const badge = createElement('span', { className: 'termo-badge' });
    if (row.termoAdesaoOk) {
      badge.appendChild(createIcon('check'));
      badge.appendChild(document.createTextNode('OK'));
      badge.classList.add('ok');
    } else {
      badge.appendChild(createIcon('pending'));
      badge.appendChild(document.createTextNode('Faltando'));
      badge.classList.add('falta');
    }
    return badge;
  }

  function limparFormulario(): void {
    formularioTabelaRequestId += 1;
    formularioTabela = null;
    formularioTabelaPlantId = null;
    formularioTabelaCarregando = false;
    formularioTabelaErro = '';
    formularioVerificando = false;
    formularioVerificacao = null;
    responsavelNome = '';
    responsavelCpf = '';
  }

  async function carregarTabelaFormulario(plantId: number): Promise<void> {
    const requestId = ++formularioTabelaRequestId;
    formularioTabelaCarregando = true;
    formularioTabelaErro = '';
    formularioTabela = null;
    formularioTabelaPlantId = plantId;

    try {
      const tabela = await getFormularioTabela(plantId);
      if (requestId !== formularioTabelaRequestId) return;
      formularioTabela = tabela;
    } catch (error) {
      if (requestId !== formularioTabelaRequestId) return;
      formularioTabela = null;
      formularioTabelaErro = error instanceof Error
        ? `Não foi possível carregar a tabela: ${error.message}`
        : 'Não foi possível carregar a tabela. Verifique o backend.';
    } finally {
      if (requestId !== formularioTabelaRequestId) return;
      formularioTabelaCarregando = false;
      if (activeTab === 'formulario' && selectedFormularioPlantId === plantId) renderContent();
    }
  }

  function renderFormularioRevisao(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const backLink = createElement('a', { className: 'rateio-back-link' });
    backLink.href = '#';
    backLink.textContent = '← Selecionar outra usina';
    backLink.addEventListener('click', (e) => {
      e.preventDefault();
      selectedFormularioPlantId = null;
      limparFormulario();
      renderContent();
    });

    const panel = createElement('section', { className: 'data-panel rateio-formulario-panel' });
    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    titleText.append(
      createElement('span', { className: 'eyebrow', textContent: 'Revisão do formulário' }),
      createElement('h2', { textContent: 'Formulário Copel — Rateio de Associação' })
    );
    title.appendChild(titleText);
    panel.appendChild(title);

    if (formularioTabelaPlantId !== plant.id && !formularioTabelaCarregando) {
      carregarTabelaFormulario(plant.id);
    }

    function renderContent(): void {
      if (formularioTabelaErro) {
        panel.replaceChildren(title, createElement('p', { className: 'empty-state', textContent: formularioTabelaErro }));
        wrapper.appendChild(panel);
        return;
      }
      if (!formularioTabela || formularioTabelaPlantId !== plant.id) {
        panel.replaceChildren(title, createElement('p', { className: 'loading-state', textContent: 'Carregando tabela...' }));
        wrapper.appendChild(panel);
        return;
      }

      const tabelaAtual = formularioTabela;

      panel.replaceChildren(title);
      panel.appendChild(createElement('p', {
        className: 'settings-hint',
        textContent: `UC geradora: ${tabelaAtual.ucGeradora ?? '-'} · UC âncora: ${tabelaAtual.ucAncora ?? '-'} (sempre a própria usina)`
      }));

      if (tabelaAtual.excedeLimiteLinhas) {
        panel.appendChild(createElement('p', {
          className: 'empty-state small',
          textContent: `Esta usina tem ${tabelaAtual.linhas.length} UCs beneficiárias, mas o formulário da Copel só suporta 24. Não será possível gerar o PDF até ajustar.`
        }));
      }

      const table = createEditableTable<FormularioLinha>({
        columns: [
          { key: 'ordem', label: '#', align: 'right' },
          { key: 'nome', label: 'Nome do titular', editable: true, onChange: (row, value) => { row.nome = value; } },
          { key: 'documento', label: 'CPF/CNPJ', editable: true, onChange: (row, value) => { row.documento = value; } },
          { key: 'ucIdentificacao', label: 'UC', editable: true, onChange: (row, value) => { row.ucIdentificacao = value; } },
          { key: 'percentual', label: '%', align: 'right', editable: true, onChange: (row, value) => { row.percentual = Number(value.replace(',', '.')) || 0; } },
          { key: 'termoAdesaoOk', label: 'Termo de adesão', render: (row) => createTermoAdesaoBadge(row).outerHTML }
        ],
        rows: tabelaAtual.linhas,
        emptyMessage: 'Nenhuma UC beneficiária conectada a esta usina ainda.',
        getRowKey: (row) => row.ordem,
        onChange: () => {
          tabelaAtual.somaPercentual = round2(tabelaAtual.linhas.reduce((sum, linha) => sum + linha.percentual, 0));
          formularioVerificacao = null;
          renderContent();
        }
      });
      panel.appendChild(table);

      const somaRow = createElement('p', { className: 'settings-hint' });
      somaRow.textContent = `Soma dos percentuais: ${formatNumber(tabelaAtual.somaPercentual)}%`;
      somaRow.classList.toggle('rateio-total-excede', tabelaAtual.somaPercentual > 100);
      panel.appendChild(somaRow);

      const responsavelFields = createElement('div', { className: 'form-grid' });
      responsavelFields.append(
        createResponsavelField('Nome do responsável (assina o formulário)', responsavelNome, (value) => { responsavelNome = value; }),
        createResponsavelField('CPF do responsável', responsavelCpf, (value) => { responsavelCpf = value; })
      );
      panel.appendChild(responsavelFields);

      const documentosEmpresaOk = Boolean(empresaDocumentos?.cnpj && empresaDocumentos?.estatuto);
      const podeGerar = !tabelaAtual.excedeLimiteLinhas
        && tabelaAtual.linhas.length > 0
        && tabelaAtual.somaPercentual <= 100
        && formularioVerificacao?.ok === true
        && documentosEmpresaOk;

      if (!documentosEmpresaOk) {
        panel.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Anexe o CNPJ e o Estatuto em Dados da Empresa antes de gerar o pacote.' }));
      }

      const actions = createElement('div', { className: 'form-actions' });
      const verificarButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
      verificarButton.append(createIcon('check'), document.createTextNode('Verificar documentos'));
      verificarButton.disabled = formularioVerificando;
      verificarButton.addEventListener('click', () => handleVerificarDocumentos(tabelaAtual.plantId));

      const gerarButton = createElement('button', { textContent: 'Gerar formulário (PDF)', type: 'button' });
      gerarButton.disabled = !podeGerar || formularioGerando;
      gerarButton.title = podeGerar ? '' : 'Ajuste os pontos acima antes de gerar.';
      gerarButton.addEventListener('click', () => handleGerarDocumentos(tabelaAtual, responsavelNome, responsavelCpf));

      actions.append(verificarButton, gerarButton);
      panel.appendChild(actions);

      if (formularioArquivosGerados) {
        panel.appendChild(renderFormularioDownloads(formularioArquivosGerados));
      }

      wrapper.appendChild(panel);
    }

    function renderFormularioDownloads(arquivos: { formulario: string; termos: string }): HTMLElement {
      const box = createElement('div', { className: 'rateio-formulario-downloads' });
      box.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Arquivos gerados' }));

      const list = createElement('div', { className: 'button-group' });
      list.append(
        createDownloadLink('Formulário Copel', arquivos.formulario),
        createDownloadLink('Termos de adesão (mesclado)', arquivos.termos)
      );

      if (empresaDocumentos?.cnpj) {
        list.appendChild(createDownloadLink('CNPJ', `${config.apiBaseUrl}${config.apiPrefix}/documents/${empresaDocumentos.cnpj.id}/download`, false));
      }
      if (empresaDocumentos?.estatuto) {
        list.appendChild(createDownloadLink('Estatuto', `${config.apiBaseUrl}${config.apiPrefix}/documents/${empresaDocumentos.estatuto.id}/download`, false));
      }

      box.appendChild(list);
      return box;
    }

    function createDownloadLink(label: string, href: string, isBlob = true): HTMLElement {
      const link = createElement('a', { className: 'secondary-button', textContent: label });
      link.href = href;
      if (isBlob) link.download = `${label.toLowerCase().replace(/\s+/g, '-')}.pdf`;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      return link;
    }

    async function handleVerificarDocumentos(plantId: number): Promise<void> {
      formularioVerificando = true;
      renderContent();

      try {
        formularioVerificacao = await verificarDocumentosFormulario(plantId);
        if (!formularioVerificacao.ok) {
          const nomes = formularioVerificacao.faltando.map((item) => item.nome).join(', ');
          toast.error(`Faltam termos de adesão para: ${nomes}.`);
        } else {
          toast.success('Todos os termos de adesão estão em dia.');
        }
      } catch {
        toast.error('Não foi possível verificar os documentos.');
      } finally {
        formularioVerificando = false;
        renderContent();
      }
    }

    async function handleGerarDocumentos(tabela: FormularioTabela, nome: string, cpf: string): Promise<void> {
      if (!nome.trim() || !cpf.trim()) {
        toast.error('Preencha nome e CPF do responsável antes de gerar.');
        return;
      }

      formularioGerando = true;
      renderContent();

      try {
        if (formularioVerificacao?.ok !== true) {
          throw new Error('Verifique os documentos novamente antes de gerar.');
        }
        const [formularioBlob, termosBlob] = await Promise.all([
          gerarFormularioPdf(tabela.plantId, nome.trim(), cpf.trim(), tabela.linhas),
          gerarTermosAdesaoPdf(tabela.plantId)
        ]);

        if (formularioArquivosGerados) {
          URL.revokeObjectURL(formularioArquivosGerados.formulario);
          URL.revokeObjectURL(formularioArquivosGerados.termos);
        }
        formularioArquivosGerados = {
          formulario: URL.createObjectURL(formularioBlob),
          termos: URL.createObjectURL(termosBlob)
        };

        toast.success('Formulário e termos gerados. Baixe os 4 arquivos abaixo antes de enviar à Copel.');
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível gerar os arquivos.');
      } finally {
        formularioGerando = false;
        renderContent();
      }
    }

    wrapper.appendChild(backLink);
    renderContent();
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

function defaultCompetencia(): string {
  const now = new Date();
  const mes = String(now.getMonth() + 1).padStart(2, '0');
  return `${now.getFullYear()}-${mes}`;
}
