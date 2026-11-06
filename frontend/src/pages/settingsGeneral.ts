import { createElement } from '../dom';
import { createInput } from '../components/formFields';
import { type EmpresaAtual, type EmpresaAtualUpdate } from '../services/empresaService';
import { DEFAULT_RATEIO_CONFIG, type RateioConfig } from '../services/rateioConfigService';
import { createPanelHeader, createToggle } from './settingsShared';

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
      createPanelHeader('Dados da Empresa', 'Informações cadastrais da empresa atual'),
      createElement('p', { className: 'settings-hint', textContent: 'Seu perfil não tem permissão para visualizar ou alterar os dados da empresa.' })
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
  panel.appendChild(createPanelHeader('Dados da Empresa', 'Informações cadastrais da empresa atual. Slug e status não podem ser alterados aqui.'));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando dados da empresa...' }));
    return panel;
  }
  if (loadError || !empresa) {
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
    retry.addEventListener('click', () => void onRetry());
    panel.append(createElement('p', { className: 'settings-hint', textContent: 'Não foi possível carregar os dados da empresa.' }), retry);
    return panel;
  }

  const form = createElement('form', { className: 'settings-form empresa-atual-form' });
  const nome = createInput('Nome', 'text', empresa.nome, true);
  const razaoSocial = createInput('Razão social', 'text', empresa.razaoSocial ?? '', false);
  const cnpj = createInput('CNPJ', 'text', empresa.cnpj ?? '', false);
  cnpj.input.inputMode = 'numeric';
  cnpj.input.placeholder = 'Somente números';
  const email = createInput('E-mail', 'email', empresa.email ?? '', false);
  const telefone = createInput('Telefone', 'tel', empresa.telefone ?? '', false);
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: 'Salvar dados' });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nomeValue = nome.input.value.trim();
    const cnpjValue = cnpj.input.value.replace(/\D/g, '');
    const telefoneValue = telefone.input.value.trim();
    if (!nomeValue) { nome.input.focus(); return; }
    if (cnpjValue && cnpjValue.length !== 14) { cnpj.input.setCustomValidity('Informe os 14 dígitos do CNPJ.'); cnpj.input.reportValidity(); return; }
    cnpj.input.setCustomValidity('');
    if (!email.input.checkValidity()) { email.input.reportValidity(); return; }
    if (telefoneValue && telefoneValue.replace(/\D/g, '').length < 8) { telefone.input.setCustomValidity('Informe um telefone válido.'); telefone.input.reportValidity(); return; }
    telefone.input.setCustomValidity('');
    submit.disabled = true;
    submit.textContent = 'Salvando...';
    try {
      await onSave({ nome: nomeValue, razaoSocial: razaoSocial.input.value.trim(), cnpj: cnpjValue, email: email.input.value.trim(), telefone: telefoneValue });
    } catch {
      submit.disabled = false;
      submit.textContent = 'Salvar dados';
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
  panel.appendChild(createPanelHeader('Rateio', 'Regras padrão usadas pelo motor de rateio'));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' }));
    return panel;
  }

  const body = createElement('div', { className: 'settings-form' });
  const habilitado = createElement('label', { className: 'form-field form-field-checkbox' });
  const habilitadoInput = createElement('input');
  habilitadoInput.type = 'checkbox';
  habilitadoInput.checked = config.bufferHabilitado;
  habilitado.append(habilitadoInput, createElement('span', { textContent: 'Aplicar buffer de segurança no consumo por padrão' }));

  const exigirCnpj = createToggle('Exigir CNPJ da empresa para gerar o formulário', config.documentoCnpjObrigatorio);
  const exigirEstatuto = createToggle('Exigir estatuto da empresa para gerar o formulário', config.documentoEstatutoObrigatorio);
  const exigirTermos = createToggle('Exigir Termos de Adesão das beneficiárias para gerar PDF e Excel', config.termosAdesaoObrigatorios);

  const percentual = createElement('label', { className: 'form-field' });
  const percentualLabel = createElement('span', { textContent: 'Percentual do buffer (%)' });
  const percentualInput = createElement('input');
  percentualInput.type = 'number';
  percentualInput.min = '0';
  percentualInput.max = '100';
  percentualInput.step = '0.5';
  percentualInput.value = String(config.bufferPercentual);
  percentual.append(percentualLabel, percentualInput);

  const hint = createElement('p', {
    className: 'settings-hint',
    textContent: 'Esse valor vale pra todas as UCs por padrão. Cada UC pode ter um percentual próprio (campo dentro do cadastro da UC), que sempre ganha desse valor global quando preenchido.'
  });

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar', type: 'button' });
  const resetButton = createElement('button', { className: 'secondary-button', textContent: 'Restaurar padrão', type: 'button' });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    await onSave({
      bufferHabilitado: habilitadoInput.checked,
      bufferPercentual: Number(percentualInput.value) || 0,
      documentoCnpjObrigatorio: exigirCnpj.checked,
      documentoEstatutoObrigatorio: exigirEstatuto.checked,
      termosAdesaoObrigatorios: exigirTermos.checked
    });

    saveButton.disabled = false;
    saveButton.textContent = 'Salvar';
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
    createElement('p', { className: 'settings-subheading', textContent: 'Documentos do formulário Copel' }),
    exigirCnpj.field,
    exigirEstatuto.field,
    exigirTermos.field,
    createElement('p', { className: 'settings-hint', textContent: 'Desative apenas para testes internos. Com a regra desligada, a geração de PDF e Excel não bloqueia pela ausência do documento.' })
  );
  actions.append(saveButton, resetButton);
  panel.append(body, actions);

  return panel;
}
