import { createIcon } from '../../components/Icon';
import { createElement } from '../../dom';
import { useToast } from '../../hooks/useToast';
import { getEmpresaDocumentos, type EmpresaDocumentos } from '../../services/empresaService';
import type { PlantRow } from '../../services/plantService';
import {
  gerarFormularioExcel, getFormularioPreview, verificarDocumentosFormulario,
  type FormularioLinha, type FormularioTabela
} from '../../services/rateioFormularioService';
import { config } from '../../services/config';
import { createEditableTable, createFormularioCheck, createFormularioStat, createResponsavelField, createTermoAdesaoBadge } from './RateioFormularioControls';
import { createStatusBadge, formatNumber, round2 } from './shared';

type GeneratedFiles = { termos?: string; excel?: string };
type Verification = { ok: boolean; exigido?: boolean; faltando: Array<{ clienteId: number | null; ucId: number | null; nome: string }> };

export type RateioFormularioView = {
  element: HTMLElement;
  selectPlant: (plantId: number | null) => void;
  refresh: () => void;
};

export function createRateioFormularioView(getPlants: () => PlantRow[]): RateioFormularioView {
  const element = createElement('section', { className: 'content-stack' }); const toast = useToast();
  let selectedPlantId: number | null = null; let companyDocuments: EmpresaDocumentos | null = null;
  let table: FormularioTabela | null = null; let tablePlantId: number | null = null;
  let loadingTable = false;
  let tableError = '';
  let requestId = 0;
  let verifying = false;
  let verification: Verification | null = null;
  let generatingExcel = false; let generated: GeneratedFiles | null = null;
  let responsavelNome = ''; let responsavelCpf = '';
  let excedenteEnergia = false;
  getEmpresaDocumentos().then((documents) => { companyDocuments = documents; render(); }).catch(() => { companyDocuments = null; });
  render();
  return { element, selectPlant, refresh: render };
  function selectPlant(plantId: number | null): void {
    selectedPlantId = plantId; resetForm(); render();
  }
  function resetForm(): void {
    requestId += 1; table = null; tablePlantId = null; loadingTable = false; tableError = ''; verifying = false; verification = null;
    responsavelNome = ''; responsavelCpf = ''; excedenteEnergia = false;
  }
  function render(): void {
    const plant = getPlants().find((item) => item.id === selectedPlantId);
    element.replaceChildren(plant ? renderReview(plant) : renderPicker());
  }
  function renderPicker(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-picker' });
    const titleText = createElement('div');
    titleText.append(createElement('span', { className: 'eyebrow', textContent: 'Formulário Copel' }), createElement('h2', { textContent: 'Selecione a usina para gerar o formulário' }));
    const title = createElement('div', { className: 'panel-title' }); title.appendChild(titleText);
    const list = createElement('div', { className: 'rateio-plant-list' });
    const plants = getPlants();
    if (!plants.length) list.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhuma usina cadastrada ainda.' }));
    plants.forEach((plant) => {
      const row = createElement('button', { className: 'rateio-plant-row', type: 'button' });
      const icon = createElement('span', { className: 'rateio-plant-icon' }); icon.appendChild(createIcon('plants'));
      const info = createElement('div', { className: 'rateio-plant-row-info' });
      info.append(createElement('strong', { textContent: plant.nome }), createElement('span', { textContent: `UC ${plant.uc || 'não informada'} · ${plant.kwPico || '-'} kWp` }));
      row.append(icon, info, createStatusBadge(plant.status));
      row.addEventListener('click', () => selectPlant(plant.id));
      list.appendChild(row);
    });
    panel.append(title, list, createElement('p', { className: 'settings-hint', textContent: 'Esta etapa apenas lê as conexões confirmadas; nenhum rateio será recalculado.' }));
    return panel;
  }
  function renderReview(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const back = createElement('a', { className: 'rateio-back-link', textContent: '← Selecionar outra usina' }); back.href = '#';
    back.addEventListener('click', (event) => { event.preventDefault(); selectPlant(null); }); wrapper.appendChild(back);
    const panel = createPanel(plant); wrapper.appendChild(panel);
    if (tablePlantId !== plant.id && !loadingTable) void loadTable(plant.id);
    return wrapper;
  }

  function createPanel(plant: PlantRow): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-formulario-panel' });
    const titleText = createElement('div'); titleText.append(createElement('span', { className: 'eyebrow', textContent: 'Revisão do formulário' }), createElement('h2', { textContent: 'Formulário Copel — Rateio de Associação' }));
    const title = createElement('div', { className: 'panel-title' }); title.append(titleText, createElement('span', { className: 'status-badge tone-info', textContent: plant.nome })); panel.appendChild(title);
    if (tableError) { panel.appendChild(createElement('p', { className: 'empty-state', textContent: tableError })); return panel; }
    if (!table || tablePlantId !== plant.id) { panel.appendChild(createElement('p', { className: 'loading-state', textContent: 'Carregando tabela...' })); return panel; }
    const content = renderTableContent(table);
    const layout = createElement('div', { className: 'rateio-formulario-layout' });
    const main = createElement('div', { className: 'rateio-formulario-main' }); main.append(...content);
    layout.append(main, renderPreview(table)); panel.appendChild(layout);
    return panel;
  }

  function renderTableContent(current: FormularioTabela): HTMLElement[] {
    const rules = current.regrasDocumentos;
    const cnpjOk = !rules.documentoCnpjObrigatorio || Boolean(companyDocuments?.cnpj); const estatutoOk = !rules.documentoEstatutoObrigatorio || Boolean(companyDocuments?.estatuto);
    const termsOk = !rules.termosAdesaoObrigatorios || verification?.ok === true; const documentsOk = cnpjOk && estatutoOk;
    const canGenerate = current.linhas.length > 0 && current.somaPercentual <= 100 && termsOk && documentsOk;
    const hint = createElement('p', { className: 'settings-hint', textContent: `UC geradora: ${current.ucGeradora ?? '-'} · UC âncora: ${current.ucAncora ?? '-'} (sempre a própria usina)` });
    const summary = createElement('div', { className: 'rateio-funil-grid rateio-formulario-resumo' });
    summary.append(createFormularioStat('UC geradora', current.ucGeradora ?? '-'), createFormularioStat('UC âncora', current.ucAncora ?? '-'), createFormularioStat('Beneficiárias', String(current.linhas.length)), createFormularioStat('Total distribuído', `${formatNumber(current.somaPercentual)}%`));
    const tableRows = [current.associacao, ...current.linhas];
    const tableElement = createEditableTable<FormularioLinha>({
      columns: [
        { key: 'ordem', label: '#', align: 'right' },
        { key: 'nome', label: 'Nome do titular', editable: true, onChange: (row, value) => { row.nome = value; } },
        { key: 'documento', label: 'CPF/CNPJ', editable: true, onChange: (row, value) => { row.documento = value; } },
        { key: 'ucIdentificacao', label: 'UC', editable: true, onChange: (row, value) => { row.ucIdentificacao = value; } },
        { key: 'percentual', label: '%', align: 'right', editable: true, onChange: (row, value) => { row.percentual = Number(value.replace(',', '.')) || 0; } },
        { key: 'termoAdesaoOk', label: 'Termo de adesão', render: (row) => createTermoAdesaoBadge(row).outerHTML }
      ], rows: tableRows, emptyMessage: 'Nenhuma UC beneficiária conectada a esta usina ainda.', getRowKey: (row) => row.ordem,
      onChange: () => { current.somaPercentual = round2(current.linhas.reduce((sum, line) => sum + line.percentual, 0)); verification = null; render(); }
    });
    const checks = createElement('div', { className: 'rateio-formulario-checks' });
    checks.append(createFormularioCheck(`Total: ${formatNumber(current.somaPercentual)}%`, current.somaPercentual <= 100), createFormularioCheck(rules.documentoCnpjObrigatorio ? 'CNPJ da empresa' : 'CNPJ dispensado', cnpjOk), createFormularioCheck(rules.documentoEstatutoObrigatorio ? 'Estatuto da empresa' : 'Estatuto dispensado', estatutoOk), createFormularioCheck(rules.termosAdesaoObrigatorios ? 'Termos de adesão' : 'Termos dispensados', termsOk, rules.termosAdesaoObrigatorios && !verification ? 'Verifique os documentos' : undefined));
    const fields = createElement('div', { className: 'form-grid' });
    fields.append(createResponsavelField('Nome do responsável (assina o formulário)', responsavelNome, (value) => { responsavelNome = value; }), createResponsavelField('CPF do responsável', responsavelCpf, (value) => { responsavelCpf = value; }));
    const excedente = createElement('div', { className: 'rateio-excedente-control' });
    const toggle = createElement('button', { className: excedenteEnergia ? 'secondary-button active' : 'secondary-button', type: 'button', textContent: excedenteEnergia ? 'Ligado' : 'Desligado' });
    toggle.setAttribute('aria-pressed', String(excedenteEnergia));
    toggle.addEventListener('click', () => { excedenteEnergia = !excedenteEnergia; render(); });
    const help = createElement('span', { className: 'rateio-help', textContent: '?' });
    help.title = 'Classifica toda a energia injetada como excedente. Se desligado, o excedente é a diferença entre a energia injetada e o consumo da usina geradora.';
    excedente.append(createElement('span', { className: 'settings-subheading', textContent: 'Excedente de energia' }), help, toggle);
    const actions = createActions(current, canGenerate);
    const nodes: HTMLElement[] = [hint, summary, createElement('h3', { className: 'settings-subheading', textContent: 'Dados que irão no formulário' }), tableElement, checks, createElement('h3', { className: 'settings-subheading', textContent: 'Responsável pela assinatura' }), fields, excedente];
    if (!documentsOk) nodes.push(createElement('p', { className: 'empty-state small', textContent: 'Anexe os documentos obrigatórios em Dados da Empresa ou desative temporariamente a exigência em Configurações → Geral → Rateio.' }));
    nodes.push(actions); if (generated) nodes.push(renderDownloads(generated)); return nodes;
  }

  function renderPreview(current: FormularioTabela): HTMLElement {
    const panel = createElement('aside', { className: 'detail-info-panel sticky rateio-formulario-preview' });
    panel.append(
      createElement('span', { className: 'eyebrow', textContent: 'Prévia do Excel' }),
      createElement('h3', { textContent: 'Resumo' }),
      createElement('p', { className: 'rateio-preview-associacao', textContent: `1. ${current.associacao.nome} · ${current.associacao.ucIdentificacao ?? '-' } · 0%` }),
      createFormularioStat('Beneficiárias', String(current.linhas.length)),
      createFormularioStat('Soma', `${formatNumber(current.somaPercentual)}%`),
    );
    current.avisos.forEach((aviso) => panel.appendChild(createElement('p', { className: 'settings-hint rateio-total-excede', textContent: aviso })));
    return panel;
  }

  function createActions(current: FormularioTabela, canGenerate: boolean): HTMLElement {
    const actions = createElement('div', { className: 'form-actions' });
    const verify = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' }); verify.append(createIcon('check'), document.createTextNode('Verificar documentos')); verify.disabled = verifying;
    const excel = createElement('button', { textContent: 'Gerar formulário (Excel)', type: 'button', title: canGenerate ? '' : 'Ajuste os pontos acima antes de gerar.' }); excel.disabled = !canGenerate || generatingExcel;
    verify.addEventListener('click', () => void verifyDocuments(current.plantId)); excel.addEventListener('click', () => void generateExcel(current));
    actions.append(verify, excel); return actions;
  }

  async function loadTable(plantId: number): Promise<void> {
    const currentRequest = ++requestId; loadingTable = true; tableError = ''; table = null; tablePlantId = plantId; render();
    try {
      const loadedTable = await getFormularioPreview(plantId);
      if (currentRequest !== requestId) return;
      table = loadedTable;
    } catch (error) {
      if (currentRequest !== requestId) return;
      table = null;
      tableError = error instanceof Error ? `Não foi possível carregar a tabela: ${error.message}` : 'Não foi possível carregar a tabela. Verifique o backend.';
    }
    finally { if (currentRequest === requestId) { loadingTable = false; render(); } }
  }

  async function verifyDocuments(plantId: number): Promise<void> {
    verifying = true; render();
    try {
      verification = await verificarDocumentosFormulario(plantId);
      if (verification.exigido === false) toast.info('A exigência de Termos de Adesão está desativada para esta empresa.'); else if (verification.ok) toast.success('Todos os termos de adesão estão em dia.'); else toast.error(`Faltam termos de adesão para: ${verification.faltando.map((item) => item.nome).join(', ')}.`);
    }
    catch { toast.error('Não foi possível verificar os documentos.'); }
    finally { verifying = false; render(); }
  }

  async function generateExcel(current: FormularioTabela): Promise<void> {
    const responsavel = validateResponsavel(current); if (!responsavel) return;
    generatingExcel = true; render();
    try { const blob = await gerarFormularioExcel(current.plantId, responsavel.nome, responsavel.cpf, current.linhas, excedenteEnergia); if (!generated) generated = {}; if (generated.excel) URL.revokeObjectURL(generated.excel); generated.excel = URL.createObjectURL(blob); toast.success('Formulário Excel gerado.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível gerar o formulário Excel.'); }
    finally { generatingExcel = false; render(); }
  }

  function validateResponsavel(current: FormularioTabela): { nome: string; cpf: string } | null {
    if (!responsavelNome.trim() || !responsavelCpf.trim()) { toast.error('Preencha nome e CPF do responsável antes de gerar.'); return null; }
    if (current.regrasDocumentos.termosAdesaoObrigatorios && verification?.ok !== true) { toast.error('Verifique os documentos novamente antes de gerar.'); return null; }
    return { nome: responsavelNome.trim(), cpf: responsavelCpf.trim() };
  }

  function renderDownloads(files: GeneratedFiles): HTMLElement {
    const box = createElement('div', { className: 'rateio-formulario-downloads' }); box.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Arquivos gerados' }));
    const links = createElement('div', { className: 'button-group' });
    if (files.termos) links.appendChild(createDownloadLink('Termos de adesão (mesclado)', files.termos));
    if (files.excel) links.appendChild(createDownloadLink('Formulário Copel (Excel)', files.excel, true, 'xlsx'));
    if (companyDocuments?.cnpj) links.appendChild(createDownloadLink('CNPJ', `${config.apiBaseUrl}${config.apiPrefix}/documents/${companyDocuments.cnpj.id}/download`, false));
    if (companyDocuments?.estatuto) links.appendChild(createDownloadLink('Estatuto', `${config.apiBaseUrl}${config.apiPrefix}/documents/${companyDocuments.estatuto.id}/download`, false));
    box.appendChild(links); return box;
  }
}

function createDownloadLink(label: string, href: string, isBlob = true, extension = 'pdf'): HTMLElement {
  const link = createElement('a', { className: 'secondary-button', textContent: label });
  link.href = href; if (isBlob) link.download = `${label.toLowerCase().replace(/\s+/g, '-')}.${extension}`;
  link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
}
