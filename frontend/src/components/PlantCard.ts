import { createElement } from '../dom';
import { createFormSection, createInput, createSelect, createSelectField } from './formFields';
import { createClientDocumentsPanel } from './ClientDocumentsPanel';
import type { PlantRow } from '../services/plantService';
import { t } from '../services/i18nService';

export type PlantFormData = {
  nome: string;
  uc: string;
  kwPico: string;
  status: string;
  percentualDisponivel: number;
  marcaInversor: string;
  telefoneProprietario: string;
  emailProprietario: string;
  cidade: string;
  uf: string;
  endereco: string;
  dataAtivacao: string;
  responsavel: string;
  numModulos: number | null;
  producaoMediaManual: number | null;
  diaEmissaoUsina: number | null;
  repasseTipo: string | null;
  repasseValor: number | null;
};

type PlantCardOptions = {
  plant?: PlantRow;
  onSave: (data: PlantFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

const plantStatuses = ['Online', 'Implantacao', 'Manutencao', 'Inativa'];

export function createPlantCard({ plant, onSave, onCancel, onDelete }: PlantCardOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: plant ? t('plants.card.eyebrowEdit') : t('plants.card.eyebrowNew') });
  const heading = createElement('h2', { textContent: plant?.nome ?? t('plants.card.headingNew') });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: t('plants.card.closeButton'),
    type: 'button'
  });
  const nome = createInput(t('plants.card.fieldNome'), 'text', plant?.nome ?? '', true);
  const uc = createInput(t('plants.card.fieldUc'), 'text', plant?.uc ?? '', true);
  const kwPico = createInput(t('plants.card.fieldKwPico'), 'number', plant?.kwPico ?? '', true);
  const status = createSelect(t('plants.card.fieldStatus'), plant?.status ?? 'Online', plantStatuses);
  const percentualDisponivel = createInput(
    t('plants.card.fieldPercentualDisponivel'),
    'number',
    String(plant?.percentualDisponivel ?? 0),
    true
  );
  const marcaInversor = createInput(t('plants.card.fieldMarcaInversor'), 'text', plant?.marcaInversor ?? '', false);
  const telefoneProprietario = createInput(t('plants.card.fieldTelefoneProprietario'), 'tel', plant?.telefoneProprietario ?? '', false);
  const emailProprietario = createInput(t('plants.card.fieldEmailProprietario'), 'email', plant?.emailProprietario ?? '', false);
  const cidade = createInput(t('plants.card.fieldCidade'), 'text', plant?.cidade ?? '', false);
  const uf = createInput(t('plants.card.fieldUf'), 'text', plant?.uf ?? '', false);
  const endereco = createInput(t('plants.card.fieldEndereco'), 'text', plant?.endereco ?? '', false);
  const dataAtivacao = createInput(t('plants.card.fieldDataAtivacao'), 'date', plant?.dataAtivacao ?? '', false);
  const responsavel = createInput(t('plants.card.fieldResponsavel'), 'text', plant?.responsavel ?? '', false);
  const numModulos = createInput(t('plants.card.fieldNumModulos'), 'number', plant?.numModulos != null ? String(plant.numModulos) : '', false);
  const producaoMediaManual = createInput(
    t('plants.card.fieldProducaoMedia'),
    'number',
    plant?.producaoMediaManual != null ? String(plant.producaoMediaManual) : '',
    false
  );
  const diaEmissaoUsina = createInput(
    t('plants.card.fieldDiaEmissao'),
    'number',
    plant?.diaEmissaoUsina != null ? String(plant.diaEmissaoUsina) : '',
    false
  );
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('plants.card.saveButton'), type: 'submit' });

  kwPico.input.min = '0';
  percentualDisponivel.input.min = '0';
  percentualDisponivel.input.max = '100';
  uf.input.maxLength = 2;
  numModulos.input.min = '0';
  producaoMediaManual.input.min = '0';
  producaoMediaManual.input.step = '0.01';
  producaoMediaManual.input.placeholder = t('plants.card.fieldProducaoMediaPlaceholder');
  diaEmissaoUsina.input.min = '1';
  diaEmissaoUsina.input.max = '31';
  diaEmissaoUsina.input.placeholder = t('plants.card.fieldDiaEmissaoPlaceholder');

  const repasseTipo = createSelectField(t('plants.card.fieldRepasseTipo'), plant?.repasseTipo ?? '', [
    { value: '', label: t('plants.card.repasseOptionNone') },
    { value: 'percentual', label: t('plants.card.repasseOptionPercent') },
    { value: 'valor_fixo', label: t('plants.card.repasseOptionFixed') }
  ]);
  const repasseValor = createInput(
    t('plants.card.fieldRepasseValor'),
    'number',
    plant?.repasseValor != null ? String(plant.repasseValor) : '',
    false
  );
  const repasseHint = createElement('p', { className: 'settings-hint' });

  repasseValor.input.min = '0';
  repasseValor.input.step = '0.01';
  repasseValor.field.appendChild(repasseHint);

  function syncRepasseHint(): void {
    if (repasseTipo.select.value === 'percentual') {
      repasseHint.textContent = t('plants.card.repasseHintPercent');
    } else if (repasseTipo.select.value === 'valor_fixo') {
      repasseHint.textContent = t('plants.card.repasseHintFixed');
    } else {
      repasseHint.textContent = '';
    }
  }

  repasseTipo.select.addEventListener('change', syncRepasseHint);
  syncRepasseHint();

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  actions.appendChild(saveButton);

  if (plant && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: t('plants.card.deleteButton'),
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  closeButton.addEventListener('click', onCancel);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (!nome.input.value.trim() || !uc.input.value.trim() || !kwPico.input.value.trim()) {
      nome.input.reportValidity();
      uc.input.reportValidity();
      kwPico.input.reportValidity();
      return;
    }

    onSave({
      nome: nome.input.value.trim(),
      uc: uc.input.value.trim(),
      kwPico: kwPico.input.value.trim(),
      status: status.select.value,
      percentualDisponivel: clampPercent(Number(percentualDisponivel.input.value)),
      marcaInversor: marcaInversor.input.value.trim(),
      telefoneProprietario: telefoneProprietario.input.value.trim(),
      emailProprietario: emailProprietario.input.value.trim(),
      cidade: cidade.input.value.trim(),
      uf: uf.input.value.trim().toUpperCase(),
      endereco: endereco.input.value.trim(),
      dataAtivacao: dataAtivacao.input.value,
      responsavel: responsavel.input.value.trim(),
      numModulos: numModulos.input.value.trim() ? Number(numModulos.input.value) : null,
      producaoMediaManual: producaoMediaManual.input.value.trim() ? Number(producaoMediaManual.input.value) : null,
      diaEmissaoUsina: diaEmissaoUsina.input.value.trim() ? Number(diaEmissaoUsina.input.value) : null,
      repasseTipo: repasseTipo.select.value || null,
      repasseValor: repasseValor.input.value.trim() ? Number(repasseValor.input.value) : null
    });
  });

  form.append(
    header,
    createFormSection(t('plants.card.sectionDados'), nome.field, uc.field, status.field, dataAtivacao.field),
    createFormSection(t('plants.card.sectionTecnicas'), kwPico.field, numModulos.field, marcaInversor.field, percentualDisponivel.field, producaoMediaManual.field, diaEmissaoUsina.field),
    createFormSection(t('plants.card.sectionAdicionais'), telefoneProprietario.field, emailProprietario.field, cidade.field, uf.field, endereco.field, responsavel.field),
    createFormSection(t('plants.card.sectionRepasse'), repasseTipo.field, repasseValor.field),
    createFormSection(t('plants.card.sectionDocumentos'), createClientDocumentsPanel(undefined, plant?.id)),
    actions
  );
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}

function clampPercent(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(100, Math.max(0, value));
}
