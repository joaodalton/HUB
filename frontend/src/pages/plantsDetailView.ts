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
  getUpcomingPlantTabs,
  plantLocationLabel,
  type ConnectedUcRow
} from './plantsShared';
import { t } from '../services/i18nService';

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

  const backLink = createElement('a', { className: 'detail-back-link', textContent: t('plants.detail.backLink') });
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
  editButton.append(createIcon('edit'), document.createTextNode(t('plants.detail.actionsEdit')));
  const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
  deleteButton.append(createIcon('trash'), document.createTextNode(t('plants.detail.actionsDelete')));

  editButton.addEventListener('click', () => onEdit(plant));
  deleteButton.addEventListener('click', () => onDelete(plant));

  titleRow.append(idTag, heading, badge);
  actions.append(editButton, deleteButton);
  header.append(titleRow, actions);

  return header;
}

function createPlantInfoPanel(plant: PlantRow, allUcs: UcRow[]): HTMLElement {
  const panel = createElement('aside', { className: 'detail-info-panel' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('plants.detail.infoEyebrow') });
  const grid = createElement('div', { className: 'detail-info-grid' });

  grid.append(
    createInfoField(t('plants.detail.labelKwPico'), plant.kwPico),
    createInfoField(t('plants.detail.labelCidadeUf'), plantLocationLabel(plant)),
    createInfoField(t('plants.detail.labelEndereco'), plant.endereco || t('plants.notInformed')),
    createInfoField(t('plants.detail.labelDataAtivacao'), plant.dataAtivacao || t('plants.notInformed')),
    createInfoField(t('plants.detail.labelResponsavel'), plant.responsavel || t('plants.notInformed')),
    createInfoField(t('plants.detail.labelUcsConectadas'), String(connectedUcs(allUcs, plant.id).length)),
    createInfoField(t('plants.detail.labelMarcaInversor'), plant.marcaInversor || t('plants.notInformed')),
    createInfoField(t('plants.detail.labelTelefoneProprietario'), plant.telefoneProprietario || t('plants.notInformed')),
    createInfoField(t('plants.detail.labelEmailProprietario'), plant.emailProprietario || t('plants.notInformed'))
  );

  panel.append(eyebrow, grid);
  return panel;
}

function createPlantSummaryPanel(plant: PlantRow, allUcs: UcRow[]): HTMLElement {
  const panel = createElement('aside', { className: 'detail-info-panel plant-summary-panel' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('plants.detail.summaryEyebrow') });
  const rows = createElement('div', { className: 'plant-summary-rows' });
  const activeCount = connectedUcs(allUcs, plant.id).length;

  // "UCs disponiveis" / "UCs aguardando" nao tem contrapartida no backend
  // ainda (nao existe esse conceito no model hoje) -- mostrando "-" em vez
  // de inventar numero. "UCs ativas" e real (contagem de PlantConnection).
  rows.append(
    createSummaryRow(t('plants.detail.summaryActiveUcs'), String(activeCount)),
    createSummaryRow(t('plants.detail.summaryAvailableUcs'), '-'),
    createSummaryRow(t('plants.detail.summaryPendingUcs'), '-')
  );

  const occupied = Math.max(0, Math.min(100, 100 - plant.percentualDisponivel));
  const occupancy = createElement('div', { className: 'plant-summary-occupancy' });
  occupancy.append(createSummaryRow(t('plants.detail.summaryOccupancy'), `${occupied}%`), createOccupancyBar(occupied));

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
  const ucsTab = createElement('button', { className: 'detail-tab active', textContent: t('plants.detail.tabConnectedUcs'), type: 'button' });

  tabs.appendChild(ucsTab);

  getUpcomingPlantTabs().forEach((label) => {
    const tab = createElement('button', { className: 'detail-tab disabled', textContent: label, type: 'button' });
    tab.disabled = true;
    tab.title = t('plants.detail.tabDisabledTitle');
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
  editButton.append(createIcon('edit'), document.createTextNode(t('plants.detail.editDistribuicao')));
  editButton.disabled = connectedUcs(allUcs, plant.id).length === 0;
  editButton.title = editButton.disabled ? t('plants.detail.editDistribuicaoDisabledTitle') : t('plants.detail.editDistribuicaoTitle');
  editButton.addEventListener('click', () => onOpenDistribuicao(plant));

  bar.append(spacer, editButton);
  return bar;
}

function createConnectedUcsTable(plant: PlantRow, allUcs: UcRow[], onRemoveConnection: (plant: PlantRow, row: ConnectedUcRow) => void): HTMLElement {
  const rows = connectedUcs(allUcs, plant.id);

  return createDataTable<ConnectedUcRow>({
    title: t('plants.detail.connectedTableTitle'),
    eyebrow: t('plants.detail.connectedTableEyebrow'),
    rows,
    emptyMessage: t('plants.detail.connectedTableEmpty'),
    columns: [
      { key: 'uc', label: t('plants.detail.columnUc'), render: (row) => createIdNameCell(row.codigo, row.apelido) },
      { key: 'cliente', label: t('plants.detail.columnCliente') },
      { key: 'percentual', label: t('plants.detail.columnPercentual'), align: 'right' },
      { key: 'status', label: t('plants.detail.columnStatus'), render: (row) => createStatusDotLabel(row.status, 'success') },
      { key: 'acao', label: '', align: 'right', render: (row) => createRemoveConnectionButton(plant, row, onRemoveConnection) }
    ]
  });
}

function createRemoveConnectionButton(plant: PlantRow, row: ConnectedUcRow, onRemoveConnection: (plant: PlantRow, row: ConnectedUcRow) => void): HTMLElement {
  const button = createElement('button', { className: 'icon-button', type: 'button' });
  button.appendChild(createIcon('x'));
  button.title = t('plants.detail.removeConnectionTitle');
  button.setAttribute('aria-label', `${t('plants.detail.removeConnectionAriaPrefix')} ${row.codigo} ${t('plants.detail.removeConnectionAriaSuffix')}`);
  button.addEventListener('click', () => onRemoveConnection(plant, row));
  return button;
}
