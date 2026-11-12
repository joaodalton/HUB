import { createElement } from '../dom';
import { createContextHelp } from './ContextHelp';
import { createConcessionariaPasswordField } from './ConcessionariaPasswordField';
import { createCheckboxField, createDebitoAutomaticoField, createFormSection, createInput } from './formFields';
import { cnpjError, cpfError, digits, ucError, validateField } from './cadastroFields';
import { createPlantConnections, createTariffSelect } from './PlantConnectionsField';
import type { ClientRow, PlantConnection } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';
import type { UcPayload, UcRow } from '../services/ucsService';
import { t } from '../services/i18nService';

type UcCardOptions = {
  uc?: UcRow;
  clients: ClientRow[];
  availablePlants: PlantRow[];
  onSave: (data: UcPayload) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

const tiposLigacao = ['Monofasico', 'Bifasico', 'Trifasico'] as const;

export function createUcCard({ uc, clients, availablePlants, onSave, onCancel, onDelete }: UcCardOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: uc ? t('ucs.card.eyebrowEdit') : t('ucs.card.eyebrowNew') });
  const heading = createElement('h2', { textContent: uc ? uc.codigo || t('ucs.card.headingFallback') : t('ucs.card.headingNew') });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: t('ucs.card.closeButton'),
    type: 'button'
  });

  const cliente = createClientSelect(clients, uc?.clienteId);
  const codigo = createInput(t('ucs.card.fieldCodigo'), 'text', uc?.codigo ?? '', true);
  const apelido = createInput(t('ucs.card.fieldApelido'), 'text', uc?.apelido ?? '', false);
  const documento = createInput(t('ucs.card.fieldDocumento'), 'text', uc?.documento ?? '', false);
  const senhaConcessionaria = createConcessionariaPasswordField(uc ?? { id: '' });
  senhaConcessionaria.input.autocomplete = 'new-password';
  senhaConcessionaria.input.placeholder = t('ucs.card.fieldSenhaPlaceholder');
  const endereco = createInput(t('ucs.card.fieldEndereco'), 'text', uc?.endereco ?? '', false);
  const cep = createInput(t('ucs.card.fieldCep'), 'text', uc?.cep ?? '', false);
  const concessionaria = createInput(t('ucs.card.fieldConcessionaria'), 'text', uc?.concessionaria ?? '', false);
  codigo.input.inputMode = 'numeric';
  documento.input.addEventListener('input', () => validateField(documento.input, ''));
  codigo.input.addEventListener('input', () => validateField(codigo.input, ''));
  concessionaria.input.addEventListener('input', () => validateField(codigo.input, ''));
  cliente.select.addEventListener('change', () => validateField(codigo.input, ''));
  const consumo = createInput(t('ucs.card.fieldConsumo'), 'number', uc?.consumo != null ? String(uc.consumo) : '', false);
  const baseTarifaria = createTariffSelect(uc?.baseTarifaria ?? 'B1');
  const desconto = createInput(t('ucs.card.fieldDesconto'), 'text', uc?.desconto ?? '', false);
  desconto.field.querySelector('span')?.appendChild(createContextHelp(t('ucs.card.discountHelpLabel'),
    t('ucs.card.discountHelpText')));
  const tipoLigacao = createLigacaoSelect(uc?.tipoLigacao ?? 'Monofasico');
  const geracaoPropria = createCheckboxField(t('ucs.card.fieldGeracaoPropria'), uc?.geracaoPropria ?? false);
  const debitoAutomatico = createDebitoAutomaticoField(uc?.debitoAutomatico ?? false);
  const diaEmissaoFatura = createInput(t('ucs.card.fieldDiaEmissaoFatura'), 'number', uc?.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : '', false);
  const inicioContrato = createInput(t('ucs.card.fieldInicioContrato'), 'date', uc?.inicioContrato ?? '', false);
  const terminoContrato = createInput(t('ucs.card.fieldTerminoContrato'), 'date', uc?.terminoContrato ?? '', false);
  const carenciaMeses = createInput(t('ucs.card.fieldCarenciaMeses'), 'number', uc?.carenciaMeses != null ? String(uc.carenciaMeses) : '', false);
  const percentualDescontoCarencia = createInput(t('ucs.card.fieldDescontoCarencia'), 'text', uc?.percentualDescontoCarencia ?? '', false);

  diaEmissaoFatura.input.min = '1';
  diaEmissaoFatura.input.max = '31';
  carenciaMeses.input.min = '0';

  // Estado local das conexoes, no mesmo formato que createPlantConnections espera.
  const connectionState: { conexoes: PlantConnection[] } = {
    conexoes: (uc?.conexoes ?? []).map((conexao) => ({ ...conexao }))
  };
  const plantArea = createPlantConnections(connectionState, availablePlants);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('ucs.card.saveButton'), type: 'submit' });

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  actions.appendChild(saveButton);

  if (uc && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: t('ucs.card.deleteButton'),
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  let isSubmitting = false;

  closeButton.addEventListener('click', onCancel);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (isSubmitting) return;

    if (!cliente.select.value || !codigo.input.value.trim()) {
      cliente.select.reportValidity();
      codigo.input.reportValidity();
      return;
    }
    if ((!uc || codigo.input.value !== uc.codigo ||
        (concessionaria.input.value.trim() || null) !== (uc.concessionaria ?? null) ||
        Number(cliente.select.value) !== uc.clienteId) &&
        !validateField(codigo.input, ucError(codigo.input.value, concessionaria.input.value || clients.find((item) => item.id === Number(cliente.select.value))?.concessionaria || 'Copel'))) return;
    if (documento.input.value.trim() && documento.input.value !== (uc?.documento ?? '') && !validateField(documento.input, digits(documento.input.value).length === 11 ? cpfError(documento.input.value) : cnpjError(documento.input.value))) return;
    const codigoValue = (!uc || codigo.input.value !== uc.codigo || (concessionaria.input.value.trim() || null) !== (uc.concessionaria ?? null)) &&
      (concessionaria.input.value || clients.find((item) => item.id === Number(cliente.select.value))?.concessionaria || 'Copel').trim().toLowerCase() === 'copel' && codigo.input.value.length === 12
      ? `000${codigo.input.value}` : codigo.input.value.trim();

    isSubmitting = true;
    saveButton.disabled = true;
    saveButton.textContent = t('ucs.card.savingButton');

    onSave({
      clienteId: Number(cliente.select.value),
      codigo: codigoValue,
      apelido: apelido.input.value.trim(),
      documento: documento.input.value.trim() ? (documento.input.value === (uc?.documento ?? '') ? documento.input.value : digits(documento.input.value)) : null,
      senhaConcessionaria: senhaConcessionaria.input.value || undefined,
      endereco: endereco.input.value.trim() || null,
      cep: cep.input.value.trim() || null,
      concessionaria: concessionaria.input.value.trim() || null,
      geracaoPropria: geracaoPropria.input.checked,
      debitoAutomatico: debitoAutomatico.input.checked,
      diaEmissaoFatura: diaEmissaoFatura.input.value.trim() ? Number(diaEmissaoFatura.input.value) : null,
      consumo: consumo.input.value.trim() ? Number(consumo.input.value) : null,
      baseTarifaria: baseTarifaria.select.value,
      desconto: desconto.input.value.trim(),
      tipoLigacao: tipoLigacao.select.value,
      inicioContrato: inicioContrato.input.value || null,
      terminoContrato: terminoContrato.input.value || null,
      carenciaMeses: carenciaMeses.input.value.trim() ? Number(carenciaMeses.input.value) : null,
      percentualDescontoCarencia: percentualDescontoCarencia.input.value.trim() || null,
      conexoes: connectionState.conexoes
    });
  });

  form.append(
    header,
    createFormSection(t('ucs.card.sectionDados'), cliente.field, codigo.field, apelido.field, documento.field, senhaConcessionaria.field, concessionaria.field),
    createFormSection(t('ucs.card.sectionEnderecoConsumo'), endereco.field, cep.field, consumo.field, baseTarifaria.field, desconto.field, tipoLigacao.field, geracaoPropria.field, debitoAutomatico.field, diaEmissaoFatura.field),
    createFormSection(t('ucs.card.sectionContrato'), inicioContrato.field, terminoContrato.field, carenciaMeses.field, percentualDescontoCarencia.field),
    plantArea,
    actions
  );
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}

function createClientSelect(clients: ClientRow[], selectedId?: number) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: t('ucs.card.fieldCliente') });
  const select = createElement('select');
  const placeholder = createElement('option', { textContent: t('ucs.card.fieldClientePlaceholder') });

  placeholder.value = '';
  select.appendChild(placeholder);

  clients.forEach((client) => {
    const option = createElement('option', { textContent: client.nome });
    option.value = String(client.id);
    select.appendChild(option);
  });

  select.value = selectedId ? String(selectedId) : '';
  select.required = true;

  field.append(text, select);
  return { field, select };
}

function createLigacaoSelect(value: UcRow['tipoLigacao']) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: t('ucs.card.fieldLigacao') });
  const select = createElement('select');

  tiposLigacao.forEach((optionValue) => {
    const option = createElement('option', { textContent: optionValue });
    option.value = optionValue;
    select.appendChild(option);
  });

  select.value = value;
  field.append(text, select);
  return { field, select };
}
