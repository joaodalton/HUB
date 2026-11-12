import { createDetailDrawer } from '../components/DetailDrawer';
import { createBadge, currentBoleto, detailSection, extracaoLabel, formatCurrency, formatDate, formatReference, internoLabel, statusLabel, validacaoLabel } from '../components/FaturasUi';
import { createElement } from '../dom';
import { getBillingExecution, getBillingExecutions, type BillingExecution, type BillingInvoice } from '../services/billingCalculationsService';
import { cancelFatura, syncFatura, type FaturaRow } from '../services/faturasService';
import type { ClientRow } from '../services/clientsService';
import type { PendenciaRow } from '../services/pendenciasService';
import { t } from '../services/i18nService';

interface InvoiceDetailOptions {
  content: HTMLElement;
  clients: ClientRow[];
  isPlatformAdmin: boolean;
  canIssue: boolean;
  empresaId: number | undefined;
  contextualCharges: (invoice: BillingInvoice) => FaturaRow[];
  relatedPendencias: (invoice: BillingInvoice) => PendenciaRow[];
  invoiceDownloadButton: (invoice: BillingInvoice) => HTMLButtonElement;
  getSelectedInvoiceId: () => number | null;
  reload: () => Promise<void>;
  toast: { success: (message: string) => void; error: (message: string) => void };
  onClose: () => void;
}

export function createFaturaInvoiceDetail(invoice: BillingInvoice, options: InvoiceDetailOptions): void {
  const {
    content, clients, isPlatformAdmin, canIssue, empresaId, contextualCharges,
    relatedPendencias, invoiceDownloadButton,
    getSelectedInvoiceId, reload, toast, onClose
  } = options;
  const body = createElement('div', { className: 'fatura-drawer-content' });
  const context = createElement('nav', { className: 'fatura-context-path' });
  context.setAttribute('aria-label', t('faturas.detail.contextAriaLabel'));
  const contextLinks: Array<[string, string | null]> = [
    [invoice.clienteNome ?? clients.find((client) => client.id === invoice.clientId)?.nome ?? t('faturas.detail.contextCliente'), invoice.clientId ? `/clientes?selecionada=${invoice.clientId}` : null],
    [invoice.ucCodigo ?? t('faturas.detail.contextUcAwaiting'), invoice.consumerUnitId ? `/ucs?selecionada=${invoice.consumerUnitId}` : null]
  ];
  (invoice.usinas ?? []).forEach((plant) => contextLinks.push([plant.nome, `/usinas?selecionada=${plant.id}`]));
  contextLinks.forEach(([label, href], index) => {
    if (index) context.appendChild(createElement('span', { textContent: '›', className: 'fatura-context-separator' }));
    if (!href) context.appendChild(createElement('span', { textContent: label }));
    else { const link = createElement('a', { textContent: label }); link.href = href; context.appendChild(link); }
  });
  // Exceção de teste: plataforma admin pode agir como owner só na empresa de testes (id 1).
  // Não afeta nenhuma outra empresa real. Remover/revisar se o fluxo de teste mudar.
  const PLATFORM_ADMIN_TEST_EMPRESA_ID = 1;
  const isPlatformAdminTestEmpresa = isPlatformAdmin && empresaId === PLATFORM_ADMIN_TEST_EMPRESA_ID;
  const linkedCharges = isPlatformAdmin && !isPlatformAdminTestEmpresa ? [] : contextualCharges(invoice);
  const cancelableCharge = linkedCharges.find((charge) => charge.asaasId && charge.asaasStatus === 'pending');
  const utility = detailSection(t('faturas.detail.sectionTitle'), [
    [t('faturas.detail.labelCliente'), invoice.clienteNome ?? clients.find((client) => client.id === invoice.clientId)?.nome ?? '—'],
    [t('faturas.detail.labelUc'), invoice.ucCodigo ?? t('faturas.detail.awaitingValidation')],
    [t('faturas.detail.labelUsinasVinculadas'), invoice.usinas?.map((plant) => plant.nome).join(', ') || t('faturas.detail.noPlantProof')],
    [t('faturas.detail.labelCompetencia'), formatReference(invoice.competencia)],
    [t('faturas.detail.labelValor'), formatCurrency(invoice.valorTotalConcessionaria)],
    [t('faturas.detail.labelVencimento'), formatDate(invoice.dataVencimento)],
    [t('faturas.detail.labelExtracao'), extracaoLabel(invoice.statusExtracao)], [t('faturas.detail.labelValidacao'), validacaoLabel(invoice.statusValidacao)]
  ]);
  if (invoice.documentoDisponivel) utility.appendChild(invoiceDownloadButton(invoice));
  if (canIssue && !currentBoleto(invoice.contextualCharges ?? []).boleto) utility.appendChild(financeiroLink());
  if (canIssue && cancelableCharge) utility.appendChild(cancelChargeButton(cancelableCharge, t('faturas.detail.deleteBoleto')));
  const history = createElement('section', { className: 'fatura-detail-section' });
  history.append(createElement('h3', { textContent: t('faturas.detail.auditHistory') }), createElement('p', { textContent: t('faturas.detail.loadingExecutions') }));
  const chargeSection = createElement('section', { className: 'fatura-detail-section' });
  chargeSection.appendChild(createElement('h3', { textContent: t('faturas.detail.commercialChargeTitle') }));
  const platformCharges = isPlatformAdmin && !isPlatformAdminTestEmpresa ? invoice.contextualCharges ?? [] : [];
  if (!linkedCharges.length && !platformCharges.length) chargeSection.appendChild(createElement('p', { textContent: t('faturas.detail.noChargeFound') }));
  else {
    chargeSection.appendChild(createElement('p', { className: 'fatura-context-note', textContent: t('faturas.detail.chargesNote') }));
    platformCharges.forEach((charge) => chargeSection.appendChild(detailSection(`${t('faturas.detail.chargePrefix')} #${charge.id}`, [
      [t('faturas.detail.labelValorComercial'), formatCurrency(charge.valor)], [t('faturas.detail.labelVencimento'), formatDate(charge.mesVencimento)],
      [t('faturas.detail.labelSituacao'), charge.asaasId ? statusLabel(charge.asaasStatus as FaturaRow['asaasStatus']) : charge.statusInterno ? internoLabel(charge.statusInterno) : t('faturas.detail.awaitingIssuance')]
    ])));
    linkedCharges.forEach((charge) => {
      const card = detailSection(`${t('faturas.detail.chargePrefix')} #${charge.id}`, [
        [t('faturas.detail.labelValorComercial'), formatCurrency(charge.valor)], [t('faturas.detail.labelVencimento'), formatDate(charge.mesVencimento)],
        [t('faturas.detail.labelSituacao'), charge.asaasId ? statusLabel(charge.asaasStatus) : charge.statusInterno ? internoLabel(charge.statusInterno) : t('faturas.detail.awaitingIssuance')]
      ]);
      const actions = createElement('div', { className: 'form-actions' });
      if (charge.boletoUrl) {
        const boleto = createElement('a', { className: 'secondary-button', textContent: t('faturas.detail.openBoleto') });
        boleto.href = charge.boletoUrl; boleto.target = '_blank'; boleto.rel = 'noreferrer'; actions.appendChild(boleto);
      }
      if (canIssue) {
        const sync = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.detail.sync') });
        sync.addEventListener('click', () => void runChargeAction(sync, () => syncFatura(charge.id), t('faturas.detail.chargeSynced'), drawer));
        actions.appendChild(sync);
        if (charge.asaasId && charge.asaasStatus === 'pending') actions.appendChild(cancelChargeButton(charge, t('faturas.detail.cancelCharge')));
      }
      card.appendChild(actions);
      chargeSection.appendChild(card);
    });
  }
  const pendingSection = createElement('section', { className: 'fatura-detail-section' });
  pendingSection.appendChild(createElement('h3', { textContent: t('faturas.detail.relatedPendenciasTitle') }));
  const related = relatedPendencias(invoice);
  if (!related.length) pendingSection.appendChild(createElement('p', { textContent: invoice.temPendencia ? t('faturas.detail.hasPendingOperational') : t('faturas.detail.noPendingLinked') }));
  related.forEach((item) => {
    const link = createElement('a', { textContent: item.titulo });
    link.href = `/pendencias?selecionada=${item.id}`;
    pendingSection.appendChild(link);
  });
  body.append(context, utility, history, chargeSection, pendingSection);
  const drawer = createDetailDrawer({
    title: `${t('faturas.detail.drawerTitlePrefix')} #${invoice.id}`,
    badge: createBadge(invoice.statusValidacao === 'pendente' ? extracaoLabel(invoice.statusExtracao) : validacaoLabel(invoice.statusValidacao)),
    tabs: [{ label: t('faturas.detail.tabDetails'), content: body }],
    onClose
  });
  content.appendChild(drawer);
  void renderAuditHistory(invoice, history);

  async function renderAuditHistory(invoice: BillingInvoice, section: HTMLElement): Promise<void> {
    try {
      const summaries = await getBillingExecutions(empresaId, invoice.id);
      if (getSelectedInvoiceId() !== invoice.id) return;
      const details = await Promise.all(summaries.map((item) => getBillingExecution(empresaId, item.id)));
      if (getSelectedInvoiceId() !== invoice.id) return;
      const timeline = createElement('ol', { className: 'fatura-timeline' });
      timeline.appendChild(timelineEvent(t('faturas.detail.timelineReceived'), invoice.createdAt, t('faturas.detail.timelineReceivedDesc')));
      if (invoice.statusExtracao !== 'pendente') timeline.appendChild(timelineEvent(`${t('faturas.detail.timelineExtracao')}: ${extracaoLabel(invoice.statusExtracao)}`, null, t('faturas.detail.timelinePersistedState')));
      if (invoice.statusValidacao !== 'pendente') timeline.appendChild(timelineEvent(`${t('faturas.detail.timelineValidacao')}: ${validacaoLabel(invoice.statusValidacao)}`, null, t('faturas.detail.timelinePersistedState')));
      details.forEach((execution) => timeline.appendChild(executionEvent(execution)));
      section.replaceChildren(createElement('h3', { textContent: t('faturas.detail.auditHistory') }), timeline);
      if (!details.length) section.appendChild(createElement('p', { className: 'fatura-history-empty', textContent: t('faturas.detail.noPersistedExecutions') }));
    } catch (cause) {
      if (getSelectedInvoiceId() !== invoice.id) return;
      section.replaceChildren(createElement('h3', { textContent: t('faturas.detail.auditHistory') }), createElement('p', { textContent: cause instanceof Error ? cause.message : t('faturas.detail.historyLoadError') }));
    }
  }

  function timelineEvent(title: string, timestamp: string | null, description: string): HTMLElement {
    const item = createElement('li');
    item.append(createElement('strong', { textContent: title }), createElement('span', { textContent: timestamp ? formatAuditTimestamp(timestamp) : t('faturas.detail.noDateRegistered') }), createElement('p', { textContent: description }));
    return item;
  }

  function executionEvent(execution: BillingExecution): HTMLElement {
    const facts = [`${t('faturas.detail.factStatus')}: ${execution.status}`];
    if (execution.blockedStage) facts.push(`${t('faturas.detail.factBlockedStage')}: ${execution.blockedStage}`);
    if (execution.blockers.length) facts.push(`${t('faturas.detail.factBlockers')}: ${execution.blockers.join('; ')}`);
    const stages = execution.auditoria?.stages ?? [];
    if (stages.length) facts.push(`${t('faturas.detail.factStagesRegistered')}: ${stages.map((stage) => `${stage.stage} (${stage.status})`).join(', ')}`);
    return timelineEvent(`${t('faturas.detail.executionPrefix')} #${execution.id}`, execution.createdAt, facts.join(' · '));
  }

  function formatAuditTimestamp(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(parsed);
  }

  async function runChargeAction(button: HTMLButtonElement, action: () => Promise<unknown>, message: string, overlay: HTMLElement): Promise<void> {
    button.disabled = true;
    try { await action(); toast.success(message); overlay.remove(); await reload(); }
    catch (cause) { toast.error(cause instanceof Error ? cause.message : t('faturas.detail.actionError')); }
    finally { button.disabled = false; }
  }

  function financeiroLink(): HTMLButtonElement {
    const link = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.detail.goToFinanceiro') });
    link.addEventListener('click', () => {
      window.history.pushState({}, '', '/financeiro');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    return link;
  }

  function cancelChargeButton(charge: FaturaRow, label: string): HTMLButtonElement {
    const button = createElement('button', { className: 'danger-button', type: 'button', textContent: label });
    button.addEventListener('click', () => { if (window.confirm(t('faturas.detail.confirmCancelCharge'))) void runChargeAction(button, () => cancelFatura(charge.id), t('faturas.detail.chargeCanceled'), drawer); });
    return button;
  }
}
