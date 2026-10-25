// frontend/src/pages/pendencias/shared.ts
// Helpers puros (sem estado) e tipos compartilhados entre os modulos da pagina de Pendencias.
import { createElement } from '../../dom';
import { createStatusBadge as createSharedStatusBadge, type StatusTone } from '../../components/StatusBadge';
import { useGlobalLoading } from '../../hooks/useGlobalLoading';
import { useToast } from '../../hooks/useToast';
import type { ClientRow } from '../../services/clientsService';
import {
  prioridadeLabel,
  prioridadeTone,
  statusLabel,
  tipoLabel,
  type PendenciaPrioridade,
  type PendenciaResumo,
  type PendenciaRow,
  type PendenciaStatus,
  type PendenciaTipo
} from '../../services/pendenciasService';
import type { PlantRow } from '../../services/plantService';
import type { UcRow } from '../../services/ucsService';
import { formatDateTime } from '../../utils/date';
// Reexportados para os demais modulos nao precisarem importar diretamente dos services.
export type { ClientRow, PlantRow, UcRow };

export const PAGE_SIZE = 25;

export function formatDate(value: string | null): string {
  return formatDateTime(value, '-');
}

// Estado mutavel compartilhado entre lista, painel de detalhe e editor --
// mesma referencia de objeto, atualizada no lugar (sem recriar) para que as
// closures de cada modulo sempre leiam o valor atual.
export interface PendenciasState {
  pendencias: PendenciaRow[];
  resumo: PendenciaResumo;
  clients: ClientRow[];
  ucs: UcRow[];
  plants: PlantRow[];
  categoriaExtras: string[];
  loadError: boolean;
  isLoading: boolean;
  selectedId: number | null;
  tipoFilter: PendenciaTipo | null;
  showAll: boolean;
  searchTerm: string;
  page: number;
}

export interface PendenciasContext {
  state: PendenciasState;
  toast: ReturnType<typeof useToast>;
  loading: ReturnType<typeof useGlobalLoading>;
  loadAll: () => Promise<void>;
  renderContent: () => void;
  openPendenciaEditor: (pendencia: PendenciaRow | null) => void;
}

export function createTipoBadge(tipo: PendenciaTipo): HTMLElement {
  const tone = tipo === 'erro' ? 'danger' : tipo === 'alerta' ? 'warning' : 'info';
  return createSharedStatusBadge(tipoLabel(tipo), tone);
}

export function createPrioridadeBadge(prioridade: PendenciaPrioridade): HTMLElement {
  const tone = prioridadeTone(prioridade);
  return createSharedStatusBadge(prioridadeLabel(prioridade), tone as StatusTone);
}

export function createStatusBadge(status: PendenciaStatus): HTMLElement {
  const tone = status === 'aberta' ? 'warning' : status === 'resolvida' ? 'success' : 'neutral';
  return createSharedStatusBadge(statusLabel(status), tone);
}

export function createStatusDot(status: PendenciaStatus): HTMLElement {
  const tone = status === 'aberta' ? 'warning' : status === 'resolvida' ? 'success' : 'neutral';
  return createSharedStatusBadge(statusLabel(status), tone);
}

export function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

export function compareOperationalPriority(a: PendenciaRow, b: PendenciaRow): number {
  const priority: Record<PendenciaPrioridade, number> = { critica: 0, alta: 1, media: 2, baixa: 3 };
  const statusRank = (item: PendenciaRow): number => item.status === 'aberta' ? 0 : 1;
  return statusRank(a) - statusRank(b) || priority[a.prioridade] - priority[b.prioridade] || deadline(a) - deadline(b) || a.id - b.id;
}

function deadline(item: PendenciaRow): number { return item.prazo ? new Date(item.prazo).getTime() : Number.MAX_SAFE_INTEGER; }

export function attentionKind(item: PendenciaRow): { label: string; tone: StatusTone } {
  if (item.tipo === 'erro' || item.prioridade === 'critica' || item.prioridade === 'alta') return { label: 'Precisa de ação', tone: 'danger' };
  const text = normalize(`${item.titulo} ${item.descricao ?? ''} ${item.origem}`);
  if (text.includes('falt') || text.includes('aguard') || text.includes('sem ')) return { label: 'Aguardando informação', tone: 'warning' };
  return { label: 'Informativa', tone: 'info' };
}

export function createAttentionBadge(item: PendenciaRow): HTMLElement {
  const kind = attentionKind(item);
  return createSharedStatusBadge(kind.label, kind.tone);
}

export function contextualDestination(item: PendenciaRow): { label: string; path: string } | null {
  if (item.faturaId) return { label: 'Abrir faturas', path: `/faturas?selecionada=${item.faturaId}` };
  if (item.ucId) return { label: 'Abrir UC', path: `/ucs?selecionada=${item.ucId}` };
  if (item.usinaId) return { label: 'Abrir usina', path: `/usinas?selecionada=${item.usinaId}` };
  if (item.clienteId) return { label: 'Abrir cliente', path: `/clientes?selecionada=${item.clienteId}` };
  if (item.documentoId) return { label: 'Abrir documentos', path: '/documentos' };
  return null;
}

export function navigateTo(path: string): void { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); }

// "erroRetornado" -> "Erro retornado". Generico de proposito -- nao sabemos
// hoje quais chaves o backend vai mandar em metadados quando a Sprint 2
// (alertas/erros automaticos) for implementada.
export function detailsLabel(key: string): string {
  const spaced = key.replace(/([a-z])([A-Z])/g, '$1 $2');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function formatDetailsValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function createVinculacaoSelect(label: string, options: Array<{ id: number; label: string }>, selectedId: number | null) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const select = createElement('select');
  const placeholder = createElement('option', { textContent: 'Nenhum' });

  placeholder.value = '';
  select.appendChild(placeholder);

  options.forEach((option) => {
    const optionElement = createElement('option', { textContent: option.label });
    optionElement.value = String(option.id);
    select.appendChild(optionElement);
  });

  select.value = selectedId ? String(selectedId) : '';
  field.append(text, select);
  return { field, select };
}
