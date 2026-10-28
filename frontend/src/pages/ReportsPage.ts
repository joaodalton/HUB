import { createIcon } from '../components/Icon';
import { createModalShell } from '../components/Modal';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { ApiRequestError } from '../services/apiClient';
import { getGoogleAuthorizeUrl } from '../services/googleAccountService';
import {
  createReportTemplate, deleteReportTemplate, downloadReportFile, generateReport, getReportTemplates, getReportTypes,
  getSourceTemplate, removeSourceTemplate, setSourceTemplateDrive, setSourceTemplateUpload, updateReportTemplate,
  type ReportFormat, type ReportTemplateOption, type ReportTypeOption, type SourceTemplateCategory, type SourceTemplateConfig
} from '../services/reportsService';

const FORMAT_LABELS: Record<ReportFormat, string> = {
  doc: 'Documento (Doc)', sheet: 'Planilha (Sheet)', slide: 'Apresentação (Slides)',
  docx: 'Word (.docx)', xlsx: 'Excel (.xlsx)', pptx: 'PowerPoint (.pptx)',
};
const FORMATOS_ARQUIVO: ReportFormat[] = ['docx', 'xlsx', 'pptx'];

const CATEGORIAS_ORIGEM: Array<{ categoria: SourceTemplateCategory; label: string; extensao: string; descricaoGoogle: string }> = [
  { categoria: 'documento', label: 'Documento', extensao: '.docx', descricaoGoogle: 'Link/ID do Google Doc' },
  { categoria: 'planilha', label: 'Planilha', extensao: '.xlsx', descricaoGoogle: 'Link/ID do Google Sheet' },
  { categoria: 'apresentacao', label: 'Apresentação', extensao: '.pptx', descricaoGoogle: 'Link/ID do Google Slides' },
];

export function createReportsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let tipos: ReportTypeOption[] = [];
  let templates: ReportTemplateOption[] = [];
  const origens: Record<SourceTemplateCategory, SourceTemplateConfig | null> = { documento: null, planilha: null, apresentacao: null };
  let loaded = false;
  let modalBody: HTMLElement | null = null;

  const layout = createBaseLayout({ content, eyebrow: 'Financeiro', title: 'Relatórios' });
  render();
  void load();
  return layout;

  async function load(): Promise<void> {
    try {
      const [tiposResp, templatesResp, ...origensResp] = await Promise.all([
        getReportTypes(), getReportTemplates(), ...CATEGORIAS_ORIGEM.map((item) => getSourceTemplate(item.categoria)),
      ]);
      tipos = tiposResp;
      templates = templatesResp;
      CATEGORIAS_ORIGEM.forEach((item, index) => { origens[item.categoria] = origensResp[index]; });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível carregar os tipos de relatório.');
    } finally {
      loaded = true; render();
    }
  }

  async function reloadTemplates(): Promise<void> {
    templates = await getReportTemplates();
    render();
  }

  async function reloadOrigem(categoria: SourceTemplateCategory): Promise<void> {
    origens[categoria] = await getSourceTemplate(categoria);
    render();
  }

  function render(): void {
    if (!loaded) { content.replaceChildren(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' })); return; }
    const actions = createElement('div', { className: 'page-actions' });
    actions.style.justifyContent = 'flex-end';
    const configButton = createElement('button', { className: 'small-button button-with-icon', type: 'button' });
    configButton.append(createIcon('settings'), document.createTextNode('Templates'));
    configButton.addEventListener('click', openTemplatesModal);
    actions.appendChild(configButton);

    const grid = createElement('div', { className: 'reports-grid' });
    tipos.forEach((tipo) => grid.appendChild(createReportCard(tipo)));
    content.replaceChildren(actions, grid);
    renderModal();
  }

  function openTemplatesModal(): void {
    const modal = createModalShell('Templates de relatório', 'Configuração', () => { modalBody = null; });
    modal.dialog.classList.add('hub-modal-wide');
    modalBody = modal.body;
    renderModal();
    document.body.appendChild(modal.overlay);
  }

  function renderModal(): void {
    if (!modalBody) return;
    const sourceRow = createElement('div', { className: 'reports-source-row' });
    CATEGORIAS_ORIGEM.forEach((item) => sourceRow.appendChild(createSourcePanel(item)));
    modalBody.replaceChildren(createTemplatesPanel(), sourceRow);
  }

  function createTemplatesPanel(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel reports-config-panel' });
    panel.appendChild(createElement('h3', { textContent: 'Cores de template' }));
    panel.appendChild(createElement('p', {
      className: 'settings-hint',
      textContent: '"Padrão", "Azul corporativo" e "Verde energia" valem pra toda a plataforma. Crie o seu próprio abaixo.',
    }));

    const list = createElement('div', { className: 'content-stack' });
    templates.filter((item) => item.editable).forEach((item) => list.appendChild(createTemplateRow(item)));
    panel.appendChild(list);
    panel.appendChild(createTemplateForm());
    return panel;
  }

  function createTemplateRow(item: ReportTemplateOption): HTMLElement {
    const row = createElement('div', { className: 'table-row-actions' });
    const swatch = createElement('span');
    swatch.style.display = 'inline-block'; swatch.style.width = '14px'; swatch.style.height = '14px';
    swatch.style.borderRadius = '3px'; swatch.style.marginRight = '8px';
    swatch.style.background = item.accentHex ? `#${item.accentHex}` : 'transparent';
    swatch.style.border = '1px solid var(--border)';
    row.append(swatch, createElement('span', { textContent: item.label }));

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.setAttribute('aria-label', 'Editar template');
    editButton.addEventListener('click', () => void handleEditTemplate(item));

    const deleteButton = createElement('button', { className: 'icon-button danger', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.setAttribute('aria-label', 'Excluir template');
    deleteButton.addEventListener('click', () => void handleDeleteTemplate(item));

    row.append(editButton, deleteButton);
    return row;
  }

  function createTemplateForm(): HTMLElement {
    const form = createElement('form', { className: 'page-actions' });
    const nome = createElement('input'); nome.type = 'text'; nome.placeholder = 'Nome do template'; nome.required = true;
    const cor = createElement('input'); cor.type = 'color'; cor.value = '#2563eb'; cor.title = 'Cor de destaque';
    const submit = createElement('button', { className: 'small-button', type: 'submit', textContent: 'Criar' });
    form.append(nome, cor, submit);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      void handleCreateTemplate(nome.value, cor.value.replace('#', '').toUpperCase(), form);
    });
    return form;
  }

  async function handleCreateTemplate(nome: string, accentHex: string, form: HTMLFormElement): Promise<void> {
    if (!nome.trim()) return;
    loading.show();
    try {
      await createReportTemplate(nome.trim(), accentHex);
      toast.success('Template criado.');
      form.reset();
      await reloadTemplates();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível criar o template.');
    } finally {
      loading.hide();
    }
  }

  async function handleEditTemplate(item: ReportTemplateOption): Promise<void> {
    const novoNome = window.prompt('Nome do template', item.label);
    if (novoNome === null) return;
    const novaCor = window.prompt('Cor de destaque (hex, ex.: 2563EB, vazio = sem cor)', item.accentHex ?? '');
    if (novaCor === null) return;
    loading.show();
    try {
      await updateReportTemplate(templateDbId(item), { nome: novoNome, accentHex: novaCor.trim() || null });
      toast.success('Template atualizado.');
      await reloadTemplates();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar o template.');
    } finally {
      loading.hide();
    }
  }

  async function handleDeleteTemplate(item: ReportTemplateOption): Promise<void> {
    if (!window.confirm(`Excluir o template "${item.label}"? Essa ação não pode ser desfeita.`)) return;
    loading.show();
    try {
      await deleteReportTemplate(templateDbId(item));
      toast.success('Template excluído.');
      await reloadTemplates();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível excluir o template.');
    } finally {
      loading.hide();
    }
  }

  function templateDbId(item: ReportTemplateOption): number {
    return Number(item.id.replace('custom:', ''));
  }

  function extrairDriveFileId(valor: string): string {
    const match = valor.match(/\/d\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : valor.trim();
  }

  function createSourcePanel(item: { categoria: SourceTemplateCategory; label: string; extensao: string; descricaoGoogle: string }): HTMLElement {
    const panel = createElement('section', { className: 'data-panel reports-config-panel' });
    panel.appendChild(createElement('h3', { textContent: item.label }));

    const origem = origens[item.categoria];
    if (origem?.tipoOrigem) {
      panel.appendChild(createElement('p', {
        className: 'settings-hint',
        textContent: origem.tipoOrigem === 'drive' ? `Drive: ${origem.driveFileId}` : `Arquivo: ${origem.documentoNome}`,
      }));
      const removeButton = createElement('button', { className: 'danger-button button-with-icon small-button', type: 'button' });
      removeButton.append(createIcon('trash'), document.createTextNode('Remover'));
      removeButton.addEventListener('click', () => void handleRemoveSource(item));
      panel.appendChild(removeButton);
      return panel;
    }

    panel.appendChild(createElement('p', { className: 'empty-state small', textContent: `Gerado do zero. Marcador: {{TABELA}}` }));

    const driveForm = createElement('form', { className: 'page-actions' });
    const driveInput = createElement('input'); driveInput.type = 'text'; driveInput.placeholder = item.descricaoGoogle; driveInput.required = true;
    const driveSubmit = createElement('button', { className: 'small-button', type: 'submit', textContent: 'Usar do Drive' });
    driveForm.append(driveInput, driveSubmit);
    driveForm.addEventListener('submit', (event) => {
      event.preventDefault();
      void handleSetDriveSource(item, extrairDriveFileId(driveInput.value), driveForm);
    });
    panel.appendChild(driveForm);

    panel.appendChild(createUploadForm(item));

    return panel;
  }

  function createUploadForm(item: { categoria: SourceTemplateCategory; label: string; extensao: string }): HTMLElement {
    const form = createElement('form', { className: 'page-actions' });
    const fileInput = createElement('input'); fileInput.type = 'file'; fileInput.accept = item.extensao; fileInput.hidden = true;
    const chooseButton = createElement('button', { className: 'secondary-button button-with-icon small-button', type: 'button' });
    chooseButton.append(createIcon('upload'), document.createTextNode('Escolher arquivo'));
    const fileNameLabel = createElement('span', { className: 'settings-hint' });
    const uploadSubmit = createElement('button', { className: 'small-button', type: 'submit', textContent: 'Enviar' });
    uploadSubmit.disabled = true;

    chooseButton.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      const file = fileInput.files?.[0];
      fileNameLabel.textContent = file?.name ?? '';
      uploadSubmit.disabled = !file;
    });

    form.append(fileInput, chooseButton, fileNameLabel, uploadSubmit);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const file = fileInput.files?.[0];
      if (file) void handleSetUploadSource(item, file, form, fileNameLabel);
    });
    return form;
  }

  async function handleSetDriveSource(item: { categoria: SourceTemplateCategory; label: string }, driveFileId: string, form: HTMLFormElement): Promise<void> {
    loading.show();
    try {
      await setSourceTemplateDrive(item.categoria, driveFileId);
      toast.success('Template configurado.');
      form.reset();
      await reloadOrigem(item.categoria);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível configurar o template.');
    } finally {
      loading.hide();
    }
  }

  async function handleSetUploadSource(
    item: { categoria: SourceTemplateCategory; label: string }, file: File, form: HTMLFormElement, fileNameLabel: HTMLElement
  ): Promise<void> {
    loading.show();
    try {
      await setSourceTemplateUpload(item.categoria, file);
      toast.success('Template configurado.');
      form.reset();
      fileNameLabel.textContent = '';
      await reloadOrigem(item.categoria);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível configurar o template.');
    } finally {
      loading.hide();
    }
  }

  async function handleRemoveSource(item: { categoria: SourceTemplateCategory; label: string }): Promise<void> {
    if (!window.confirm(`Remover o template de ${item.label}? Esses formatos voltam a ser gerados do zero.`)) return;
    loading.show();
    try {
      await removeSourceTemplate(item.categoria);
      toast.success('Template removido.');
      await reloadOrigem(item.categoria);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível remover o template.');
    } finally {
      loading.hide();
    }
  }

  function createReportCard(tipo: ReportTypeOption): HTMLElement {
    const card = createElement('section', { className: 'report-card' });
    card.appendChild(createElement('h2', { textContent: tipo.label }));
    const formatField = createElement('label', { className: 'form-field' });
    const format = createElement('select') as HTMLSelectElement;
    (Object.keys(FORMAT_LABELS) as ReportFormat[]).forEach((value) => {
      const option = createElement('option', { textContent: FORMAT_LABELS[value] }) as HTMLOptionElement;
      option.value = value;
      format.appendChild(option);
    });
    formatField.append(createElement('span', { textContent: 'Formato' }), format);
    card.appendChild(formatField);

    const templateField = createElement('label', { className: 'form-field' });
    const template = createElement('select') as HTMLSelectElement;
    templates.forEach((option) => {
      const el = createElement('option', { textContent: option.label }) as HTMLOptionElement;
      el.value = option.id;
      template.appendChild(el);
    });
    templateField.append(createElement('span', { textContent: 'Template' }), template);
    card.appendChild(templateField);

    let competencia: HTMLInputElement | undefined;
    if (tipo.tipo === 'financeiro' || tipo.tipo === 'rateio') {
      const competenciaField = createElement('label', { className: 'form-field' });
      competencia = createElement('input') as HTMLInputElement;
      competencia.type = 'month';
      competenciaField.append(createElement('span', { textContent: 'Competência (opcional)' }), competencia);
      card.appendChild(competenciaField);
    }
    const generate = createElement('button', { type: 'button', textContent: 'Gerar' });
    const result = createElement('div', { className: 'report-card-result' });
    generate.addEventListener('click', () => void handleGenerate(tipo.tipo, format.value as ReportFormat, competencia?.value || undefined, template.value || undefined, generate, result));
    card.append(generate, result);
    return card;
  }

  async function handleGenerate(tipo: ReportTypeOption['tipo'], formato: ReportFormat, competencia: string | undefined, template: string | undefined, button: HTMLElement, result: HTMLElement): Promise<void> {
    (button as HTMLButtonElement).disabled = true;
    loading.show();
    result.replaceChildren();
    try {
      if (FORMATOS_ARQUIVO.includes(formato)) {
        await downloadReportFile(tipo, formato, competencia, template);
        result.appendChild(createElement('p', { textContent: 'Arquivo baixado.' }));
      } else {
        const report = await generateReport(tipo, formato, competencia, template);
        const link = createElement('a', { textContent: 'Abrir no Google' }) as HTMLAnchorElement;
        link.href = report.webViewLink;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        result.appendChild(link);
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === 'GOOGLE_SCOPE_MISSING') {
        const warning = createElement('p', { className: 'importacao-error', textContent: 'Sua conta Google não tem permissão de escrita suficiente para gerar relatórios.' });
        const reconnect = createElement('a', { textContent: 'Reconectar conta Google' }) as HTMLAnchorElement;
        reconnect.href = getGoogleAuthorizeUrl();
        result.append(warning, reconnect);
      } else {
        toast.error(error instanceof Error ? error.message : 'Não foi possível gerar o relatório.');
      }
    } finally {
      (button as HTMLButtonElement).disabled = false;
      loading.hide();
    }
  }
}
