import { createDetailDrawer } from '../components/DetailDrawer';
import { createBadge, detailSection, formatCurrency, formatDate, formatReference, statusLabel } from '../components/FaturasUi';
import { attachTooltip } from '../components/Tooltip';
import { createElement } from '../dom';
import { ApiRequestError } from '../services/apiClient';
import { gerarBoletoConcessionaria, getBillingExecution, getBillingExecutions, type BillingExecution, type BillingInvoice } from '../services/billingCalculationsService';
import { cancelFatura, syncFatura, type FaturaRow } from '../services/faturasService';
import type { ClientRow } from '../services/clientsService';
import type { PendenciaRow } from '../services/pendenciasService';

const MISSING_FIELD_LABELS: Record<string, string> = {
  ucId: 'UC', valor: 'valor da concessionária', dataVencimento: 'vencimento',
  competencia: 'competência', statusValidacao: 'validação da fatura'
};

interface InvoiceDetailOptions {
  content: HTMLElement;
  clients: ClientRow[];
  isPlatformAdmin: boolean;
  canIssue: boolean;
  empresaId: number | undefined;
  contextualCharges: (invoice: BillingInvoice) => FaturaRow[];
  relatedPendencias: (invoice: BillingInvoice) => PendenciaRow[];
  invoiceDownloadButton: (invoice: BillingInvoice) => HTMLButtonElement;
  canIssueInvoice: (invoice: BillingInvoice) => boolean;
  openCreateModal: (invoice: BillingInvoice) => void;
  getSelectedInvoiceId: () => number | null;
  reload: () => Promise<void>;
  toast: { success: (message: string) => void; error: (message: string) => void };
  onClose: () => void;
}

export function createFaturaInvoiceDetail(invoice: BillingInvoice, options: InvoiceDetailOptions): void {
  const {
    content, clients, isPlatformAdmin, canIssue, empresaId, contextualCharges,
    relatedPendencias, invoiceDownloadButton, canIssueInvoice, openCreateModal,
    getSelectedInvoiceId, reload, toast, onClose
  } = options;
  const body = createElement('div', { className: 'fatura-drawer-content' });
  const context = createElement('nav', { className: 'fatura-context-path' });
  context.setAttribute('aria-label', 'Contexto da fatura');
  const contextLinks: Array<[string, string | null]> = [
    [invoice.clienteNome ?? clients.find((client) => client.id === invoice.clientId)?.nome ?? 'Cliente', invoice.clientId ? `/clientes?selecionada=${invoice.clientId}` : null],
    [invoice.ucCodigo ?? 'UC aguardando validação', invoice.consumerUnitId ? `/ucs?selecionada=${invoice.consumerUnitId}` : null]
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
  const utility = detailSection('Fatura da concessionária', [
    ['Cliente', invoice.clienteNome ?? clients.find((client) => client.id === invoice.clientId)?.nome ?? '—'],
    ['UC', invoice.ucCodigo ?? 'Aguardando validação'],
    ['Usinas vinculadas', invoice.usinas?.map((plant) => plant.nome).join(', ') || 'Sem vínculo comprovado'],
    ['Competência', formatReference(invoice.competencia)],
    ['Valor', formatCurrency(invoice.valorTotalConcessionaria)],
    ['Vencimento', formatDate(invoice.dataVencimento)],
    ['Extração', invoice.statusExtracao], ['Validação', invoice.statusValidacao]
  ]);
  if (invoice.documentoDisponivel) utility.appendChild(invoiceDownloadButton(invoice));
  if (canIssue) utility.appendChild(gerarBoletoButton(invoice));
  if (canIssue && cancelableCharge) utility.appendChild(cancelChargeButton(cancelableCharge, 'Excluir boleto'));
  const history = createElement('section', { className: 'fatura-detail-section' });
  history.append(createElement('h3', { textContent: 'Histórico auditável' }), createElement('p', { textContent: 'Carregando execuções persistidas…' }));
  const chargeSection = createElement('section', { className: 'fatura-detail-section' });
  chargeSection.appendChild(createElement('h3', { textContent: 'Cobrança comercial ASAAS' }));
  const platformCharges = isPlatformAdmin && !isPlatformAdminTestEmpresa ? invoice.contextualCharges ?? [] : [];
  if (!linkedCharges.length && !platformCharges.length) chargeSection.appendChild(createElement('p', { textContent: 'Nenhuma cobrança encontrada para esta UC e competência.' }));
  else {
    chargeSection.appendChild(createElement('p', { className: 'fatura-context-note', textContent: 'Cobranças encontradas pela UC e competência; o vínculo documental ainda não é confirmado pela API.' }));
    platformCharges.forEach((charge) => chargeSection.appendChild(detailSection(`Cobrança #${charge.id}`, [
      ['Valor comercial', formatCurrency(charge.valor)], ['Vencimento', formatDate(charge.mesVencimento)],
      ['Situação', charge.asaasId ? statusLabel(charge.asaasStatus as FaturaRow['asaasStatus']) : charge.statusInterno ?? 'Aguardando emissão']
    ])));
    linkedCharges.forEach((charge) => {
      const card = detailSection(`Cobrança #${charge.id}`, [
        ['Valor comercial', formatCurrency(charge.valor)], ['Vencimento', formatDate(charge.mesVencimento)],
        ['Situação', charge.asaasId ? statusLabel(charge.asaasStatus) : charge.statusInterno ?? 'Aguardando emissão']
      ]);
      const actions = createElement('div', { className: 'form-actions' });
      if (charge.boletoUrl) {
        const boleto = createElement('a', { className: 'secondary-button', textContent: 'Abrir boleto ASAAS' });
        boleto.href = charge.boletoUrl; boleto.target = '_blank'; boleto.rel = 'noreferrer'; actions.appendChild(boleto);
      }
      if (canIssue) {
        const sync = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Sincronizar' });
        sync.addEventListener('click', () => void runChargeAction(sync, () => syncFatura(charge.id), 'Cobrança sincronizada.', drawer));
        actions.appendChild(sync);
        if (charge.asaasId && charge.asaasStatus === 'pending') actions.appendChild(cancelChargeButton(charge, 'Cancelar cobrança'));
      }
      card.appendChild(actions);
      chargeSection.appendChild(card);
    });
  }
  const pendingSection = createElement('section', { className: 'fatura-detail-section' });
  pendingSection.appendChild(createElement('h3', { textContent: 'Pendências relacionadas' }));
  const related = relatedPendencias(invoice);
  if (!related.length) pendingSection.appendChild(createElement('p', { textContent: invoice.temPendencia ? 'Há pendência operacional. Consulte a central de pendências.' : 'Nenhuma pendência aberta vinculada.' }));
  related.forEach((item) => {
    const link = createElement('a', { textContent: item.titulo });
    link.href = `/pendencias?selecionada=${item.id}`;
    pendingSection.appendChild(link);
  });
  body.append(context, utility, history, chargeSection, pendingSection);
  const drawer = createDetailDrawer({
    title: `Fatura da concessionária #${invoice.id}`,
    badge: createBadge(invoice.statusValidacao === 'pendente' ? invoice.statusExtracao : invoice.statusValidacao),
    tabs: [{ label: 'Detalhes e histórico', content: body }],
    onClose
  });
  if (canIssueInvoice(invoice)) {
    const issue = createElement('button', { type: 'button', textContent: 'Emitir cobrança para esta fatura' });
    issue.addEventListener('click', () => { drawer.remove(); openCreateModal(invoice); }); body.appendChild(issue);
  }
  content.appendChild(drawer);
  void renderAuditHistory(invoice, history);

  async function renderAuditHistory(invoice: BillingInvoice, section: HTMLElement): Promise<void> {
    try {
      const summaries = await getBillingExecutions(empresaId, invoice.id);
      if (getSelectedInvoiceId() !== invoice.id) return;
      const details = await Promise.all(summaries.map((item) => getBillingExecution(empresaId, item.id)));
      if (getSelectedInvoiceId() !== invoice.id) return;
      const timeline = createElement('ol', { className: 'fatura-timeline' });
      timeline.appendChild(timelineEvent('Fatura recebida', invoice.createdAt, 'Documento persistido no HUB.'));
      if (invoice.statusExtracao !== 'pendente') timeline.appendChild(timelineEvent(`Extração: ${invoice.statusExtracao}`, null, 'Estado persistido da fatura.'));
      if (invoice.statusValidacao !== 'pendente') timeline.appendChild(timelineEvent(`Validação: ${invoice.statusValidacao}`, null, 'Estado persistido da fatura.'));
      details.forEach((execution) => timeline.appendChild(executionEvent(execution)));
      section.replaceChildren(createElement('h3', { textContent: 'Histórico auditável' }), timeline);
      if (!details.length) section.appendChild(createElement('p', { className: 'fatura-history-empty', textContent: 'Nenhuma execução de cálculo persistida para esta fatura.' }));
    } catch (cause) {
      if (getSelectedInvoiceId() !== invoice.id) return;
      section.replaceChildren(createElement('h3', { textContent: 'Histórico auditável' }), createElement('p', { textContent: cause instanceof Error ? cause.message : 'Não foi possível carregar o histórico persistido.' }));
    }
  }

  function timelineEvent(title: string, timestamp: string | null, description: string): HTMLElement {
    const item = createElement('li');
    item.append(createElement('strong', { textContent: title }), createElement('span', { textContent: timestamp ? formatAuditTimestamp(timestamp) : 'Data não registrada' }), createElement('p', { textContent: description }));
    return item;
  }

  function executionEvent(execution: BillingExecution): HTMLElement {
    const facts = [`Status: ${execution.status}`];
    if (execution.blockedStage) facts.push(`Etapa bloqueada: ${execution.blockedStage}`);
    if (execution.blockers.length) facts.push(`Bloqueios: ${execution.blockers.join('; ')}`);
    const stages = execution.auditoria?.stages ?? [];
    if (stages.length) facts.push(`Etapas registradas: ${stages.map((stage) => `${stage.stage} (${stage.status})`).join(', ')}`);
    return timelineEvent(`Execução de cálculo #${execution.id}`, execution.createdAt, facts.join(' · '));
  }

  function formatAuditTimestamp(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(parsed);
  }

  async function runChargeAction(button: HTMLButtonElement, action: () => Promise<unknown>, message: string, overlay: HTMLElement): Promise<void> {
    button.disabled = true;
    try { await action(); toast.success(message); overlay.remove(); await reload(); }
    catch (cause) { toast.error(cause instanceof Error ? cause.message : 'Não foi possível concluir a ação.'); }
    finally { button.disabled = false; }
  }

  function cancelChargeButton(charge: FaturaRow, label: string): HTMLButtonElement {
    const button = createElement('button', { className: 'danger-button', type: 'button', textContent: label });
    button.addEventListener('click', () => { if (window.confirm('Cancelar esta cobrança na ASAAS?')) void runChargeAction(button, () => cancelFatura(charge.id), 'Cobrança cancelada.', drawer); });
    return button;
  }

  function gerarBoletoButton(target: BillingInvoice): HTMLButtonElement {
    const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Gerar boleto' });
    const enabled = canIssueInvoice(target);
    button.disabled = !enabled;
    if (!enabled) attachTooltip(button, 'Fatura precisa estar validada, com UC, valor, vencimento e sem pendência para gerar boleto.');
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      button.disabled = true;
      void gerarBoletoConcessionaria(target.id)
        .then(() => { toast.success('Boleto gerado.'); drawer.remove(); return reload(); })
        .catch((cause) => {
          if (cause instanceof ApiRequestError && cause.code === 'INVOICE_DATA_INCOMPLETE') {
            const missing = ((cause.details as { missing?: string[] } | undefined)?.missing ?? []).map((field) => MISSING_FIELD_LABELS[field] ?? field);
            toast.error(`Dados incompletos para gerar boleto: ${missing.join(', ')}.`);
          } else if (cause instanceof ApiRequestError && cause.code === 'EMISSAO_PENDENTE') {
            toast.error('Emissão deste boleto já está em andamento. Aguarde a conclusão.');
          } else {
            toast.error(cause instanceof Error ? cause.message : 'Não foi possível gerar o boleto.');
          }
        })
        .finally(() => { button.disabled = !enabled; });
    });
    button.addEventListener('keydown', (event) => event.stopPropagation());
    return button;
  }
}
