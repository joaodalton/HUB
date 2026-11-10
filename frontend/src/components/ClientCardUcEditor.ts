import { createElement } from '../dom';
import { createContextHelp } from './ContextHelp';
import { createConcessionariaPasswordField } from './ConcessionariaPasswordField';
import { createCheckboxField, createDebitoAutomaticoField, createInput, createSelect } from './formFields';
import { cnpjError, cpfError, digits, maskCpfCnpjInput, validateField } from './cadastroFields';
import { createPlantConnections, createTariffSelect } from './PlantConnectionsField';
import type { ClientUc } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';
import { t } from '../services/i18nService';

export function createUcPanel(ucs: ClientUc[], availablePlants: PlantRow[]): HTMLElement {
  const panel = createElement('aside', { className: 'client-uc-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('clients.uc.panelEyebrow') });
  const heading = createElement('h2', { textContent: t('clients.uc.panelHeading') });
  const addButton = createElement('button', {
    className: 'small-button',
    textContent: t('clients.uc.addButton'),
    type: 'button'
  });
  const list = createElement('div', { className: 'uc-editor-list' });

  function renderList(): void {
    list.replaceChildren();

    if (ucs.length === 0) {
      list.appendChild(createElement('p', {
        className: 'empty-state small',
        textContent: t('clients.uc.empty')
      }));
      return;
    }

    ucs.forEach((uc) => {
      list.appendChild(createUcEditor(uc, availablePlants, () => {
        const index = ucs.findIndex((item) => item.id === uc.id);
        if (index >= 0) ucs.splice(index, 1);
        renderList();
      }));
    });
  }

  addButton.addEventListener('click', () => {
    ucs.push(createEmptyUc());
    renderList();
  });

  titleText.append(eyebrow, heading);
  title.append(titleText, addButton);
  panel.append(title, list);
  renderList();

  return panel;
}

function createUcEditor(uc: ClientUc, availablePlants: PlantRow[], onRemove: () => void): HTMLElement {
  const card = createElement('details', { className: 'uc-editor-card' });
  const summary = createElement('summary', { className: 'uc-summary' });
  const summaryTitle = createElement('strong', { textContent: uc.codigo || t('clients.uc.newFallback') });
  const summaryMeta = createElement('span', { textContent: uc.apelido || t('clients.uc.moreInfoFallback') });
  const body = createElement('div', { className: 'uc-editor-body' });
  const grid = createElement('div', { className: 'uc-editor-grid' });

  const codigo = createInput(t('clients.uc.fieldCode'), 'text', uc.codigo, false);
  codigo.input.inputMode = 'numeric';
  codigo.input.dataset.ucCode = 'true';
  codigo.input.dataset.existingUc = String(typeof uc.id === 'number');
  codigo.input.dataset.originalValue = uc.codigo;
  codigo.input.dataset.originalConcessionaria = uc.concessionaria ?? '';
  const apelido = createInput(t('clients.uc.fieldNickname'), 'text', uc.apelido, false);
  const documento = createInput(t('clients.uc.fieldDocument'), 'text', uc.documento ?? '', false);
  documento.input.dataset.ucDocument = 'true';
  documento.input.dataset.originalValue = uc.documento ?? '';
  maskCpfCnpjInput(documento.input);
  documento.input.addEventListener('input', () => validateField(documento.input, ''));
  documento.input.addEventListener('blur', () => {
    if (documento.input.value.trim() && documento.input.value !== documento.input.dataset.originalValue) validateField(documento.input,
      digits(documento.input.value).length === 11 ? cpfError(documento.input.value) : cnpjError(documento.input.value));
  });
  const senhaConcessionaria = createConcessionariaPasswordField(uc);
  senhaConcessionaria.input.autocomplete = 'new-password';
  senhaConcessionaria.input.placeholder = t('clients.uc.fieldPasswordPlaceholder');
  const endereco = createInput(t('clients.uc.fieldAddress'), 'text', uc.endereco ?? '', false);
  const cep = createInput(t('clients.uc.fieldZip'), 'text', uc.cep ?? '', false);
  const concessionariaUc = createInput(t('clients.uc.fieldUtility'), 'text', uc.concessionaria ?? '', false);
  concessionariaUc.input.addEventListener('input', () => {
    codigo.input.dataset.concessionaria = concessionariaUc.input.value; validateField(codigo.input, '');
  });
  codigo.input.dataset.concessionaria = concessionariaUc.input.value;
  const consumo = createInput(t('clients.uc.fieldConsumption'), 'number', uc.consumo != null ? String(uc.consumo) : '', false);
  const baseTarifaria = createTariffSelect(uc.baseTarifaria);
  const desconto = createInput(t('clients.uc.fieldDiscount'), 'text', uc.desconto, false);
  desconto.field.querySelector('span')?.appendChild(createContextHelp(t('clients.uc.discountHelpLabel'),
    t('clients.uc.discountHelpText')));
  const tipoLigacao = createSelect(t('clients.uc.fieldConnectionLabel'), uc.tipoLigacao, ['Monofasico', 'Bifasico', 'Trifasico']);
  const geracaoPropria = createCheckboxField(t('clients.uc.fieldGeracaoPropria'), uc.geracaoPropria);
  const debitoAutomatico = createDebitoAutomaticoField(uc.debitoAutomatico ?? false);
  const diaEmissaoFatura = createInput(t('clients.uc.fieldDiaEmissao'), 'number', uc.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : '', false);
  const inicioContrato = createInput(t('clients.uc.fieldInicioContrato'), 'date', uc.inicioContrato ?? '', false);
  const terminoContrato = createInput(t('clients.uc.fieldTerminoContrato'), 'date', uc.terminoContrato ?? '', false);
  const carenciaMeses = createInput(t('clients.uc.fieldCarenciaMeses'), 'number', uc.carenciaMeses != null ? String(uc.carenciaMeses) : '', false);
  const percentualDescontoCarencia = createInput(t('clients.uc.fieldDescontoCarencia'), 'text', uc.percentualDescontoCarencia ?? '', false);

  const removeButton = createElement('button', {
    className: 'danger-button',
    textContent: t('clients.uc.removeButton'),
    type: 'button'
  });
  const plantArea = createPlantConnections(uc, availablePlants);

  diaEmissaoFatura.input.min = '1';
  diaEmissaoFatura.input.max = '31';
  carenciaMeses.input.min = '0';

  codigo.input.addEventListener('input', () => {
    validateField(codigo.input, '');
    uc.codigo = codigo.input.value;
    summaryTitle.textContent = uc.codigo || t('clients.uc.newFallback');
  });
  apelido.input.addEventListener('input', () => {
    uc.apelido = apelido.input.value;
    summaryMeta.textContent = uc.apelido || t('clients.uc.moreInfoFallback');
  });
  documento.input.addEventListener('input', () => { uc.documento = documento.input.value || null; });
  senhaConcessionaria.input.addEventListener('input', () => { uc.senhaConcessionaria = senhaConcessionaria.input.value || undefined; });
  endereco.input.addEventListener('input', () => { uc.endereco = endereco.input.value || null; });
  cep.input.addEventListener('input', () => { uc.cep = cep.input.value || null; });
  concessionariaUc.input.addEventListener('input', () => { uc.concessionaria = concessionariaUc.input.value || null; });
  consumo.input.addEventListener('input', () => {
    uc.consumo = consumo.input.value.trim() ? Number(consumo.input.value) : null;
  });
  baseTarifaria.select.addEventListener('change', () => { uc.baseTarifaria = baseTarifaria.select.value; });
  desconto.input.addEventListener('input', () => { uc.desconto = desconto.input.value; });
  tipoLigacao.select.addEventListener('change', () => {
    uc.tipoLigacao = tipoLigacao.select.value as ClientUc['tipoLigacao'];
  });
  geracaoPropria.input.addEventListener('change', () => { uc.geracaoPropria = geracaoPropria.input.checked; });
  debitoAutomatico.input.addEventListener('change', () => { uc.debitoAutomatico = debitoAutomatico.input.checked; });
  diaEmissaoFatura.input.addEventListener('input', () => {
    const raw = diaEmissaoFatura.input.value.trim();
    uc.diaEmissaoFatura = raw ? Number(raw) : null;
  });
  inicioContrato.input.addEventListener('input', () => { uc.inicioContrato = inicioContrato.input.value || null; });
  terminoContrato.input.addEventListener('input', () => { uc.terminoContrato = terminoContrato.input.value || null; });
  carenciaMeses.input.addEventListener('input', () => {
    const raw = carenciaMeses.input.value.trim();
    uc.carenciaMeses = raw ? Number(raw) : null;
  });
  percentualDescontoCarencia.input.addEventListener('input', () => {
    uc.percentualDescontoCarencia = percentualDescontoCarencia.input.value || null;
  });
  removeButton.addEventListener('click', onRemove);

  grid.append(
    codigo.field,
    apelido.field,
    documento.field,
    senhaConcessionaria.field,
    endereco.field,
    cep.field,
    concessionariaUc.field,
    consumo.field,
    baseTarifaria.field,
    desconto.field,
    tipoLigacao.field,
    geracaoPropria.field,
    debitoAutomatico.field,
    diaEmissaoFatura.field,
    inicioContrato.field,
    terminoContrato.field,
    carenciaMeses.field,
    percentualDescontoCarencia.field
  );
  summary.append(summaryTitle, summaryMeta);
  body.append(grid, plantArea, removeButton);
  card.append(summary, body);

  return card;
}

export function createEmptyUc(): ClientUc {
  return {
    id: crypto.randomUUID(),
    codigo: '',
    apelido: '',
    documento: null,
    endereco: null,
    cep: null,
    concessionaria: null,
    geracaoPropria: false,
    debitoAutomatico: false,
    diaEmissaoFatura: null,
    consumo: null,
    baseTarifaria: 'B1',
    desconto: '',
    tipoLigacao: 'Monofasico',
    inicioContrato: null,
    terminoContrato: null,
    carenciaMeses: null,
    percentualDescontoCarencia: null,
    conexoes: []
  };
}
