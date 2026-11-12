import { createDataTable } from '../components/DataTable';
import { createStatusBadge, type StatusTone } from '../components/StatusBadge';
import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { createBaseLayout } from '../layouts/BaseLayout';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { getCrmLeads, sincronizarCrmLeads, type CrmLead } from '../services/crmLeadService';
import { t } from '../services/i18nService';

export function createCrmLeadsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const layout = createBaseLayout({
    content,
    eyebrow: t('crmLeads.page.eyebrow'),
    title: t('crmLeads.page.title')
  });
  const loading = useGlobalLoading();
  const toast = useToast();
  let leads: CrmLead[] = [];
  let state: 'ready' | 'loading' | 'error' = 'loading';

  void load();

  return layout;

  async function load(): Promise<void> {
    state = 'loading';
    renderContent();
    try {
      leads = await getCrmLeads();
      state = 'ready';
    } catch {
      leads = [];
      state = 'error';
      toast.error(t('crmLeads.page.loadError'));
    } finally {
      renderContent();
    }
  }

  async function handleSync(): Promise<void> {
    loading.show();
    try {
      const resumo = await sincronizarCrmLeads();
      toast.success(
        t('crmLeads.page.syncSuccess')
          .replace('{imported}', String(resumo.totalImportados))
          .replace('{updated}', String(resumo.totalAtualizados))
      );
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('crmLeads.page.syncError'));
    } finally {
      loading.hide();
    }
  }

  function renderContent(): void {
    content.replaceChildren(renderList());
  }

  function renderList(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });

    const toolbar = createElement('div', { className: 'page-actions' });
    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';

    const syncButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    syncButton.append(createIcon('refresh'), document.createTextNode(t('crmLeads.page.syncButton')));
    syncButton.addEventListener('click', () => void handleSync());

    toolbar.append(spacer, syncButton);

    const panel = createDataTable<CrmLead>({
      title: t('crmLeads.page.tableTitle'),
      eyebrow: t('crmLeads.page.eyebrow'),
      rows: leads,
      state,
      emptyMessage: state === 'error' ? t('crmLeads.page.loadError') : t('crmLeads.page.empty'),
      columns: [
        { key: 'titulo', label: t('crmLeads.page.colTitulo'), render: (lead) => lead.titulo || '-' },
        { key: 'pipelineNome', label: t('crmLeads.page.colPipeline'), render: (lead) => lead.pipelineNome || '-' },
        { key: 'etapaNome', label: t('crmLeads.page.colEtapa'), render: (lead) => lead.etapaNome || '-' },
        { key: 'valor', label: t('crmLeads.page.colValor'), align: 'right', render: (lead) => lead.valor || '-' },
        { key: 'status', label: t('crmLeads.page.colStatus'), render: (lead) => createLeadStatusBadge(lead.status) },
        { key: 'importadoEm', label: t('crmLeads.page.colImportadoEm'), render: (lead) => formatDate(lead.importadoEm) }
      ]
    });

    fragment.append(toolbar, panel);
    return fragment;
  }
}

function createLeadStatusBadge(status: number | null): HTMLElement {
  const labels: Record<number, string> = {
    0: t('crmLeads.page.statusAberta'),
    1: t('crmLeads.page.statusGanha'),
    3: t('crmLeads.page.statusPerdida')
  };
  const tones: Record<number, StatusTone> = { 0: 'neutral', 1: 'success', 3: 'danger' };
  const key = status ?? 0;
  return createStatusBadge(labels[key] ?? String(status), tones[key] ?? 'neutral');
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}
