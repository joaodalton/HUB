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
import { t } from '../../services/i18nService';

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
    titleText.append(createElement('span', { className: 'eyebrow', textContent: t('rateioFormulario.picker.eyebrow') }), createElement('h2', { textContent: t('rateioFormulario.picker.title') }));
    const title = createElement('div', { className: 'panel-title' }); title.appendChild(titleText);
    const list = createElement('div', { className: 'rateio-plant-list' });
    const plants = getPlants();
    if (!plants.length) list.appendChild(createElement('p', { className: 'empty-state small', textContent: t('rateioFormulario.picker.empty') }));
    plants.forEach((plant) => {
      const row = createElement('button', { className: 'rateio-plant-row', type: 'button' });
      const icon = createElement('span', { className: 'rateio-plant-icon' }); icon.appendChild(createIcon('plants'));
      const info = createElement('div', { className: 'rateio-plant-row-info' });
      info.append(createElement('strong', { textContent: plant.nome }), createElement('span', { textContent: `UC ${plant.uc || t('rateioFormulario.picker.ucNotInformed')} · ${plant.kwPico || '-'} kWp` }));
      row.append(icon, info, createStatusBadge(plant.status));
      row.addEventListener('click', () => selectPlant(plant.id));
      list.appendChild(row);
    });
    panel.append(title, list, createElement('p', { className: 'settings-hint', textContent: t('rateioFormulario.picker.hint') }));
    return panel;
  }
  function renderReview(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'content-stack' });
    const back = createElement('a', { className: 'rateio-back-link', textContent: t('rateioFormulario.review.backLink') }); back.href = '#';
    back.addEventListener('click', (event) => { event.preventDefault(); selectPlant(null); }); wrapper.appendChild(back);
    const panel = createPanel(plant); wrapper.appendChild(panel);
    if (tablePlantId !== plant.id && !loadingTable) void loadTable(plant.id);
    return wrapper;
  }

  function createPanel(plant: PlantRow): HTMLElement {
    const panel = createElement('section', { className: 'data-panel rateio-formulario-panel' });
    const titleText = createElement('div'); titleText.append(createElement('span', { className: 'eyebrow', textContent: t('rateioFormulario.review.eyebrow') }), createElement('h2', { textContent: t('rateioFormulario.review.title') }));
    const title = createElement('div', { className: 'panel-title' }); title.append(titleText, createElement('span', { className: 'status-badge tone-info', textContent: plant.nome })); panel.appendChild(title);
    if (tableError) { panel.appendChild(createElement('p', { className: 'empty-state', textContent: tableError })); return panel; }
    if (!table || tablePlantId !== plant.id) { panel.appendChild(createElement('p', { className: 'loading-state', textContent: t('rateioFormulario.review.loadingTable') })); return panel; }
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
    const hint = createElement('p', { className: 'settings-hint', textContent: `${t('rateioFormulario.review.ucGeradoraPrefix')} ${current.ucGeradora ?? '-'} · ${t('rateioFormulario.review.ucAncoraPrefix')} ${current.ucAncora ?? '-'} ${t('rateioFormulario.review.ucAncoraSuffix')}` });
    const summary = createElement('div', { className: 'rateio-funil-grid rateio-formulario-resumo' });
    summary.append(createFormularioStat(t('rateioFormulario.review.statUcGeradora'), current.ucGeradora ?? '-'), createFormularioStat(t('rateioFormulario.review.statUcAncora'), current.ucAncora ?? '-'), createFormularioStat(t('rateioFormulario.review.statBeneficiarias'), String(current.linhas.length)), createFormularioStat(t('rateioFormulario.review.statTotalDistribuido'), `${formatNumber(current.somaPercentual)}%`));
    const tableRows = [current.associacao, ...current.linhas];
    const tableElement = createEditableTable<FormularioLinha>({
      columns: [
        { key: 'ordem', label: t('rateioFormulario.review.columnOrdem'), align: 'right' },
        { key: 'nome', label: t('rateioFormulario.review.columnNome'), editable: true, onChange: (row, value) => { row.nome = value; } },
        { key: 'documento', label: t('rateioFormulario.review.columnDocumento'), editable: true, onChange: (row, value) => { row.documento = value; } },
        { key: 'ucIdentificacao', label: t('rateioFormulario.review.columnUc'), editable: true, onChange: (row, value) => { row.ucIdentificacao = value; } },
        { key: 'percentual', label: t('rateioFormulario.review.columnPercentual'), align: 'right', editable: true, onChange: (row, value) => { row.percentual = Number(value.replace(',', '.')) || 0; } },
        { key: 'termoAdesaoOk', label: t('rateioFormulario.review.columnTermoAdesao'), render: (row) => createTermoAdesaoBadge(row) }
      ], rows: tableRows, emptyMessage: t('rateioFormulario.review.tableEmpty'), getRowKey: (row) => row.ordem,
      onChange: () => { current.somaPercentual = round2(current.linhas.reduce((sum, line) => sum + line.percentual, 0)); verification = null; render(); }
    });
    const checks = createElement('div', { className: 'rateio-formulario-checks' });
    checks.append(createFormularioCheck(`${t('rateioFormulario.review.checkTotal')} ${formatNumber(current.somaPercentual)}%`, current.somaPercentual <= 100), createFormularioCheck(rules.documentoCnpjObrigatorio ? t('rateioFormulario.review.checkCnpjRequired') : t('rateioFormulario.review.checkCnpjWaived'), cnpjOk), createFormularioCheck(rules.documentoEstatutoObrigatorio ? t('rateioFormulario.review.checkEstatutoRequired') : t('rateioFormulario.review.checkEstatutoWaived'), estatutoOk), createFormularioCheck(rules.termosAdesaoObrigatorios ? t('rateioFormulario.review.checkTermosRequired') : t('rateioFormulario.review.checkTermosWaived'), termsOk, rules.termosAdesaoObrigatorios && !verification ? t('rateioFormulario.review.checkTermosPending') : undefined));
    const fields = createElement('div', { className: 'form-grid' });
    fields.append(createResponsavelField(t('rateioFormulario.review.fieldNomeResponsavel'), responsavelNome, (value) => { responsavelNome = value; }), createResponsavelField(t('rateioFormulario.review.fieldCpfResponsavel'), responsavelCpf, (value) => { responsavelCpf = value; }));
    const excedente = createElement('div', { className: 'rateio-excedente-control' });
    const toggle = createElement('button', { className: excedenteEnergia ? 'secondary-button active' : 'secondary-button', type: 'button', textContent: excedenteEnergia ? t('rateioFormulario.review.excedenteOn') : t('rateioFormulario.review.excedenteOff') });
    toggle.setAttribute('aria-pressed', String(excedenteEnergia));
    toggle.addEventListener('click', () => { excedenteEnergia = !excedenteEnergia; render(); });
    const help = createElement('span', { className: 'rateio-help', textContent: '?' });
    help.title = t('rateioFormulario.review.excedenteHelp');
    excedente.append(createElement('span', { className: 'settings-subheading', textContent: t('rateioFormulario.review.excedenteHeading') }), help, toggle);
    const actions = createActions(current, canGenerate);
    const nodes: HTMLElement[] = [hint, summary, createElement('h3', { className: 'settings-subheading', textContent: t('rateioFormulario.review.sectionDados') }), tableElement, checks, createElement('h3', { className: 'settings-subheading', textContent: t('rateioFormulario.review.sectionResponsavel') }), fields, excedente];
    if (!documentsOk) nodes.push(createElement('p', { className: 'empty-state small', textContent: t('rateioFormulario.review.documentsMissing') }));
    nodes.push(actions); if (generated) nodes.push(renderDownloads(generated)); return nodes;
  }

  function renderPreview(current: FormularioTabela): HTMLElement {
    const panel = createElement('aside', { className: 'detail-info-panel sticky rateio-formulario-preview' });
    panel.append(
      createElement('span', { className: 'eyebrow', textContent: t('rateioFormulario.review.previewEyebrow') }),
      createElement('h3', { textContent: t('rateioFormulario.review.previewTitle') }),
      createElement('p', { className: 'rateio-preview-associacao', textContent: `1. ${current.associacao.nome} · ${current.associacao.ucIdentificacao ?? '-' } · 0%` }),
      createFormularioStat(t('rateioFormulario.review.statBeneficiarias'), String(current.linhas.length)),
      createFormularioStat(t('rateioFormulario.review.previewSoma'), `${formatNumber(current.somaPercentual)}%`),
    );
    current.avisos.forEach((aviso) => panel.appendChild(createElement('p', { className: 'settings-hint rateio-total-excede', textContent: aviso })));
    return panel;
  }

  function createActions(current: FormularioTabela, canGenerate: boolean): HTMLElement {
    const actions = createElement('div', { className: 'form-actions' });
    const verify = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' }); verify.append(createIcon('check'), document.createTextNode(t('rateioFormulario.review.verifyButton'))); verify.disabled = verifying;
    const excel = createElement('button', { textContent: t('rateioFormulario.review.generateButton'), type: 'button', title: canGenerate ? '' : t('rateioFormulario.review.generateDisabledHint') }); excel.disabled = !canGenerate || generatingExcel;
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
      tableError = error instanceof Error ? `${t('rateioFormulario.review.loadErrorPrefix')} ${error.message}` : t('rateioFormulario.review.loadErrorDefault');
    }
    finally { if (currentRequest === requestId) { loadingTable = false; render(); } }
  }

  async function verifyDocuments(plantId: number): Promise<void> {
    verifying = true; render();
    try {
      verification = await verificarDocumentosFormulario(plantId);
      if (verification.exigido === false) toast.info(t('rateioFormulario.review.verifyWaived')); else if (verification.ok) toast.success(t('rateioFormulario.review.verifyOk')); else toast.error(`${t('rateioFormulario.review.verifyMissingPrefix')} ${verification.faltando.map((item) => item.nome).join(', ')}.`);
    }
    catch { toast.error(t('rateioFormulario.review.verifyError')); }
    finally { verifying = false; render(); }
  }

  async function generateExcel(current: FormularioTabela): Promise<void> {
    const responsavel = validateResponsavel(current); if (!responsavel) return;
    generatingExcel = true; render();
    try { const blob = await gerarFormularioExcel(current.plantId, responsavel.nome, responsavel.cpf, current.linhas, excedenteEnergia); if (!generated) generated = {}; if (generated.excel) URL.revokeObjectURL(generated.excel); generated.excel = URL.createObjectURL(blob); toast.success(t('rateioFormulario.review.excelGenerated')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('rateioFormulario.review.excelError')); }
    finally { generatingExcel = false; render(); }
  }

  function validateResponsavel(current: FormularioTabela): { nome: string; cpf: string } | null {
    if (!responsavelNome.trim() || !responsavelCpf.trim()) { toast.error(t('rateioFormulario.review.responsavelRequired')); return null; }
    if (current.regrasDocumentos.termosAdesaoObrigatorios && verification?.ok !== true) { toast.error(t('rateioFormulario.review.recheckDocuments')); return null; }
    return { nome: responsavelNome.trim(), cpf: responsavelCpf.trim() };
  }

  function renderDownloads(files: GeneratedFiles): HTMLElement {
    const box = createElement('div', { className: 'rateio-formulario-downloads' }); box.appendChild(createElement('span', { className: 'settings-subheading', textContent: t('rateioFormulario.review.downloadsHeading') }));
    const links = createElement('div', { className: 'button-group' });
    if (files.termos) links.appendChild(createDownloadLink(t('rateioFormulario.review.downloadTermos'), files.termos));
    if (files.excel) links.appendChild(createDownloadLink(t('rateioFormulario.review.downloadExcel'), files.excel, true, 'xlsx'));
    if (companyDocuments?.cnpj) links.appendChild(createDownloadLink(t('rateioFormulario.review.downloadCnpj'), `${config.apiBaseUrl}${config.apiPrefix}/documents/${companyDocuments.cnpj.id}/download`, false));
    if (companyDocuments?.estatuto) links.appendChild(createDownloadLink(t('rateioFormulario.review.downloadEstatuto'), `${config.apiBaseUrl}${config.apiPrefix}/documents/${companyDocuments.estatuto.id}/download`, false));
    box.appendChild(links); return box;
  }
}

function createDownloadLink(label: string, href: string, isBlob = true, extension = 'pdf'): HTMLElement {
  const link = createElement('a', { className: 'secondary-button', textContent: label });
  link.href = href; if (isBlob) link.download = `${label.toLowerCase().replace(/\s+/g, '-')}.${extension}`;
  link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
}
