// frontend/src/pages/PendenciasPage.ts
import { createElement } from '../dom';
import { createDashboardCards, type DashboardMetric } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createInfoField } from '../components/ClientDetailView';
import { createIcon } from '../components/Icon';
import { createInput, createSelect } from '../components/formFields';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients, type ClientRow } from '../services/clientsService';
import { formattedLogDate, getEntityLogs, type LogRow } from '../services/logsService';
import {
  addComentario,
  cancelarPendencia,
  CATEGORIAS_POR_TIPO,
  createPendencia,
  deletePendencia,
  getPendencias,
  getPendenciaResumo,
  PRIORIDADES,
  prioridadeLabel,
  prioridadeTone,
  reabrirPendencia,
  resolverPendencia,
  statusLabel,
  tipoLabel,
  updatePendencia,
  verificarPendencias,
  vinculacaoLabel,
  type PendenciaPayload,
  type PendenciaPrioridade,
  type PendenciaResumo,
  type PendenciaRow,
  type PendenciaStatus,
  type PendenciaTipo
} from '../services/pendenciasService';
import { addExtraCategoria, getExtraCategorias } from '../services/pendenciaCategoriasService';
import { getPlants, type PlantRow } from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';

export function createPendenciasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let pendencias: PendenciaRow[] = [];
  let resumo: PendenciaResumo = { pendencias: 0, alertas: 0, erros: 0 };
  let clients: ClientRow[] = [];
  let ucs: UcRow[] = [];
  let plants: PlantRow[] = [];
  let categoriaExtras: string[] = [];
  let loadError = false;

  // Agenda navega com uma dica de seleção; a lista ainda busca e autoriza o
  // registro pelo endpoint normal antes de mostrá-lo.
  const requestedId = Number(new URLSearchParams(window.location.search).get('selecionada'));
  let selectedId: number | null = Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : null;
  let tipoFilter: PendenciaTipo | null = null;
  let showAll = false;
  let searchTerm = '';

  const layout = createBaseLayout({
    content,
    eyebrow: 'Automações',
    title: 'Central de ações do HUB — pendências, alertas e erros'
  });

  loadAll();

  return layout;

  let verificacaoEmAndamento = false;

  async function loadAll(): Promise<void> {
    loading.show();
    try {
      const [pendenciasData, resumoData, clientsData, ucsData, plantsData, categoriaExtrasData] = await Promise.all([
        getPendencias(),
        getPendenciaResumo(),
        getClients(),
        getUcs(),
        getPlants(),
        getExtraCategorias()
      ]);
      pendencias = pendenciasData;
      resumo = resumoData;
      clients = clientsData;
      ucs = ucsData;
      plants = plantsData;
      categoriaExtras = categoriaExtrasData;
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Não foi possível carregar pendências. Verifique se o backend está rodando.');
    } finally {
      loading.hide();
      renderContent();
    }

    // Verificacao automatica roda DEPOIS, fora do try/finally do loading
    // global -- nunca acende o overlay e nunca chama loadAll() de novo
    // (isso causava um ciclo show/hide sem fim quando o backend sempre
    // encontrava algo pra criar/resolver, dando a impressao de "carregando
    // pra sempre" no canto superior direito).
    runVerificacaoAutomatica();
  }

  async function runVerificacaoAutomatica(): Promise<void> {
    if (verificacaoEmAndamento) return;
    verificacaoEmAndamento = true;

    try {
      const resultado = await verificarPendencias();

      if (resultado.total_criadas > 0) {
        toast.success(`${resultado.total_criadas} nova(s) pendência(s) criada(s) automaticamente.`);
        await refreshListaSemLoading();
      } else if (resultado.resolvidas > 0) {
        toast.success(`${resultado.resolvidas} pendência(s) resolvida(s) automaticamente.`);
        await refreshListaSemLoading();
      }
    } catch {
      // Silencioso - não mostra erro na verificação automática
    } finally {
      verificacaoEmAndamento = false;
    }
  }

  // Atualiza só pendências + resumo (sem loading global, sem recarregar
  // clientes/UCs/usinas de novo) -- usado depois da verificação automática.
  async function refreshListaSemLoading(): Promise<void> {
    try {
      const [pendenciasData, resumoData] = await Promise.all([getPendencias(), getPendenciaResumo()]);
      pendencias = pendenciasData;
      resumo = resumoData;
    } catch {
      // mantém o que já estava carregado se falhar
    } finally {
      renderContent();
    }
  }

  function getFilteredPendencias(): PendenciaRow[] {
    return pendencias.filter((item) => {
      if (!showAll && item.status !== 'aberta') return false;
      if (tipoFilter && item.tipo !== tipoFilter) return false;

      if (searchTerm) {
        const haystack = normalize(`${item.titulo} ${item.categoria} ${item.origem} ${vinculacaoLabel(item)}`);
        if (!haystack.includes(normalize(searchTerm))) return false;
      }

      return true;
    });
  }

  function renderContent(): void {
    const selected = pendencias.find((item) => item.id === selectedId) ?? null;

    if (!selected) {
      content.replaceChildren(renderListView());
      return;
    }

    const layoutWrap = createElement('div', { className: 'pendencias-layout' });
    layoutWrap.append(renderListView(), renderDetailPanel(selected));
    content.replaceChildren(layoutWrap);
  }

  // Mesmo truque do PlantsPage.ts: toolbar (com o campo de busca) e criada
  // uma vez so, refresh() troca somente os holders de cards/tabela por baixo
  // -- assim o input nunca perde foco enquanto o usuario digita.
  function renderListView(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });
    const toolbar = createElement('div', { className: 'page-actions' });

    const searchInput = createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Pesquisar pendências...';
    searchInput.value = searchTerm;
    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value;
      refresh();
    });

    const toggleAllButton = createElement('button', {
      className: showAll ? 'secondary-button active' : 'secondary-button',
      textContent: showAll ? 'Mostrando: todas' : 'Mostrando: abertas',
      type: 'button'
    });
    toggleAllButton.addEventListener('click', () => {
      showAll = !showAll;
      refresh();
    });

    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';

    // Botao de verificacao automatica
    const verifyButton = createElement('button', {
      className: 'secondary-button button-with-icon',
      type: 'button',
      title: 'Verificar agora'
    });
    verifyButton.append(createIcon('refresh'), document.createTextNode('Verificar agora'));
    verifyButton.addEventListener('click', async () => {
      verifyButton.disabled = true;
      verifyButton.textContent = 'Verificando...';
      try {
        const resultado = await verificarPendencias();
        if (resultado.total_criadas > 0) {
          toast.success(`${resultado.total_criadas} nova(s) pendência(s) criada(s) automaticamente.`);
        } else if (resultado.resolvidas > 0) {
          toast.success(`${resultado.resolvidas} pendência(s) resolvida(s) automaticamente.`);
        } else {
          toast.success('Nenhuma nova pendência encontrada.');
        }
        await loadAll();
      } catch {
        toast.error('Erro ao executar verificação automática.');
      } finally {
        verifyButton.disabled = false;
        verifyButton.innerHTML = '';
        verifyButton.append(createIcon('refresh'), document.createTextNode('Verificar agora'));
      }
    });

    const newButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newButton.append(createIcon('plus'), document.createTextNode('Nova Pendência'));
    newButton.addEventListener('click', () => openPendenciaEditor(null));

    toolbar.append(searchInput, toggleAllButton, spacer, verifyButton, newButton);

    const statsHolder = createElement('div');
    const tableHolder = createElement('div');

    function refresh(): void {
      statsHolder.replaceChildren(createStatCards());
      tableHolder.replaceChildren(createPendenciasTable());
    }

    refresh();
    fragment.append(toolbar, statsHolder, tableHolder);
    return fragment;

    function createStatCards(): HTMLElement {
      const metrics: DashboardMetric[] = [
        {
          label: 'Pendências',
          value: String(resumo.pendencias),
          tone: 'warning',
          icon: 'pending',
          active: tipoFilter === 'pendencia',
          onClick: () => {
            tipoFilter = tipoFilter === 'pendencia' ? null : 'pendencia';
            refresh();
          }
        },
        {
          label: 'Alertas',
          value: String(resumo.alertas),
          tone: 'warning',
          icon: 'cobrancas',
          active: tipoFilter === 'alerta',
          onClick: () => {
            tipoFilter = tipoFilter === 'alerta' ? null : 'alerta';
            refresh();
          }
        },
        {
          label: 'Erros',
          value: String(resumo.erros),
          tone: 'danger',
          icon: 'x',
          active: tipoFilter === 'erro',
          onClick: () => {
            tipoFilter = tipoFilter === 'erro' ? null : 'erro';
            refresh();
          }
        }
      ];

      return createDashboardCards(metrics);
    }

    function createPendenciasTable(): HTMLElement {
      const rows = getFilteredPendencias();
      const isFiltered = Boolean(searchTerm || tipoFilter);

      return createDataTable<PendenciaRow>({
        title: 'Fila de itens',
        eyebrow: 'Listagem',
        rows,
        emptyMessage: loadError
          ? 'Não foi possível carregar pendências.'
          : isFiltered
            ? 'Nenhum item encontrado para esse filtro.'
            : showAll
              ? 'Nenhum item cadastrado ainda.'
              : 'Nenhuma pendência aberta. Tudo em dia!',
        onRowClick: (item) => {
          selectedId = item.id;
          renderContent();
        },
        columns: [
          { key: 'tipo', label: 'Tipo', render: (item) => createTipoBadge(item.tipo) },
          { key: 'titulo', label: 'Pendência' },
          { key: 'categoria', label: 'Categoria' },
          { key: 'origem', label: 'Origem' },
          { key: 'vinculacao', label: 'Vinculação', render: (item) => vinculacaoLabel(item) },
          { key: 'prazo', label: 'Prazo', render: (item) => formatDate(item.prazo) },
          { key: 'prioridade', label: 'Prioridade', render: (item) => createPrioridadeBadge(item.prioridade) },
          { key: 'status', label: 'Status', render: (item) => createStatusDot(item.status) }
        ]
      });
    }
  }

  function renderDetailPanel(pendencia: PendenciaRow): HTMLElement {
    const panel = createElement('aside', { className: 'pendencia-detail-panel' });

    const header = createElement('div', { className: 'pendencia-detail-header' });
    const titleRow = createElement('div', { className: 'pendencia-detail-title-row' });
    const heading = createElement('h2', { textContent: pendencia.titulo });
    const closeButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    closeButton.appendChild(createIcon('x'));
    closeButton.title = 'Fechar';
    closeButton.addEventListener('click', () => {
      selectedId = null;
      renderContent();
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
      infoGrid,
      createDetailsSection(pendencia),
      createDetailActions(pendencia),
      createCommentsSection(pendencia),
      createTimelineSection(pendencia)
    );

    return panel;
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

  function createDetailActions(pendencia: PendenciaRow): HTMLElement {
    const wrap = createElement('div', { className: 'pendencia-detail-actions' });

    if (pendencia.status === 'aberta') {
      const resolveButton = createElement('button', { className: 'button-with-icon', type: 'button' });
      resolveButton.append(createIcon('check'), document.createTextNode('Resolver'));
      resolveButton.addEventListener('click', () => runAction(() => resolverPendencia(pendencia.id), 'Pendência resolvida.'));

      const cancelButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
      cancelButton.append(createIcon('x'), document.createTextNode('Cancelar'));
      cancelButton.addEventListener('click', () => runAction(() => cancelarPendencia(pendencia.id), 'Pendência cancelada.'));

      wrap.append(resolveButton, cancelButton);
    } else {
      const reopenButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
      reopenButton.append(createIcon('pending'), document.createTextNode('Reabrir'));
      reopenButton.addEventListener('click', () => runAction(() => reabrirPendencia(pendencia.id), 'Pendência reaberta.'));
      wrap.append(reopenButton);
    }

    // Editar so faz sentido pra quem foi criado na mao -- alerta/erro sao
    // gerados pelo sistema (ver pendencia_service.py), editar o conteudo
    // deles aqui ia confundir a fonte da verdade.
    if (pendencia.tipo === 'pendencia') {
      const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
      editButton.append(createIcon('edit'), document.createTextNode('Editar'));
      editButton.addEventListener('click', () => openPendenciaEditor(pendencia));
      wrap.append(editButton);
    }

    const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
    deleteButton.append(createIcon('trash'), document.createTextNode('Excluir'));
    deleteButton.addEventListener('click', () => handleDelete(pendencia));
    wrap.append(deleteButton);

    return wrap;
  }

  async function runAction(action: () => Promise<unknown>, successMessage: string): Promise<void> {
    loading.show();
    try {
      await action();
      toast.success(successMessage);
      await loadAll();
    } catch {
      toast.error('Não foi possível concluir a ação.');
    } finally {
      loading.hide();
    }
  }

  async function handleDelete(pendencia: PendenciaRow): Promise<void> {
    const confirmed = window.confirm(`Excluir "${pendencia.titulo}"? Essa ação não pode ser desfeita.`);
    if (!confirmed) return;

    loading.show();
    try {
      await deletePendencia(pendencia.id);
      toast.success('Excluída.');
      if (selectedId === pendencia.id) selectedId = null;
      await loadAll();
    } catch {
      toast.error('Não foi possível excluir.');
    } finally {
      loading.hide();
    }
  }

  function createCommentsSection(pendencia: PendenciaRow): HTMLElement {
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
        await loadAll();
      } catch {
        toast.error('Não foi possível comentar.');
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

  // Select de categoria + botao "+ categoria" -- mesmo espirito do
  // CategoryPicker.ts (usado em Documentos), mas Pendencia nao tem model de
  // categoria proprio: as extras ficam em Setting (ver
  // pendenciaCategoriasService.ts). Nao fecha o modal, so atualiza a lista
  // na hora -- a categoria recem-criada ja fica selecionada.
  function createCategoriaField(selected: string): { field: HTMLElement; select: HTMLSelectElement } {
    const field = createElement('label', { className: 'form-field' });
    const text = createElement('span', { textContent: 'Categoria' });
    const row = createElement('div', { className: 'select-with-button' });
    const select = createElement('select');
    const addButton = createElement('button', { className: 'secondary-button', textContent: '+ categoria', type: 'button' });

    function renderOptions(value: string): void {
      const todas = [...CATEGORIAS_POR_TIPO.pendencia, ...categoriaExtras.filter((item) => !CATEGORIAS_POR_TIPO.pendencia.includes(item))];
      select.replaceChildren();
      todas.forEach((nome) => {
        const option = createElement('option', { textContent: nome });
        option.value = nome;
        select.appendChild(option);
      });
      select.value = todas.includes(value) ? value : todas[0];
    }

    addButton.addEventListener('click', async () => {
      const nome = window.prompt('Nome da nova categoria de pendência (ex: Idade, Contrato...):');
      if (!nome || !nome.trim()) return;

      addButton.disabled = true;
      try {
        categoriaExtras = await addExtraCategoria(nome.trim(), categoriaExtras);
        renderOptions(nome.trim());
      } catch {
        toast.error('Não foi possível salvar a nova categoria.');
      } finally {
        addButton.disabled = false;
      }
    });

    renderOptions(selected);
    row.append(select, addButton);
    field.append(text, row);
    return { field, select };
  }

  function openPendenciaEditor(pendencia: PendenciaRow | null): void {
    const overlay = createElement('section', { className: 'modal-overlay' });
    const panel = createElement('article', { className: 'plant-card' });
    const form = createElement('form', { className: 'client-form' });
    const header = createElement('div', { className: 'form-header' });
    const titleText = createElement('div');
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: pendencia ? 'Pendência' : 'Nova pendência' });
    const heading = createElement('h2', { textContent: pendencia ? pendencia.titulo : 'Cadastrar pendência' });
    const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });
    const fields = createElement('div', { className: 'form-grid' });

    const titulo = createInput('Título', 'text', pendencia?.titulo ?? '', true);
    const categoria = createCategoriaField(pendencia?.categoria ?? CATEGORIAS_POR_TIPO.pendencia[0]);
    const prioridade = createSelect('Prioridade', pendencia?.prioridade ?? 'media', PRIORIDADES);
    const prazo = createInput('Prazo', 'datetime-local', pendencia?.prazo ? pendencia.prazo.slice(0, 16) : '', false);

    const descricao = createElement('label', { className: 'form-field form-field-wide' });
    const descricaoLabel = createElement('span', { textContent: 'Descrição' });
    const descricaoInput = createElement('textarea');
    descricaoInput.rows = 3;
    descricaoInput.value = pendencia?.descricao ?? '';
    descricao.append(descricaoLabel, descricaoInput);

    const clienteField = createVinculacaoSelect('Cliente (opcional)', clients.map((item) => ({ id: item.id, label: item.nome })), pendencia?.clienteId ?? null);
    const ucField = createVinculacaoSelect('UC (opcional)', ucs.map((item) => ({ id: item.id, label: item.codigo })), pendencia?.ucId ?? null);
    const usinaField = createVinculacaoSelect('Usina (opcional)', plants.map((item) => ({ id: item.id, label: item.nome })), pendencia?.usinaId ?? null);

    const actions = createElement('div', { className: 'form-actions' });
    const saveButton = createElement('button', { textContent: 'Salvar pendência', type: 'submit' });

    titleText.append(eyebrow, heading);
    header.append(titleText, closeButton);
    fields.append(
      titulo.field,
      categoria.field,
      prioridade.field,
      prazo.field,
      descricao,
      clienteField.field,
      ucField.field,
      usinaField.field
    );
    actions.appendChild(saveButton);

    closeButton.addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) overlay.remove();
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      if (!titulo.input.value.trim()) {
        titulo.input.reportValidity();
        return;
      }

      saveButton.disabled = true;
      saveButton.textContent = 'Salvando...';

      const payload: PendenciaPayload = {
        titulo: titulo.input.value.trim(),
        categoria: categoria.select.value,
        descricao: descricaoInput.value.trim(),
        clienteId: clienteField.select.value ? Number(clienteField.select.value) : null,
        ucId: ucField.select.value ? Number(ucField.select.value) : null,
        usinaId: usinaField.select.value ? Number(usinaField.select.value) : null,
        prazo: prazo.input.value,
        prioridade: prioridade.select.value as PendenciaPrioridade
      };

      loading.show();
      try {
        if (pendencia) {
          await updatePendencia(pendencia.id, payload);
          toast.success('Pendência atualizada.');
        } else {
          await createPendencia(payload);
          toast.success('Pendência criada.');
        }
        overlay.remove();
        await loadAll();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a pendência.');
      } finally {
        loading.hide();
        saveButton.disabled = false;
        saveButton.textContent = 'Salvar pendência';
      }
    });

    form.append(header, fields, actions);
    panel.appendChild(form);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }
}

function createVinculacaoSelect(label: string, options: Array<{ id: number; label: string }>, selectedId: number | null) {
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

function createTipoBadge(tipo: PendenciaTipo): HTMLElement {
  const tone = tipo === 'erro' ? 'danger' : tipo === 'alerta' ? 'warning' : 'info';
  return createElement('span', { className: `status-badge tone-${tone}`, textContent: tipoLabel(tipo) });
}

function createPrioridadeBadge(prioridade: PendenciaPrioridade): HTMLElement {
  const tone = prioridadeTone(prioridade);
  const className = tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`;
  return createElement('span', { className, textContent: prioridadeLabel(prioridade) });
}

function createStatusBadge(status: PendenciaStatus): HTMLElement {
  const tone = status === 'aberta' ? 'warning' : status === 'resolvida' ? 'success' : 'neutral';
  const className = tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`;
  return createElement('span', { className, textContent: statusLabel(status) });
}

function createStatusDot(status: PendenciaStatus): HTMLElement {
  const tone = status === 'aberta' ? 'warning' : status === 'resolvida' ? 'success' : 'neutral';
  const wrap = createElement('span', { className: 'status-dot-label' });
  wrap.append(
    createElement('span', { className: `status-dot status-${tone}` }),
    createElement('span', { textContent: statusLabel(status) })
  );
  return wrap;
}

function formatDate(value: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

// "erroRetornado" -> "Erro retornado". Generico de proposito -- nao sabemos
// hoje quais chaves o backend vai mandar em metadados quando a Sprint 2
// (alertas/erros automaticos) for implementada.
function detailsLabel(key: string): string {
  const spaced = key.replace(/([a-z])([A-Z])/g, '$1 $2');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function formatDetailsValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
