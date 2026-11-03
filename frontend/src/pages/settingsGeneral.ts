import { maskCnpjInput } from '../components/cadastroFields';
import { createElement } from '../dom';
import { createInput } from '../components/formFields';
import { type EmpresaAtual, type EmpresaAtualUpdate } from '../services/empresaService';
import { DEFAULT_RATEIO_CONFIG, type RateioConfig } from '../services/rateioConfigService';
import { createPanelHeader, createToggle } from './settingsShared';
import { t } from '../services/i18nService';

// ---------- Geral ----------

export function createGeralPanel(
  empresa: EmpresaAtual | null,
  empresaLoaded: boolean,
  empresaLoadError: boolean,
  canManage: boolean,
  onRetryEmpresa: () => Promise<void>,
  onSaveEmpresa: (data: EmpresaAtualUpdate) => Promise<void>,
  config: RateioConfig,
  loaded: boolean,
  onSave: (config: RateioConfig) => Promise<void>
): HTMLElement {
  const stack = createElement('div', { className: 'content-stack' });
  if (!canManage) {
    const denied = createElement('section', { className: 'settings-panel' });
    denied.append(
      createPanelHeader(t('settings.general.empresaHeading'), t('settings.general.empresaDescriptionDenied')),
      createElement('p', { className: 'settings-hint', textContent: t('settings.general.denied') })
    );
    stack.appendChild(denied);
    return stack;
  }

  stack.append(
    createEmpresaAtualPanel(empresa, empresaLoaded, empresaLoadError, onRetryEmpresa, onSaveEmpresa),
    createRateioConfigPanel(config, loaded, onSave)
  );
  return stack;
}

function createEmpresaAtualPanel(
  empresa: EmpresaAtual | null,
  loaded: boolean,
  loadError: boolean,
  onRetry: () => Promise<void>,
  onSave: (data: EmpresaAtualUpdate) => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel empresa-atual-panel' });
  panel.appendChild(createPanelHeader(t('settings.general.empresaHeading'), t('settings.general.empresaDescription')));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.general.loadingEmpresa') }));
    return panel;
  }
  if (loadError || !empresa) {
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.retry') });
    retry.addEventListener('click', () => void onRetry());
    panel.append(createElement('p', { className: 'settings-hint', textContent: t('settings.general.loadEmpresaError') }), retry);
    return panel;
  }

  const form = createElement('form', { className: 'settings-form empresa-atual-form' });
  const nome = createInput(t('settings.general.nome'), 'text', empresa.nome, true);
  const razaoSocial = createInput(t('settings.general.razaoSocial'), 'text', empresa.razaoSocial ?? '', false);
  const cnpj = createInput(t('settings.general.cnpj'), 'text', empresa.cnpj ?? '', false);
  cnpj.input.inputMode = 'numeric';
  maskCnpjInput(cnpj.input);
  const email = createInput(t('settings.general.email'), 'email', empresa.email ?? '', false);
  const telefone = createInput(t('settings.general.telefone'), 'tel', empresa.telefone ?? '', false);
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: t('settings.general.saveEmpresa') });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nomeValue = nome.input.value.trim();
    const cnpjValue = cnpj.input.value.replace(/\D/g, '');
    const telefoneValue = telefone.input.value.trim();
    if (!nomeValue) { nome.input.focus(); return; }
    if (cnpjValue && cnpjValue.length !== 14) { cnpj.input.setCustomValidity(t('settings.general.cnpjInvalid')); cnpj.input.reportValidity(); return; }
    cnpj.input.setCustomValidity('');
    if (!email.input.checkValidity()) { email.input.reportValidity(); return; }
    if (telefoneValue && telefoneValue.replace(/\D/g, '').length < 8) { telefone.input.setCustomValidity(t('settings.general.telefoneInvalid')); telefone.input.reportValidity(); return; }
    telefone.input.setCustomValidity('');
    submit.disabled = true;
    submit.textContent = t('common.saving');
    try {
      await onSave({ nome: nomeValue, razaoSocial: razaoSocial.input.value.trim(), cnpj: cnpjValue, email: email.input.value.trim(), telefone: telefoneValue });
    } catch {
      submit.disabled = false;
      submit.textContent = t('settings.general.saveEmpresa');
    }
  });
  actions.appendChild(submit);
  form.append(nome.field, razaoSocial.field, cnpj.field, email.field, telefone.field, actions);
  panel.appendChild(form);
  return panel;
}
function createRateioConfigPanel(
  config: RateioConfig,
  loaded: boolean,
  onSave: (config: RateioConfig) => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel rateio-config-panel' });
  panel.appendChild(createPanelHeader(t('settings.general.rateioHeading'), t('settings.general.rateioDescription')));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('common.loading') }));
    return panel;
  }

  const body = createElement('div', { className: 'settings-form' });
  const habilitado = createElement('label', { className: 'form-field form-field-checkbox' });
  const habilitadoInput = createElement('input');
  habilitadoInput.type = 'checkbox';
  habilitadoInput.checked = config.bufferHabilitado;
  habilitado.append(habilitadoInput, createElement('span', { textContent: t('settings.general.bufferCheckbox') }));

  const exigirCnpj = createToggle(t('settings.general.exigirCnpj'), config.documentoCnpjObrigatorio);
  const exigirEstatuto = createToggle(t('settings.general.exigirEstatuto'), config.documentoEstatutoObrigatorio);
  const exigirTermos = createToggle(t('settings.general.exigirTermos'), config.termosAdesaoObrigatorios);

  const percentual = createElement('label', { className: 'form-field' });
  const percentualLabel = createElement('span', { textContent: t('settings.general.percentualLabel') });
  const percentualInput = createElement('input');
  percentualInput.type = 'number';
  percentualInput.min = '0';
  percentualInput.max = '100';
  percentualInput.step = '0.5';
  percentualInput.value = String(config.bufferPercentual);
  percentual.append(percentualLabel, percentualInput);

  const hint = createElement('p', {
    className: 'settings-hint',
    textContent: t('settings.general.percentualHint')
  });

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('settings.general.save'), type: 'button' });
  const resetButton = createElement('button', { className: 'secondary-button', textContent: t('common.restoreDefault'), type: 'button' });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = t('common.saving');

    await onSave({
      bufferHabilitado: habilitadoInput.checked,
      bufferPercentual: Number(percentualInput.value) || 0,
      documentoCnpjObrigatorio: exigirCnpj.checked,
      documentoEstatutoObrigatorio: exigirEstatuto.checked,
      termosAdesaoObrigatorios: exigirTermos.checked
    });

    saveButton.disabled = false;
    saveButton.textContent = t('settings.general.save');
  });

  resetButton.addEventListener('click', async () => {
    habilitadoInput.checked = DEFAULT_RATEIO_CONFIG.bufferHabilitado;
    percentualInput.value = String(DEFAULT_RATEIO_CONFIG.bufferPercentual);
    exigirCnpj.checked = DEFAULT_RATEIO_CONFIG.documentoCnpjObrigatorio;
    exigirEstatuto.checked = DEFAULT_RATEIO_CONFIG.documentoEstatutoObrigatorio;
    exigirTermos.checked = DEFAULT_RATEIO_CONFIG.termosAdesaoObrigatorios;
    await onSave(DEFAULT_RATEIO_CONFIG);
  });

  body.append(
    habilitado,
    percentual,
    hint,
    createElement('p', { className: 'settings-subheading', textContent: t('settings.general.documentsSubheading') }),
    exigirCnpj.field,
    exigirEstatuto.field,
    exigirTermos.field,
    createElement('p', { className: 'settings-hint', textContent: t('settings.general.disableDocsHint') })
  );
  actions.append(saveButton, resetButton);
  panel.append(body, actions);

  return panel;
}
