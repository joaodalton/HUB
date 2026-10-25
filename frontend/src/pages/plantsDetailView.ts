// frontend/src/pages/plantsDetailView.ts
// Detalhe de usina (painel de informacoes, resumo, abas e UCs conectadas) --
// extraido de PlantsPage.ts (organizacao, sem mudanca de comportamento).
import { createDataTable } from '../components/DataTable';
import { createInfoField } from '../components/ClientDetailView';
import { createIcon } from '../components/Icon';
import { createStatusBadge } from '../components/StatusBadge';
import { createElement } from '../dom';
import { plantStatusLabel, plantStatusTone, type PlantRow } from '../services/plantService';
import type { UcRow } from '../services/ucsService';
import {
  connectedUcs,
  createIdNameCell,
  createMonthlyProductionChart,
  createOccupancyBar,
  createStatusDotLabel,
  createSummaryRow,
  plantLocationLabel,
  upcomingPlantTabs,
  type ConnectedUcRow
} from './plantsShared';

export type PlantDetailViewProps = {
  plant: PlantRow;
  allUcs: UcRow[];
  onBack: () => void;
  onEdit: (plant: PlantRow) => void;
  onDelete: (plant: PlantRow) => void;
  onOpenDistribuicao: (plant: PlantRow) => void;
  onRemoveConnection: (plant: PlantRow, row: ConnectedUcRow) => void;
};

export function renderPlantDetailView(props: PlantDetailViewProps): HTMLElement {
  const { plant, allUcs, onBack, onEdit, onDelete, onOpenDistribuicao, onRemoveConnection } = props;
  const wrapper = createElement('section', { className: 'client-detail-view' });

  const backLink = createElement('a', { className: 'detail-back-link', textContent: '← Usinas' });
  backLink.href = '#';
  backLink.addEventListener('click', (event) => {
    event.preventDefault();
    onBack();
  });

  const columns = createElement('div', { className: 'detail-columns' });
  columns.append(createPlantInfoPanel(plant, allUcs), createPlantSummaryPanel(plant, allUcs));

  wrapper.append(backLink, createPlantDetailHeader(plant, onEdit, onDelete), columns, createPlantTabsPanel(plant, allUcs, onOpenDistribuicao, onRemoveConnection));
  return wrapper;
}

function createPlantDetailHeader(plant: PlantRow, onEdit: (plant: PlantRow) => void, onDelete: (plant: PlantRow) => void): HTMLElement {
  const header = createElement('div', { className: 'detail-header' });
  const titleRow = createElement('div', { className: 'detail-title-row' });
  const idTag = createElement('span', { className: 'cell-id-tag', textContent: `#${plant.id}` });
  const heading = createElement('h2', { textContent: plant.nome });
  const tone = plantStatusTone(plant.status);
  const badge = createStatusBadge(plantStatusLabel(plant.status), tone);

  const actions = createElement('div', { className: 'detail-actions' });
  const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
  editButton.append(createIcon('edit'), document.createTextNode('Editar'));
  const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
  deleteButton.append(createIcon('trash'), document.createTextNode('Excluir'));

  editButton.addEventListener('click', () => onEdit(plant));
  deleteButton.addEventListener('click', () => onDelete(plant));

  titleRow.append(idTag, heading, badge);
  actions.append(editButton, deleteButton);
  header.append(titleRow, actions);

  return header;
}

function createPlantInfoPanel(plant: PlantRow, allUcs: UcRow[]): HTMLElement {
  const panel = createElement('aside', { className: 'detail-info-panel' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Informações gerais' });
  const grid = createElement('div', { className: 'detail-info-grid' });

  grid.append(
    createInfoField('Potência (kWp)', plant.kwPico),
    createInfoField('Cidade/UF', plantLocationLabel(plant)),
    createInfoField('Endereço', plant.endereco || 'Não informado'),
    createInfoField('Data de ativação', plant.dataAtivacao || 'Não informado'),
    createInfoField('Responsável', plant.responsavel || 'Não informado'),
    createInfoField('UCs conectadas', String(connectedUcs(allUcs, plant.id).length)),
    createInfoField('Marca do inversor', plant.marcaInversor || 'Não informado'),
    createInfoField('Telefone do proprietário', plant.telefoneProprietario || 'Não informado'),
    createInfoField('Email do proprietário', plant.emailProprietario || 'Não informado')
  );

  panel.append(eyebrow, grid);
  return panel;
}

function createPlantSummaryPanel(plant: PlantRow, allUcs: UcRow[]): HTMLElement {
  const panel = createElement('aside', { className: 'detail-info-panel plant-summary-panel' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Resumo' });
  const rows = createElement('div', { className: 'plant-summary-rows' });
  const activeCount = connectedUcs(allUcs, plant.id).length;

  // "UCs disponiveis" / "UCs aguardando" nao tem contrapartida no backend
  // ainda (nao existe esse conceito no model hoje) -- mostrando "-" em vez
  // de inventar numero. "UCs ativas" e real (contagem de PlantConnection).
  rows.append(
    createSummaryRow('UCs ativas', String(activeCount)),
    createSummaryRow('UCs disponíveis', '-'),
    createSummaryRow('UCs aguardando', '-')
  );

  const occupied = Math.max(0, Math.min(100, 100 - plant.percentualDisponivel));
  const occupancy = createElement('div', { className: 'plant-summary-occupancy' });
  occupancy.append(createSummaryRow('% Ocupação', `${occupied}%`), createOccupancyBar(occupied));

  panel.append(eyebrow, rows, occupancy, createMonthlyProductionChart(plant));
  return panel;
}

function createPlantTabsPanel(
  plant: PlantRow,
  allUcs: UcRow[],
  onOpenDistribuicao: (plant: PlantRow) => void,
  onRemoveConnection: (plant: PlantRow, row: ConnectedUcRow) => void
): HTMLElement {
  const panel = createElement('section', { className: 'detail-tabs-panel' });
  const tabs = createElement('div', { className: 'detail-tabs' });
  const ucsTab = createElement('button', { className: 'detail-tab active', textContent: 'UCs conectadas', type: 'button' });

  tabs.appendChild(ucsTab);

  upcomingPlantTabs.forEach((label) => {
    const tab = createElement('button', { className: 'detail-tab disabled', textContent: label, type: 'button' });
    tab.disabled = true;
    tab.title = 'Em breve';
    tabs.appendChild(tab);
  });

  panel.append(tabs, createConnectedUcsActions(plant, allUcs, onOpenDistribuicao), createConnectedUcsTable(plant, allUcs, onRemoveConnection));
  return panel;
}

function createConnectedUcsActions(plant: PlantRow, allUcs: UcRow[], onOpenDistribuicao: (plant: PlantRow) => void): HTMLElement {
  const bar = createElement('div', { className: 'page-actions' });
  const spacer = createElement('div');
  spacer.style.flex = '1 0 auto';
  spacer.style.minWidth = '0';

  const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
  editButton.append(createIcon('edit'), document.createTextNode('Editar distribuição'));
  editButton.disabled = connectedUcs(allUcs, plant.id).length === 0;
  editButton.title = editButton.disabled ? 'Nenhuma UC conectada ainda' : 'Editar percentual das UCs conectadas';
  editButton.addEventListener('click', () => onOpenDistribuicao(plant));

  bar.append(spacer, editButton);
  return bar;
}

function createConnectedUcsTable(plant: PlantRow, allUcs: UcRow[], onRemoveConnection: (plant: PlantRow, row: ConnectedUcRow) => void): HTMLElement {
  const rows = connectedUcs(allUcs, plant.id);

  return createDataTable<ConnectedUcRow>({
    title: 'UCs conectadas',
    eyebrow: 'Rateio',
    rows,
    emptyMessage: 'Nenhuma UC conectada a esta usina ainda.',
    columns: [
      { key: 'uc', label: 'UC', render: (row) => createIdNameCell(row.codigo, row.apelido) },
      { key: 'cliente', label: 'Cliente' },
      { key: 'percentual', label: '% Rateio', align: 'right' },
      { key: 'status', label: 'Status', render: (row) => createStatusDotLabel(row.status, 'success') },
      { key: 'acao', label: '', align: 'right', render: (row) => createRemoveConnectionButton(plant, row, onRemoveConnection) }
    ]
  });
}

function createRemoveConnectionButton(plant: PlantRow, row: ConnectedUcRow, onRemoveConnection: (plant: PlantRow, row: ConnectedUcRow) => void): HTMLElement {
  const button = createElement('button', { className: 'icon-button', type: 'button' });
  button.appendChild(createIcon('x'));
  button.title = 'Desconectar da usina';
  button.setAttribute('aria-label', `Desconectar ${row.codigo} da usina`);
  button.addEventListener('click', () => onRemoveConnection(plant, row));
  return button;
}
