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
  getSourceTemplate, updateReportTemplate,
  type ReportFormat, type ReportTemplateOption, type ReportTypeOption, type SourceTemplateCategory, type SourceTemplateConfig
} from '../services/reportsService';
import { createSourcePanel } from './reportsSourcePanel';
import { t } from '../services/i18nService';

function reportTypeLabel(tipo: ReportTypeOption['tipo']): string {
  const keys: Record<ReportTypeOption['tipo'], string> = {
    cadastro: 'reports.page.typeCadastro',
    financeiro: 'reports.page.typeFinanceiro',
    rateio: 'reports.page.typeRateio',
    producao: 'reports.page.typeProducao'
  };
  const key = keys[tipo];
  return key ? t(key) : tipo;
}

function systemTemplateLabel(item: ReportTemplateOption): string {
  const keys: Record<string, string> = {
    padrao: 'reports.page.templatePadrao',
    azul: 'reports.page.templateAzul',
    verde: 'reports.page.templateVerde'
  };
  const key = keys[item.id];
  return key ? t(key) : item.label;
}

function formatLabels(): Record<ReportFormat, string> {
  return { doc: t('reports.page.formatDoc'), sheet: t('reports.page.formatSheet'), slide: t('reports.page.formatSlide'), docx: t('reports.page.formatDocx'), xlsx: t('reports.page.formatXlsx'), pptx: t('reports.page.formatPptx') };
}
const FORMATOS_ARQUIVO: ReportFormat[] = ['docx', 'xlsx', 'pptx'];

function categoriasOrigem(): Array<{ categoria: SourceTemplateCategory; label: string; extensao: string; descricaoGoogle: string }> {
  return [
    { categoria: 'documento', label: t('reports.page.categoryDocumento'), extensao: '.docx', descricaoGoogle: t('reports.page.descGoogleDoc') },
    { categoria: 'planilha', label: t('reports.page.categoryPlanilha'), extensao: '.xlsx', descricaoGoogle: t('reports.page.descGoogleSheet') },
    { categoria: 'apresentacao', label: t('reports.page.categoryApresentacao'), extensao: '.pptx', descricaoGoogle: t('reports.page.descGoogleSlides') }];
}

export function createReportsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let tipos: ReportTypeOption[] = [];
  let templates: ReportTemplateOption[] = [];
  const origens: Record<SourceTemplateCategory, SourceTemplateConfig | null> = { documento: null, planilha: null, apresentacao: null };
  let loaded = false;
  let modalBody: HTMLElement | null = null;

  const layout = createBaseLayout({ content, eyebrow: t('nav.section.financeiro'), title: t('nav.item.relatorios') });
  render();
  void load();
  return layout;

  async function load(): Promise<void> {
    try {
      const [tiposResp, templatesResp, ...origensResp] = await Promise.all([
        getReportTypes(), getReportTemplates(), ...categoriasOrigem().map((item) => getSourceTemplate(item.categoria)),
      ]);
      tipos = tiposResp;
      templates = templatesResp;
      categoriasOrigem().forEach((item, index) => { origens[item.categoria] = origensResp[index]; });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('reports.page.loadError'));
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
    if (!loaded) { content.replaceChildren(createElement('p', { className: 'settings-hint', textContent: t('common.loading') })); return; }
    const actions = createElement('div', { className: 'page-actions' });
    actions.style.justifyContent = 'flex-end';
    const configButton = createElement('button', { className: 'small-button button-with-icon', type: 'button' });
    configButton.append(createIcon('settings'), document.createTextNode(t('nav.item.templates')));
    configButton.addEventListener('click', openTemplatesModal);
    actions.appendChild(configButton);

    const grid = createElement('div', { className: 'reports-grid' });
    tipos.forEach((tipo) => grid.appendChild(createReportCard(tipo)));
    content.replaceChildren(actions, grid);
    renderModal();
  }

  function openTemplatesModal(): void {
    const modal = createModalShell(t('reports.page.modalTitle'), t('reports.page.modalSubtitle'), () => { modalBody = null; });
    modal.dialog.classList.add('hub-modal-wide');
    modalBody = modal.body;
    renderModal();
    document.body.appendChild(modal.overlay);
  }

  function renderModal(): void {
    if (!modalBody) return;
    const sourceRow = createElement('div', { className: 'reports-source-row' });
    categoriasOrigem().forEach((item) => sourceRow.appendChild(createSourcePanel(item, { origens, loading, toast, reloadOrigem })));
    modalBody.replaceChildren(createTemplatesPanel(), sourceRow);
  }

  function createTemplatesPanel(): HTMLElement {
    const panel = createElement('section', { className: 'data-panel reports-config-panel' });
    panel.appendChild(createElement('h3', { textContent: t('reports.page.colorsTitle') }));
    panel.appendChild(createElement('p', {
      className: 'settings-hint',
      textContent: t('reports.page.colorsHint'),
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
    row.append(swatch, createElement('span', { textContent: systemTemplateLabel(item) }));

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.setAttribute('aria-label', t('reports.page.editTemplateAria'));
    editButton.addEventListener('click', () => void handleEditTemplate(item));

    const deleteButton = createElement('button', { className: 'icon-button danger', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.setAttribute('aria-label', t('reports.page.deleteTemplateAria'));
    deleteButton.addEventListener('click', () => void handleDeleteTemplate(item));

    row.append(editButton, deleteButton);
    return row;
  }

  function createTemplateForm(): HTMLElement {
    const form = createElement('form', { className: 'page-actions' });
    const nome = createElement('input'); nome.type = 'text'; nome.placeholder = t('reports.page.templateNamePlaceholder'); nome.required = true;
    const cor = createElement('input'); cor.type = 'color'; cor.value = '#2563eb'; cor.title = t('reports.page.accentColorTitle');
    const submit = createElement('button', { className: 'small-button', type: 'submit', textContent: t('reports.page.createButton') });
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
      toast.success(t('reports.page.templateCreatedSuccess'));
      form.reset();
      await reloadTemplates();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('reports.page.templateCreateError'));
    } finally {
      loading.hide();
    }
  }

  async function handleEditTemplate(item: ReportTemplateOption): Promise<void> {
    const novoNome = window.prompt(t('reports.page.templateNamePlaceholder'), item.label);
    if (novoNome === null) return;
    const novaCor = window.prompt(t('reports.page.accentColorPrompt'), item.accentHex ?? '');
    if (novaCor === null) return;
    loading.show();
    try {
      await updateReportTemplate(templateDbId(item), { nome: novoNome, accentHex: novaCor.trim() || null });
      toast.success(t('reports.page.templateUpdatedSuccess'));
      await reloadTemplates();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('reports.page.templateUpdateError'));
    } finally {
      loading.hide();
    }
  }

  async function handleDeleteTemplate(item: ReportTemplateOption): Promise<void> {
    if (!window.confirm(t('reports.page.confirmDeleteTemplate').replace('{name}', item.label))) return;
    loading.show();
    try {
      await deleteReportTemplate(templateDbId(item));
      toast.success(t('reports.page.templateDeletedSuccess'));
      await reloadTemplates();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('reports.page.templateDeleteError'));
    } finally {
      loading.hide();
    }
  }

  function templateDbId(item: ReportTemplateOption): number {
    return Number(item.id.replace('custom:', ''));
  }


  function createReportCard(tipo: ReportTypeOption): HTMLElement {
    const card = createElement('section', { className: 'report-card' });
    card.appendChild(createElement('h2', { textContent: reportTypeLabel(tipo.tipo) }));
    const formatField = createElement('label', { className: 'form-field' });
    const format = createElement('select') as HTMLSelectElement;
    const formatLabelsMap = formatLabels();
    (Object.keys(formatLabelsMap) as ReportFormat[]).forEach((value) => {
      const option = createElement('option', { textContent: formatLabelsMap[value] }) as HTMLOptionElement; option.value = value; format.appendChild(option);
    });
    formatField.append(createElement('span', { textContent: t('reports.page.fieldFormato') }), format);
    card.appendChild(formatField);

    const templateField = createElement('label', { className: 'form-field' });
    const template = createElement('select') as HTMLSelectElement;
    templates.forEach((option) => {
      const el = createElement('option', { textContent: systemTemplateLabel(option) }) as HTMLOptionElement;
      el.value = option.id;
      template.appendChild(el);
    });
    templateField.append(createElement('span', { textContent: t('reports.page.fieldTemplate') }), template);
    card.appendChild(templateField);

    let competencia: HTMLInputElement | undefined;
    if (tipo.tipo === 'financeiro' || tipo.tipo === 'rateio') {
      const competenciaField = createElement('label', { className: 'form-field' });
      competencia = createElement('input') as HTMLInputElement;
      competencia.type = 'month';
      competenciaField.append(createElement('span', { textContent: t('reports.page.fieldCompetencia') }), competencia);
      card.appendChild(competenciaField);
    }
    const generate = createElement('button', { type: 'button', textContent: t('reports.page.generateButton') });
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
        result.appendChild(createElement('p', { textContent: t('reports.page.fileDownloadedSuccess') }));
      } else {
        const report = await generateReport(tipo, formato, competencia, template);
        const link = createElement('a', { textContent: t('reports.page.openInGoogleLink') }) as HTMLAnchorElement;
        link.href = report.webViewLink;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        result.appendChild(link);
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === 'GOOGLE_SCOPE_MISSING') {
        const warning = createElement('p', { className: 'importacao-error', textContent: t('reports.page.googleScopeWarning') });
        const reconnect = createElement('a', { textContent: t('reports.page.reconnectGoogleLink') }) as HTMLAnchorElement;
        reconnect.href = getGoogleAuthorizeUrl();
        result.append(warning, reconnect);
      } else {
        toast.error(error instanceof Error ? error.message : t('reports.page.generateError'));
      }
    } finally {
      (button as HTMLButtonElement).disabled = false;
      loading.hide();
    }
  }
}
