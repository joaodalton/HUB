import { createElement, statusTone } from '../dom';
import { createClientDocumentsPanel } from './ClientDocumentsPanel';
import type { ClientRow, ClientUc } from '../services/clientsService';

type ClientDetailViewOptions = {
  client: ClientRow;
  onBack: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

// Abas sem backend ainda (Financeiro = V3.0, Agenda real = V1.5, Historico/Observacoes/Logs
// nem tem model hoje) -- visiveis mas desabilitadas, so como referencia visual.
const upcomingTabs = ['Financeiro', 'Histórico', 'Agenda', 'Observações', 'Logs'];

export function createClientDetailView({ client, onBack, onEdit, onDelete }: ClientDetailViewOptions): HTMLElement {
  const wrapper = createElement('section', { className: 'client-detail-view' });

  const backLink = createElement('a', { className: 'detail-back-link', textContent: '\u2190 Clientes' });
  backLink.href = '#';
  backLink.addEventListener('click', (event) => {
    event.preventDefault();
    onBack();
  });

  const columns = createElement('div', { className: 'detail-columns' });
  // "+ Nova UC" reaproveita o modal de edicao (que ja sabe adicionar UC) em vez
  // de construir um fluxo novo so pra isso.
  columns.append(createInfoPanel(client), createUcSection(client, onEdit));

  wrapper.append(backLink, createHeader(client, onEdit, onDelete), columns, createTabsPanel(client));

  return wrapper;
}

function createHeader(client: ClientRow, onEdit: () => void, onDelete: () => void): HTMLElement {
  const header = createElement('div', { className: 'detail-header' });
  const titleRow = createElement('div', { className: 'detail-title-row' });
  const heading = createElement('h2', { textContent: client.nome });
  const badge = createElement('span', {
    className: `client-status-badge status-${statusTone(client.status)}`,
    textContent: client.status
  });
  const actions = createElement('div', { className: 'detail-actions' });
  const editButton = createElement('button', { className: 'secondary-button', textContent: 'Editar', type: 'button' });
  const deleteButton = createElement('button', { className: 'danger-button', textContent: 'Excluir', type: 'button' });

  editButton.addEventListener('click', onEdit);
  deleteButton.addEventListener('click', onDelete);

  titleRow.append(heading, badge);
  actions.append(editButton, deleteButton);
  header.append(titleRow, actions);

  return header;
}

function createInfoPanel(client: ClientRow): HTMLElement {
  const panel = createElement('aside', { className: 'detail-info-panel' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Informações gerais' });
  const grid = createElement('div', { className: 'detail-info-grid' });

  grid.append(
    createInfoField('ID', String(client.id)),
    createInfoField('CPF', client.cpf),
    createInfoField('Telefone', client.telefone || 'Não informado'),
    createInfoField('Email', client.email),
    createInfoField('Concessionária', client.concessionaria),
    createInfoField('Data de nascimento', 'Não configurado')
  );

  panel.append(eyebrow, grid);
  return panel;
}

function createUcSection(client: ClientRow, onAddUc: () => void): HTMLElement {
  const section = createElement('aside', { className: 'detail-uc-section' });
  const header = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'UCs' });
  const heading = createElement('h2', { textContent: `Unidades consumidoras (${client.ucs.length})` });
  const addButton = createElement('button', { className: 'small-button', textContent: '+ Nova UC', type: 'button' });

  addButton.addEventListener('click', onAddUc);
  titleText.append(eyebrow, heading);
  header.append(titleText, addButton);
  section.appendChild(header);

  if (client.ucs.length === 0) {
    section.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: 'Nenhuma UC vinculada ainda.'
    }));
    return section;
  }

  const list = createElement('div', { className: 'uc-editor-list' });
  client.ucs.forEach((uc) => list.appendChild(createUcViewCard(uc)));
  section.appendChild(list);

  return section;
}

// Reaproveita as mesmas classes CSS do accordion de edicao (ClientCard.ts) --
// mesmo componente visual, so que so-leitura (details/summary nativo).
function createUcViewCard(uc: ClientUc): HTMLElement {
  const isConnected = uc.conexoes.length > 0;
  const card = createElement('details', { className: 'uc-editor-card' });
  const summary = createElement('summary', { className: 'uc-summary' });
  const titleGroup = createElement('div', { className: 'uc-summary-title' });

  titleGroup.append(
    createElement('strong', { textContent: uc.codigo || 'UC sem código' }),
    createElement('span', { textContent: uc.apelido || 'Mais informações' })
  );

  summary.append(
    titleGroup,
    createElement('span', {
      className: `client-status-badge status-${isConnected ? 'success' : 'warning'}`,
      textContent: isConnected ? 'Ativa' : 'Sem usina'
    })
  );

  const body = createElement('div', { className: 'uc-editor-body' });
  const grid = createElement('div', { className: 'uc-editor-grid' });

  grid.append(
    createInfoField('Consumo', uc.consumo || '-'),
    createInfoField('Tarifa', uc.baseTarifaria),
    createInfoField('Desconto', uc.desconto || '-'),
    createInfoField('Ligação', uc.tipoLigacao),
    createInfoField('Usina conectada', isConnected ? uc.conexoes.map((conexao) => conexao.usina).join(', ') : 'Nenhuma')
  );

  body.appendChild(grid);
  card.append(summary, body);

  return card;
}

// Exportado -- PlantsPage.ts reaproveita pro mesmo padrao label/valor no
// painel de informacoes da Usina, em vez de duplicar essa funcao.
export function createInfoField(label: string, value: string): HTMLElement {
  const field = createElement('div', { className: 'detail-info-field' });
  field.append(
    createElement('span', { className: 'detail-info-label', textContent: label }),
    createElement('span', { className: 'detail-info-value', textContent: value })
  );
  return field;
}

function createTabsPanel(client: ClientRow): HTMLElement {
  const panel = createElement('section', { className: 'detail-tabs-panel' });
  const tabs = createElement('div', { className: 'detail-tabs' });
  const documentsTab = createElement('button', { className: 'detail-tab active', textContent: 'Documentos', type: 'button' });

  tabs.appendChild(documentsTab);

  upcomingTabs.forEach((label) => {
    const tab = createElement('button', { className: 'detail-tab disabled', textContent: label, type: 'button' });
    tab.disabled = true;
    tab.title = 'Em breve';
    tabs.appendChild(tab);
  });

  panel.append(tabs, createClientDocumentsPanel(client.id));
  return panel;
}