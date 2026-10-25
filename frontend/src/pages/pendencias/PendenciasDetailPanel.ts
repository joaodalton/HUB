// frontend/src/pages/pendencias/PendenciasDetailPanel.ts
import { createElement } from '../../dom';
import { createInfoField } from '../../components/ClientDetailView';
import { createIcon } from '../../components/Icon';
import { formattedLogDate, getEntityLogs, type LogRow } from '../../services/logsService';
import {
  addComentario,
  cancelarPendencia,
  deletePendencia,
  reabrirPendencia,
  resolverPendencia,
  vinculacaoLabel,
  type PendenciaRow
} from '../../services/pendenciasService';
import { writeListState } from '../../services/listState';
import {
  contextualDestination,
  createAttentionBadge,
  createPrioridadeBadge,
  createStatusBadge,
  createTipoBadge,
  detailsLabel,
  formatDate,
  formatDetailsValue,
  navigateTo,
  type PendenciasContext
} from './shared';

export function renderDetailPanel(ctx: PendenciasContext, pendencia: PendenciaRow): HTMLElement {
  const panel = createElement('aside', { className: 'pendencia-detail-panel' });

  const header = createElement('div', { className: 'pendencia-detail-header' });
  const titleRow = createElement('div', { className: 'pendencia-detail-title-row' });
  const heading = createElement('h2', { textContent: pendencia.titulo });
  const closeButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
  closeButton.appendChild(createIcon('x'));
  closeButton.title = 'Fechar';
  closeButton.addEventListener('click', () => {
    ctx.state.selectedId = null; writeListState({ selecionada: null }, 'replace');
    ctx.renderContent();
  });

  const badgesRow = createElement('div', { className: 'pendencia-detail-badges' });
  badgesRow.append(
    createTipoBadge(pendencia.tipo),
    createPrioridadeBadge(pendencia.prioridade),
    createStatusBadge(pendencia.status)
  );

  titleRow.append(heading, closeButton);
  header.append(titleRow, badgesRow);

  const description = createElement('p', {
    className: 'pendencia-detail-description',
    textContent: pendencia.descricao || 'Sem descrição.'
  });

  const infoGrid = createElement('div', { className: 'detail-info-grid' });
  infoGrid.append(
    createInfoField('Categoria', pendencia.categoria),
    createInfoField('Origem', pendencia.origem),
    createInfoField('Vinculação', vinculacaoLabel(pendencia)),
    createInfoField('Prazo', formatDate(pendencia.prazo)),
    createInfoField('Responsável', pendencia.responsavelNome ?? 'Não definido'),
    createInfoField('Criada em', formatDate(pendencia.criadoEm))
  );

  panel.append(
    header,
    description,
    createNextAction(pendencia),
    infoGrid,
    createDetailsSection(pendencia),
    createDetailActions(ctx, pendencia),
    createCommentsSection(ctx, pendencia),
    createTimelineSection(pendencia)
  );

  return panel;
}

function createNextAction(pendencia: PendenciaRow): HTMLElement {
  const section = createElement('div', { className: 'pendencia-next-action' });
  const destination = contextualDestination(pendencia);
  section.append(
    createAttentionBadge(pendencia),
    createElement('span', { textContent: destination ? 'Próxima ação: revisar o registro vinculado.' : 'Sem ação contextual: nenhum registro navegável está vinculado.' })
  );
  if (destination) {
    const link = createElement('a', { className: 'secondary-button', textContent: destination.label });
    link.href = destination.path;
    link.addEventListener('click', event => { event.preventDefault(); navigateTo(destination.path); });
    section.appendChild(link);
  }
  return section;
}

// Le pendencia.metadados (JSON livre, ja existe no model/banco -- ver
// Pendencia.metadados em backend/models/pendencia.py) e mostra qualquer
// chave que vier ali, sem hardcode. Quando a Sprint 2 (alerta/erro
// automatico) comecar a popular esse campo (ex.: tentativas,
// ultimaTentativa, erroRetornado), essa secao ja funciona sem precisar
// tocar no frontend de novo -- so o backend passa a mandar o JSON.
function createDetailsSection(pendencia: PendenciaRow): HTMLElement {
  const section = createElement('div', { className: 'pendencia-detail-section' });
  const title = createElement('span', { className: 'pendencia-detail-section-title', textContent: 'Detalhes' });
  section.appendChild(title);

  const entries = pendencia.metadados ? Object.entries(pendencia.metadados) : [];

  if (entries.length === 0) {
    section.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: 'Nenhum detalhe adicional registrado ainda.'
    }));
    return section;
  }

  const grid = createElement('div', { className: 'detail-info-grid' });
  entries.forEach(([key, value]) => {
    grid.appendChild(createInfoField(detailsLabel(key), formatDetailsValue(value)));
  });
  section.appendChild(grid);

  return section;
}

function createDetailActions(ctx: PendenciasContext, pendencia: PendenciaRow): HTMLElement {
  const wrap = createElement('div', { className: 'pendencia-detail-actions' });

  if (pendencia.status === 'aberta') {
    const resolveButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    resolveButton.append(createIcon('check'), document.createTextNode('Resolver'));
    resolveButton.addEventListener('click', () => runAction(ctx, () => resolverPendencia(pendencia.id), 'Pendência resolvida.'));

    const cancelButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    cancelButton.append(createIcon('x'), document.createTextNode('Cancelar'));
    cancelButton.addEventListener('click', () => runAction(ctx, () => cancelarPendencia(pendencia.id), 'Pendência cancelada.'));

    wrap.append(resolveButton, cancelButton);
  } else {
    const reopenButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    reopenButton.append(createIcon('pending'), document.createTextNode('Reabrir'));
    reopenButton.addEventListener('click', () => runAction(ctx, () => reabrirPendencia(pendencia.id), 'Pendência reaberta.'));
    wrap.append(reopenButton);
  }

  // Editar so faz sentido pra quem foi criado na mao -- alerta/erro sao
  // gerados pelo sistema (ver pendencia_service.py), editar o conteudo
  // deles aqui ia confundir a fonte da verdade.
  if (pendencia.tipo === 'pendencia') {
    const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    editButton.append(createIcon('edit'), document.createTextNode('Editar'));
    editButton.addEventListener('click', () => ctx.openPendenciaEditor(pendencia));
    wrap.append(editButton);
  }

  const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
  deleteButton.append(createIcon('trash'), document.createTextNode('Excluir'));
  deleteButton.addEventListener('click', () => handleDelete(ctx, pendencia));
  wrap.append(deleteButton);

  return wrap;
}

async function runAction(ctx: PendenciasContext, action: () => Promise<unknown>, successMessage: string): Promise<void> {
  ctx.loading.show();
  try {
    await action();
    ctx.toast.success(successMessage);
    await ctx.loadAll();
  } catch {
    ctx.toast.error('Não foi possível concluir a ação.');
  } finally {
    ctx.loading.hide();
  }
}

async function handleDelete(ctx: PendenciasContext, pendencia: PendenciaRow): Promise<void> {
  const confirmed = window.confirm(`Excluir "${pendencia.titulo}"? Essa ação não pode ser desfeita.`);
  if (!confirmed) return;

  ctx.loading.show();
  try {
    await deletePendencia(pendencia.id);
    ctx.toast.success('Excluída.');
    if (ctx.state.selectedId === pendencia.id) ctx.state.selectedId = null;
    await ctx.loadAll();
  } catch {
    ctx.toast.error('Não foi possível excluir.');
  } finally {
    ctx.loading.hide();
  }
}

function createCommentsSection(ctx: PendenciasContext, pendencia: PendenciaRow): HTMLElement {
  const section = createElement('div', { className: 'pendencia-detail-section' });
  const title = createElement('span', {
    className: 'pendencia-detail-section-title',
    textContent: `Comentários (${pendencia.comentarios.length})`
  });
  const list = createElement('div', { className: 'pendencia-comments-list' });

  if (pendencia.comentarios.length === 0) {
    list.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhum comentário ainda.' }));
  } else {
    pendencia.comentarios.forEach((comentario) => {
      const row = createElement('div', { className: 'pendencia-comment-row' });
      const meta = createElement('div', { className: 'pendencia-comment-meta' });
      meta.append(
        createElement('strong', { textContent: comentario.autorNome ?? 'Usuário' }),
        createElement('span', { textContent: comentario.criadoEm ? new Date(comentario.criadoEm).toLocaleString('pt-BR') : '' })
      );
      const text = createElement('p', { textContent: comentario.texto });
      row.append(meta, text);
      list.appendChild(row);
    });
  }

  const form = createElement('form', { className: 'pendencia-comment-form' });
  const textarea = createElement('textarea');
  textarea.placeholder = 'Escrever um comentário...';
  textarea.rows = 2;
  const sendButton = createElement('button', { textContent: 'Comentar', type: 'submit' });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const texto = textarea.value.trim();
    if (!texto) return;

    sendButton.disabled = true;
    try {
      await addComentario(pendencia.id, texto);
      await ctx.loadAll();
    } catch {
      ctx.toast.error('Não foi possível comentar.');
    } finally {
      sendButton.disabled = false;
    }
  });

  form.append(textarea, sendButton);
  section.append(title, list, form);
  return section;
}

function createTimelineSection(pendencia: PendenciaRow): HTMLElement {
  const section = createElement('div', { className: 'pendencia-detail-section' });
  const title = createElement('span', { className: 'pendencia-detail-section-title', textContent: 'Histórico' });
  const list = createElement('div', { className: 'pendencia-timeline' });
  list.appendChild(createElement('small', { textContent: 'Carregando histórico...' }));

  section.append(title, list);

  getEntityLogs('Pendencia', pendencia.id)
    .then((logs) => renderTimeline(list, logs))
    .catch(() => {
      list.replaceChildren(createElement('small', { textContent: 'Não foi possível carregar o histórico.' }));
    });

  return section;
}

function renderTimeline(container: HTMLElement, logs: LogRow[]): void {
  container.replaceChildren();

  if (logs.length === 0) {
    container.appendChild(createElement('small', { textContent: 'Sem eventos registrados.' }));
    return;
  }

  logs.forEach((log) => {
    const row = createElement('div', { className: 'pendencia-timeline-row' });
    const dot = createElement('span', { className: 'pendencia-timeline-dot' });
    const text = createElement('div');
    text.append(
      createElement('span', { textContent: log.mensagem ?? log.acao }),
      createElement('small', { textContent: formattedLogDate(log) })
    );
    row.append(dot, text);
    container.appendChild(row);
  });
}
