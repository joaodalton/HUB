import { createElement } from '../dom';
import type { FaturaRow } from '../services/faturasService';
import { t } from '../services/i18nService';
import { createModalShell } from './Modal';
import { createStatusBadge, type StatusTone } from './StatusBadge';
export { formatDate } from '../utils/date';

export function createModal(title: string, eyebrow: string, onClose?: () => void): HTMLElement {
  const { overlay, dialog } = createModalShell(title, eyebrow, onClose);
  dialog.classList.add('fatura-modal');
  document.body.appendChild(overlay);
  return overlay;
}

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
export function selectField(label: string, options: Array<{ value: string; label: string }>, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const select = createElement('select'); select.required = required;
  select.append(...options.map((item) => option(item.value, item.label)));
  field.append(createElement('span', { textContent: label }), select);
  return { field, select };
}
export function textField(label: string, type: string, value: string, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const input = createElement('input'); input.type = type; input.value = value; input.required = required;
  field.append(createElement('span', { textContent: label }), input);
  return { field, input };
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
export function createChargeCell(charges: Array<{ asaasId: string | null; asaasStatus: FaturaRow['asaasStatus']; statusInterno: string | null }>): HTMLElement {
  if (!charges.length) return createBadge(t('faturas.status.semCobranca'));
  const wrap = createElement('div', { className: 'fatura-charge-cell' });
  charges.forEach((charge) => wrap.appendChild(createBadge(charge.asaasId ? statusLabel(charge.asaasStatus) : charge.statusInterno ?? t('faturas.page.awaitingIssuance'), charge.asaasStatus === 'received' && charge.asaasId ? 'success' : charge.asaasStatus === 'overdue' && charge.asaasId ? 'danger' : 'warning')));
  return wrap;
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
export function currentMonth(): string { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`; }
