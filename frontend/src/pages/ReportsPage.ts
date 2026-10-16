import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { ApiRequestError } from '../services/apiClient';
import { getGoogleAuthorizeUrl } from '../services/googleAccountService';
import { generateReport, getReportTypes, type ReportFormat, type ReportTypeOption } from '../services/reportsService';

const FORMAT_LABELS: Record<ReportFormat, string> = { doc: 'Documento (Doc)', sheet: 'Planilha (Sheet)', slide: 'Apresentação (Slides)' };

export function createReportsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let tipos: ReportTypeOption[] = [];
  let loaded = false;

  const layout = createBaseLayout({ content, eyebrow: 'Financeiro', title: 'Relatórios' });
  render();
  void load();
  return layout;

  async function load(): Promise<void> {
    try { tipos = await getReportTypes(); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível carregar os tipos de relatório.'); }
    finally { loaded = true; render(); }
  }

  function render(): void {
    const grid = createElement('div', { className: 'reports-grid' });
    if (!loaded) { content.replaceChildren(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' })); return; }
    tipos.forEach((tipo) => grid.appendChild(createReportCard(tipo)));
    content.replaceChildren(grid);
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
    const generate = createElement('button', { type: 'button', textContent: 'Gerar' });
    const result = createElement('div', { className: 'report-card-result' });
    generate.addEventListener('click', () => void handleGenerate(tipo.tipo, format.value as ReportFormat, generate, result));
    card.append(formatField, generate, result);
    return card;
  }

  async function handleGenerate(tipo: ReportTypeOption['tipo'], formato: ReportFormat, button: HTMLElement, result: HTMLElement): Promise<void> {
    (button as HTMLButtonElement).disabled = true;
    loading.show();
    result.replaceChildren();
    try {
      const report = await generateReport(tipo, formato);
      const link = createElement('a', { textContent: 'Abrir no Google' }) as HTMLAnchorElement;
      link.href = report.webViewLink;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      result.appendChild(link);
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
