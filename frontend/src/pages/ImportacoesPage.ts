import { createDataTable } from '../components/DataTable';
import { createCheckboxField } from '../components/formFields';
import { createIcon } from '../components/Icon';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { config } from '../services/config';
import { t } from '../services/i18nService';
import {
  confirmarImportacao,
  criarPreviaImportacao,
  exportarImportacao,
  type ImportacaoPrevia,
  type ImportacaoProblema,
  type ImportacaoResultado
} from '../services/importacoesService';

type ImportacaoStage = 'selecionar' | 'previa' | 'resultado';
type TipoCsv = 'clientes' | 'ucs' | 'usinas';
type ProblemaRow = ImportacaoProblema & { local: string };

export function createImportacoesContent(onImported?: () => void): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  const toast = useToast();
  let stage: ImportacaoStage = 'selecionar';
  let arquivo: File | null = null;
  let tipoCsv: TipoCsv = 'clientes';
  let previa: ImportacaoPrevia | null = null;
  let resultado: ImportacaoResultado | null = null;
  let busy = false;
  let uploadError = '';
  let confirmError = '';
  const tiposExportacao = new Set<TipoCsv>(['clientes', 'ucs', 'usinas']);

  render();
  return content;

  function render(): void {
    if (!canImport()) {
      const denied = createElement('section', { className: 'importacao-panel empty-state' });
      denied.append(
        createIcon('lock', 'empty-state-icon'),
        createElement('strong', { textContent: t('importacoes.access.title') }),
        createElement('span', { textContent: t('importacoes.access.description') })
      );
      content.replaceChildren(createTemplateGuide(), denied);
      return;
    }

    if (stage === 'previa' && previa) {
      content.replaceChildren(createPreviewPanel(previa));
      return;
    }
    if (stage === 'resultado' && resultado) {
      content.replaceChildren(createResultPanel(resultado));
      return;
    }
    content.replaceChildren(createUploadPanel());
  }

  function createUploadPanel(): HTMLElement {
    const panel = createElement('section', { className: 'importacao-panel' });
    panel.append(
      createImportacaoHeader(t('importacoes.upload.headerEyebrow'), t('importacoes.upload.headerTitle')),
      createTemplateGuide()
    );
    const exportPanel = createElement('section', { className: 'importacao-export' });
    exportPanel.append(createElement('h2', { textContent: t('importacoes.export.title') }), createElement('p', { textContent: t('importacoes.export.description') }));
    const exportFilters = createElement('div', { className: 'importacao-export-filters' });
    const exportButton = createElement('button', { className: 'secondary-button', type: 'button' });
    ([['clientes', t('importacoes.export.tipoClientes')], ['ucs', t('importacoes.export.tipoUcs')], ['usinas', t('importacoes.export.tipoUsinas')]] as Array<[TipoCsv, string]>).forEach(([tipo, label]) => {
      const field = createCheckboxField(label, tiposExportacao.has(tipo));
      field.input.addEventListener('change', () => {
        if (field.input.checked) tiposExportacao.add(tipo);
        else tiposExportacao.delete(tipo);
        updateExportButton();
      });
      exportFilters.appendChild(field.field);
    });
    function updateExportButton(): void {
      exportButton.disabled = tiposExportacao.size === 0;
      exportButton.textContent = tiposExportacao.size === 1 ? t('importacoes.export.buttonOne') : t('importacoes.export.buttonMany');
    }
    updateExportButton();
    exportButton.addEventListener('click', () => void downloadExport(Array.from(tiposExportacao)));
    exportPanel.append(exportFilters, exportButton);
    panel.appendChild(exportPanel);
    const form = createElement('form', { className: 'importacao-form' });
    const fileField = createElement('label', { className: 'upload-dropzone importacao-dropzone' });
    const fileInput = createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv';
    fileInput.required = true;
    const selectedLabel = createElement('span', { className: 'importacao-file-name', textContent: arquivo?.name ?? t('importacoes.upload.chooseFile') });
    fileField.append(createIcon('upload'), selectedLabel, fileInput);

    function selectFile(file: File | null): void {
      arquivo = file;
      uploadError = '';
      selectedLabel.textContent = arquivo?.name ?? t('importacoes.upload.chooseFile');
    }

    fileInput.addEventListener('change', () => {
      selectFile(fileInput.files?.[0] ?? null);
    });
    fileField.addEventListener('dragover', (event) => { event.preventDefault(); fileField.classList.add('dragging'); });
    fileField.addEventListener('dragleave', () => fileField.classList.remove('dragging'));
    fileField.addEventListener('drop', (event) => {
      event.preventDefault();
      fileField.classList.remove('dragging');
      selectFile(event.dataTransfer?.files[0] ?? null);
    });
    const csvTypeField = createElement('label', { className: 'form-field' });
    csvTypeField.appendChild(createElement('span', { textContent: t('importacoes.upload.csvTypeLabel') }));
    const csvType = createElement('select');
    [['clientes', t('importacoes.export.tipoClientes')], ['ucs', t('importacoes.export.tipoUcs')], ['usinas', t('importacoes.export.tipoUsinas')]].forEach(([value, label]) => { const option = createElement('option', { textContent: label }); option.value = value; csvType.appendChild(option); });
    csvType.value = tipoCsv;
    csvType.addEventListener('change', () => { tipoCsv = csvType.value as TipoCsv; });
    csvTypeField.appendChild(csvType);
    const hint = createElement('p', { className: 'settings-hint', textContent: t('importacoes.upload.hint') });
    const actions = createElement('div', { className: 'form-actions' });
    const submit = createElement('button', { className: 'button-with-icon', type: 'submit' });
    submit.append(createIcon('eye'), document.createTextNode(t('importacoes.upload.submit')));
    if (uploadError) form.appendChild(createElement('p', { className: 'importacao-error', textContent: uploadError }));
    form.addEventListener('submit', (event) => { event.preventDefault(); if (arquivo) void upload(arquivo, arquivo.name.toLowerCase().endsWith('.csv') ? tipoCsv : undefined); else fileInput.reportValidity(); });
    actions.appendChild(submit);
    form.append(fileField, csvTypeField, hint, actions);
    panel.appendChild(form);
    return panel;
  }

  function createPreviewPanel(data: ImportacaoPrevia): HTMLElement {
    const panel = createElement('section', { className: 'content-stack' });
    const header = createElement('section', { className: 'importacao-panel' });
    header.append(createImportacaoHeader(t('importacoes.preview.headerEyebrow'), t('importacoes.preview.headerTitle')));
    header.appendChild(createResumo(data.contagens, data.erros.length));
    if (data.erros.length) {
      header.append(createProblemasPanel(t('importacoes.preview.errorsTitle'), data.erros, 'importacao-erros'), createPreviewActions(false));
    } else {
      header.append(createElement('p', { className: 'importacao-ready', textContent: `${t('importacoes.preview.validPrefix')} ${formatExpiration(data.expiraEm)}.` }), createPreviewActions(true));
    }
    panel.appendChild(header);
    return panel;
  }

  function createPreviewActions(canConfirm: boolean): HTMLElement {
    const actions = createElement('div', { className: 'form-actions' });
    const replace = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('importacoes.preview.replace') });
    replace.addEventListener('click', reset);
    actions.appendChild(replace);
    if (canConfirm) {
      const confirm = createElement('button', { type: 'button', textContent: busy ? t('importacoes.preview.confirming') : t('importacoes.preview.confirm') });
      confirm.disabled = busy;
      confirm.addEventListener('click', () => { if (previa) void confirmImport(previa.previewId); });
      actions.appendChild(confirm);
    }
    if (confirmError) actions.appendChild(createElement('p', { className: 'importacao-error', textContent: confirmError }));
    return actions;
  }

  function createResultPanel(data: ImportacaoResultado): HTMLElement {
    const panel = createElement('section', { className: 'importacao-panel importacao-result' });
    panel.append(
      createIcon('check', 'importacao-success-icon'),
      createImportacaoHeader(t('importacoes.result.headerEyebrow'), t('importacoes.result.headerTitle')),
      createResumo(data)
    );
    const actions = createElement('div', { className: 'form-actions' });
    const again = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('importacoes.result.again') });
    again.addEventListener('click', reset);
    actions.append(again, createNavigateButton(t('importacoes.result.viewClients'), '/clientes'), createNavigateButton(t('importacoes.result.viewUcs'), '/ucs'), createNavigateButton(t('importacoes.result.viewUsinas'), '/usinas'));
    panel.appendChild(actions);
    return panel;
  }

  function createTemplateGuide(): HTMLElement {
    const guide = createElement('section', { className: 'importacao-template-guide' });
    const download = createElement('a', { className: 'secondary-button', textContent: t('importacoes.guide.download') });
    download.href = `${config.apiBaseUrl}${config.apiPrefix}/importacoes/modelo`;
    guide.append(download, createElement('p', { textContent: t('importacoes.guide.description') }));
    guide.append(createElement('h2', { textContent: t('importacoes.guide.formatTitle') }), createElement('p', { textContent: t('importacoes.guide.formatDescription') }));
    const list = createElement('ol');
    [t('importacoes.guide.clientesRule'), t('importacoes.guide.ucsRule'), t('importacoes.guide.usinasRule')].forEach((item) => list.appendChild(createElement('li', { textContent: item })));
    guide.appendChild(list);
    return guide;
  }

  function createResumo(contagens: ImportacaoResultado, erros = 0): HTMLElement {
    const grid = createElement('div', { className: 'importacao-summary-grid' });
    const validas = contagens.clientes + contagens.ucs + contagens.usinas;
    const rows: Array<[string, string, number]> = [
      ['ready', t('importacoes.summary.ready'), validas],
      ['erro', t('importacoes.summary.error'), erros],
      ['clientes', t('importacoes.export.tipoClientes'), contagens.clientes],
      ['ucs', t('importacoes.export.tipoUcs'), contagens.ucs],
      ['usinas', t('importacoes.export.tipoUsinas'), contagens.usinas]
    ];
    rows.forEach(([key, label, value]) => {
      const card = createElement('div', { className: key === 'erro' && value ? 'importacao-summary-card danger' : 'importacao-summary-card' });
      card.append(createElement('strong', { textContent: String(value) }), createElement('span', { textContent: label }));
      grid.appendChild(card);
    });
    return grid;
  }

  function createProblemasPanel(title: string, problemas: ImportacaoProblema[], className: string): HTMLElement {
    const section = createElement('section', { className: `importacao-problemas ${className}` });
    section.appendChild(createElement('h2', { textContent: title }));
    const rows: ProblemaRow[] = problemas.map((item) => ({ ...item, local: `${item.tipo} · linha ${item.linha}` }));
    section.appendChild(createDataTable<ProblemaRow>({
      title,
      eyebrow: t('importacoes.problems.validationEyebrow'),
      rows,
      emptyMessage: t('importacoes.problems.empty'),
      columns: [{ key: 'local', label: t('importacoes.problems.colLocal') }, { key: 'erro', label: t('importacoes.problems.colMensagem') }]
    }));
    return section;
  }

  async function upload(file: File, csvType?: TipoCsv): Promise<void> {
    busy = true;
    uploadError = '';
    loading.show();
    render();
    try {
      previa = await criarPreviaImportacao(file, csvType);
      confirmError = '';
      stage = 'previa';
    } catch (error) {
      uploadError = error instanceof Error ? error.message : t('importacoes.errors.previewError');
    } finally {
      busy = false;
      loading.hide();
      render();
    }
  }

  async function downloadExport(tipos: TipoCsv[]): Promise<void> {
    loading.show();
    try {
      const blob = await exportarImportacao(tipos);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `hub-${tipos.join('-')}.xlsx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t('importacoes.errors.exportError'));
    } finally {
      loading.hide();
    }
  }

  async function confirmImport(id: number): Promise<void> {
    busy = true;
    confirmError = '';
    loading.show();
    render();
    try {
      resultado = await confirmarImportacao(id);
      stage = 'resultado';
      onImported?.();
      toast.success(t('importacoes.success.confirmed'));
    } catch (error) {
      confirmError = error instanceof Error ? error.message : t('importacoes.errors.confirmError');
    } finally {
      busy = false;
      loading.hide();
      render();
    }
  }

  function reset(): void {
    stage = 'selecionar';
    arquivo = null;
    previa = null;
    resultado = null;
    uploadError = '';
    confirmError = '';
    render();
  }
}

export function createImportacoesPage(): HTMLElement {
  return createBaseLayout({
    content: createImportacoesContent(),
    eyebrow: t('importacoes.page.eyebrow'),
    title: t('importacoes.page.title')
  });
}

function canImport(): boolean {
  const role = getCurrentUser()?.role;
  return role === 'owner' || role === 'admin' || role === 'operator';
}

function createImportacaoHeader(eyebrow: string, title: string): HTMLElement {
  const header = createElement('div', { className: 'panel-title' });
  const content = createElement('div');
  content.append(createElement('span', { className: 'eyebrow', textContent: eyebrow }), createElement('h2', { textContent: title }));
  header.appendChild(content);
  return header;
}

function createNavigateButton(label: string, path: string): HTMLElement {
  const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: label });
  button.addEventListener('click', () => { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); });
  return button;
}

function formatExpiration(value: string): string {
  return new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
