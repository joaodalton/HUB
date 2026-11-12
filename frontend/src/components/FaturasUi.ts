import { createElement } from '../dom';
import type { BillingInvoice } from '../services/billingCalculationsService';
import type { FaturaRow } from '../services/faturasService';
import { t } from '../services/i18nService';
import type { AuthUser } from '../services/authService';
import { createStatusBadge, type StatusTone } from './StatusBadge';
export { formatDate } from '../utils/date';

export function detailSection(title: string, fields: Array<[string, string]>): HTMLElement {
  const section = createElement('section', { className: 'fatura-detail-section' });
  section.appendChild(createElement('h3', { textContent: title }));
  const grid = createElement('div', { className: 'detail-info-grid' });
  fields.forEach(([label, value]) => {
    const field = createElement('div', { className: 'detail-info-field' });
    field.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
    grid.appendChild(field);
  });
  section.appendChild(grid);
  return section;
}
export function option(value: string, label: string): HTMLOptionElement { const element = createElement('option', { textContent: label }); element.value = value; return element; }
export function filterSelect(label: string, value: string, options: Array<{ value: string; label: string }>, onChange: (value: string) => void): HTMLElement {
  const field = createElement('label', { className: 'faturas-filter-field' });
  const select = createElement('select'); select.append(...options.map((item) => option(item.value, item.label))); select.value = value;
  select.addEventListener('change', () => onChange(select.value));
  field.append(createElement('span', { textContent: label }), select); return field;
}
export function createBadge(label: string, tone: StatusTone = 'neutral'): HTMLElement {
  return createStatusBadge(label, tone);
}
export function statusLabel(status: FaturaRow['asaasStatus']): string {
  return ({
    pending: t('faturas.page.cobPending'),
    received: t('faturas.page.cobReceived'),
    overdue: t('faturas.page.cobOverdue'),
    canceled: t('faturas.page.cobCanceled'),
    refunded: t('faturas.page.cobRefunded')
  })[status];
}
export function extracaoLabel(status: string): string {
  return ({
    recebida: t('faturas.status.extracaoRecebida'),
    processando: t('faturas.status.extracaoProcessando'),
    extraida: t('faturas.status.extracaoExtraida'),
    layout_nao_reconhecido: t('faturas.status.extracaoLayoutNaoReconhecido'),
    erro: t('faturas.status.extracaoErro')
  } as Record<string, string>)[status] ?? status;
}
export function internoLabel(status: string): string {
  return ({
    aguardando_emissao: t('faturas.status.internoAguardandoEmissao'),
    emitida: t('faturas.status.internoEmitida'),
    erro_emissao: t('faturas.status.internoErroEmissao'),
    cancelada: t('faturas.status.internoCancelada')
  } as Record<string, string>)[status] ?? status;
}
export function validacaoLabel(status: string): string {
  return ({
    pendente: t('faturas.status.validacaoPendente'),
    valida: t('faturas.status.validacaoValida'),
    revisao_necessaria: t('faturas.status.validacaoRevisaoNecessaria'),
    uc_nao_encontrada: t('faturas.status.validacaoUcNaoEncontrada'),
    uc_pertence_outro_cliente: t('faturas.status.validacaoUcPertenceOutroCliente')
  } as Record<string, string>)[status] ?? status;
}
export function formatCurrency(value: string | number | null | undefined): string { return value == null ? '—' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value)); }
export function formatReference(value: string | null): string { if (!value) return '—'; if (!/^\d{4}-\d{2}$/.test(value)) return value; const [year, month] = value.split('-'); return `${month}/${year}`; }

export type InvoiceCharge = NonNullable<BillingInvoice['contextualCharges']>[number];
// Boleto da linha: cobrancas canceladas/estornadas nao contam; sem asaasId a emissao ainda esta pendente (nao e boleto).
export function currentBoleto(charges: InvoiceCharge[]): { boleto: InvoiceCharge | null; canMutate: boolean } {
  const active = charges.filter((charge) => charge.asaasStatus !== 'canceled' && charge.asaasStatus !== 'refunded');
  return { boleto: active.filter((charge) => charge.asaasId).sort((a, b) => b.id - a.id)[0] ?? null, canMutate: active.length === 0 };
}
export function boletoBadge(boleto: InvoiceCharge | null): HTMLElement {
  if (!boleto) return createBadge(t('faturas.page.boletoNone'));
  if (boleto.asaasStatus === 'received') return createBadge(t('faturas.page.boletoPaid'), 'success');
  return createBadge(boleto.asaasStatus === 'overdue' ? t('faturas.page.boletoOverdue') : t('faturas.page.boletoAwaiting'), 'warning');
}
export function kwhLabel(value: string | null | undefined): string { return value == null ? '—' : `${Number(value).toLocaleString('pt-BR')} kWh`; }
export function extractionCell(item: BillingInvoice): HTMLElement {
  const cell = createElement('div', { className: 'faturas-extraction-cell' });
  if (!item.problemas.length) { cell.appendChild(createBadge(t('faturas.page.procExtraida'), 'success')); return cell; }
  cell.appendChild(createBadge(t('faturas.page.procErro'), 'danger'));
  item.problemas.forEach((problem) => cell.appendChild(createElement('p', { className: 'faturas-problem', textContent: problem.message })));
  return cell;
}

// Excecao de teste: plataforma admin pode agir como owner so na empresa de testes (id 1).
// Nao afeta nenhuma outra empresa real. Remover/revisar se o fluxo de teste mudar.
const PLATFORM_ADMIN_TEST_EMPRESA_ID = 1;
export function issuingAccess(user: AuthUser | null): { empresaId?: number; canIssue: boolean; isPlatformAdminTestEmpresa: boolean } {
  const empresaId = user?.isPlatformAdmin ? user.platformViewEmpresaId ?? undefined : undefined;
  const isPlatformAdminTestEmpresa = Boolean(user?.isPlatformAdmin && empresaId === PLATFORM_ADMIN_TEST_EMPRESA_ID);
  const canIssue = isPlatformAdminTestEmpresa ||
    (!user?.isPlatformAdmin && ['owner', 'admin', 'financial'].includes(user?.role ?? ''));
  return { empresaId, canIssue, isPlatformAdminTestEmpresa };
}

export const isHttpsUrl = (url: string | null | undefined): url is string => Boolean(url?.startsWith('https://'));

// Link externo seguro: so abre URLs https (retorna null caso contrario).
export function createExternalLink(url: string | null | undefined, label: string, className = 'secondary-button'): HTMLAnchorElement | null {
  if (!isHttpsUrl(url)) return null;
  const link = createElement('a', { className, textContent: label });
  link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
  return link;
}
