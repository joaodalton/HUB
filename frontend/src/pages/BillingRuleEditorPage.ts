import { createContextHelp } from '../components/ContextHelp';
import { createInput, createSelectField, createFormSection } from '../components/formFields';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import {
  createBillingRule, createBillingRuleAssignment, getBillingRule,
  listBillingRuleAssignments, updateBillingRule, updateBillingRuleAssignment,
  type BillingRule, type BillingRuleAssignment, type BillingRuleInput
} from '../services/billingRulesService';

const METHODS = [
  ['energia_compensada', 'Energia compensada'], ['energia_recebida', 'Energia recebida'],
  ['valor_total_fatura', 'Valor total da fatura'], ['tarifa_fixa', 'Tarifa fixa'],
  ['tarifa_fixa_com_desconto', 'Tarifa fixa com desconto'], ['tarifa_especifica', 'Tarifa específica'],
  ['economia_gerada', 'Economia gerada']
];
const TARIFF_SOURCES = [['invoice', 'Documental'], ['manual', 'Tarifa configurada']];
const BASES = [
  ['compensated', 'Energia compensada'], ['consumed', 'Energia consumida'],
  ['gd1', 'GD I'], ['gd2', 'GD II'], ['documented_component', 'Componente documental']
];
const MODES = [['auto', 'Automático'], ['unified', 'Unificada'], ['separate', 'Separada']];
const DUE_BASES = [
  ['invoice_due_date', 'Vencimento da fatura'], ['invoice_issue_date', 'Emissão da fatura'],
  ['reading_date', 'Leitura'], ['calculation_date', 'Data do cálculo']
];

function options(values: string[][]): Array<{ value: string; label: string }> {
  return [{ value: '', label: 'Selecione' }, ...values.map(([value, label]) => ({ value, label }))];
}

function help(field: HTMLElement, label: string, explanation: string): void {
  field.querySelector('span')?.appendChild(createContextHelp(label, explanation));
}

function decimalField(label: string, value: string | null) {
  const control = createInput(label, 'text', value ?? '');
  control.input.inputMode = 'decimal';
  control.input.pattern = '-?[0-9]{1,12}(\\.[0-9]{1,6})?';
  control.input.title = 'Use ponto decimal e até seis casas, por exemplo 0.654321.';
  return control;
}

function decimalValue(input: HTMLInputElement): string | null {
  return input.value.trim() || null;
}

function booleanValue(value: string): boolean | null {
  return value === '' ? null : value === 'true';
}

function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function createBillingRuleEditorPage(id?: number): HTMLElement {
  const content = createElement('section', { className: 'content-stack billing-rule-editor' });
  const toast = useToast();
  const loading = useGlobalLoading();
  const canWrite = ['owner', 'admin', 'financial'].includes(getCurrentUser()?.role ?? '');
  const ucParam = new URLSearchParams(window.location.search).get('ucId');
  const defaultFlow = !id && new URLSearchParams(window.location.search).get('default') === '1';
  const ucId = ucParam && /^[1-9][0-9]*$/.test(ucParam) && Number.isSafeInteger(Number(ucParam))
    ? Number(ucParam) : null;
  const returnPath = ucId ? `/ucs?ucId=${ucId}` : '/regras-cobranca';
  let rule: BillingRule | undefined;
  let savedId = id;
  let assignments: BillingRuleAssignment[] = [];
  const layout = createBaseLayout({ content, eyebrow: 'Financeiro / Regras de cobrança', title: id ? 'Editar regra' : 'Nova regra' });
  if (id) void load();
  else render();
  return layout;

  async function load(): Promise<void> {
    if (id === undefined) return;
    loading.show();
    try {
      [rule, assignments] = await Promise.all([
        getBillingRule(id), listBillingRuleAssignments({ grupoRegraCobrancaId: String(id), ativo: 'true' })
      ]);
      render();
    } catch (error) {
      content.replaceChildren(createElement('p', {
        textContent: error instanceof Error ? error.message : 'Não foi possível carregar esta regra.'
      }));
    } finally {
      loading.hide();
    }
  }

  function render(): void {
    const readOnly = !canWrite;
    const form = createElement('form', { className: 'billing-rule-form' });
    const heading = createElement('div', { className: 'billing-rule-editor-heading' });
    const breadcrumb = createElement('a', { textContent: 'Regras de cobrança' });
    breadcrumb.href = '/regras-cobranca';
    breadcrumb.addEventListener('click', (event) => { event.preventDefault(); navigate('/regras-cobranca'); });
    heading.append(breadcrumb, document.createTextNode(` / ${id ? 'Editar regra' : 'Nova regra'}`));
    const status = createElement('span', {
      className: 'status-badge tone-info',
      textContent: rule ? rule.ativo ? 'ATIVA' : 'INATIVA' : 'NOVA'
    });
    heading.appendChild(status);
    if (defaultFlow) heading.appendChild(createElement('span', {
      textContent: 'Ao salvar, esta regra será vinculada como padrão da empresa.'
    }));

    const name = createInput('Nome', 'text', rule?.nome ?? '', true);
    name.input.maxLength = 150;
    const description = createElement('label', { className: 'form-field form-field-wide' });
    const descriptionInput = createElement('textarea');
    descriptionInput.value = rule?.descricao ?? '';
    description.append(createElement('span', { textContent: 'Descrição' }), descriptionInput);

    const method = createSelectField('Método tarifário', rule?.calculationMethod ?? '', options(METHODS));
    method.select.required = true;
    help(method.field, 'Método tarifário', 'Define qual base comercial a regra usará. Exemplo: energia compensada usa os kWh de compensação comprovados; métodos sem dados suficientes podem bloquear a execução.');
    const tariffSource = createSelectField('Origem da tarifa', rule?.tariffSource ?? '', options(TARIFF_SOURCES));
    tariffSource.select.required = true;
    const companyTariff = decimalField('Tarifa da empresa (R$/kWh)', rule?.tariffConfiguration.companyTariff ?? null);
    help(companyTariff.field, 'Tarifa da empresa', 'Tarifa configurada para o método comercial. Exemplo: 0.654321 R$/kWh; não é a tarifa cheia encontrada na fatura.');
    const tariffHfp = decimalField('Tarifa HFP (R$/kWh)', rule?.tariffConfiguration.tariffHfp ?? null);
    const tariffHp = decimalField('Tarifa HP (R$/kWh)', rule?.tariffConfiguration.tariffHp ?? null);
    const basis = createSelectField('Base energética', rule?.tariffBasis ?? '', options(BASES));
    basis.select.required = true;
    const componentIndex = createInput('Índice do componente documental', 'number', rule?.energyComponentIndex?.toString() ?? '');
    componentIndex.input.min = '0';
    componentIndex.input.step = '1';
    const documentaryNote = createElement('p', {
      className: 'billing-rule-note',
      textContent: 'Tarifa cheia documental e tarifa de compensação vêm da fatura. Esta página não edita esses valores. ICMS e bandeira são configurações comerciais; algumas combinações ainda bloqueiam a execução.'
    });

    const icms = createSelectField('ICMS', rule?.billingModifiers.icmsPolicy ?? '', [
      { value: '', label: 'Não configurado' }, { value: 'exclude', label: 'Sem ICMS' }
    ]);
    help(icms.field, 'ICMS', '“Sem ICMS” pede a variante documental sem ICMS. Exemplo: tarifa de compensação identificada na fatura. Sem evidência, o cálculo pode bloquear; não recalcula imposto.');
    const flag = createSelectField('Bandeira tarifária', String(rule?.billingModifiers.excludeTariffFlag ?? ''), [
      { value: '', label: 'Não configurado' }, { value: 'true', label: 'Sem bandeira' },
      { value: 'false', label: 'Com bandeira' }
    ]);
    help(flag.field, 'Bandeira tarifária', 'Exige uma tarifa documental com ou sem bandeira, conforme a escolha. Exemplo: “Sem bandeira” só serve quando o documento comprova essa composição.');
    const pis = createSelectField('PIS/COFINS', String(rule?.billingModifiers.excludePisCofins ?? ''), [
      { value: '', label: 'Não configurado' }, { value: 'true', label: 'Excluir com comprovação' },
      { value: 'false', label: 'Não excluir' }
    ]);
    help(pis.field, 'PIS/COFINS', 'A exclusão só ocorre com valores documentais ligados a cada compensação. Exemplo: sem esse vínculo, a execução fica pendente.');
    const graceEnabled = createSelectField('Carência', String(rule?.billingModifiers.gracePeriod.enabled ?? ''), [
      { value: '', label: 'Não configurada' }, { value: 'true', label: 'Ativa' }, { value: 'false', label: 'Desativada' }
    ]);
    const graceDuration = createInput('Duração da carência (meses)', 'number', rule?.billingModifiers.gracePeriod.durationMonths?.toString() ?? '');
    graceDuration.input.min = '1';
    graceDuration.input.step = '1';
    const graceDiscount = createSelectField('Sem desconto na carência', String(rule?.billingModifiers.gracePeriod.withoutDiscount ?? ''), [
      { value: '', label: 'Não configurado' }, { value: 'true', label: 'Sim' }, { value: 'false', label: 'Não' }
    ]);
    const additional = decimalField('Adicional recorrente (R$)', rule?.billingModifiers.recurringAdditionalCost ?? null);
    help(additional.field, 'Adicional recorrente', 'Valor fixo configurado em separado da tarifa, juros e multa. Exemplo: 12.50; aplicação depende do método executável.');

    const mode = createSelectField('Modo de cobrança', rule?.billingMode ?? '', options(MODES));
    mode.select.required = true;
    const dueBasis = createSelectField('Base do vencimento', rule?.dueDateBasis ?? '', options(DUE_BASES));
    dueBasis.select.required = true;
    const dueOffset = createInput('Deslocamento do vencimento (dias)', 'number', rule?.dueDateOffsetDays?.toString() ?? '');
    dueOffset.input.required = true;
    dueOffset.input.step = '1';
    const interest = decimalField('Juros mensais (%)', rule?.monthlyInterest ?? null);
    const fine = decimalField('Multa (%)', rule?.finePercentage ?? null);

    const methodWarning = createElement('p', { className: 'billing-rule-warning' });
    function updateConditional(): void {
      const needsCompanyTariff = ['energia_compensada', 'tarifa_fixa', 'tarifa_especifica',
        'tarifa_fixa_com_desconto'].includes(method.select.value);
      companyTariff.field.hidden = tariffSource.select.value !== 'manual' && !needsCompanyTariff;
      companyTariff.input.required = tariffSource.select.value === 'manual' || needsCompanyTariff;
      componentIndex.field.hidden = basis.select.value !== 'documented_component';
      componentIndex.input.required = basis.select.value === 'documented_component';
      graceDuration.field.hidden = graceEnabled.select.value !== 'true';
      graceDiscount.field.hidden = graceEnabled.select.value !== 'true';
      const unsupportedMethod = method.select.value && ![
        'energia_compensada', 'tarifa_fixa', 'tarifa_especifica'
      ].includes(method.select.value);
      const unsupportedModifiers = Boolean(tariffHfp.input.value || tariffHp.input.value ||
        icms.select.value || flag.select.value === 'true' || graceEnabled.select.value === 'true' ||
        additional.input.value);
      methodWarning.textContent = unsupportedMethod
        ? 'Este método pode ser configurado, mas ainda não é executável pelo motor atual.'
        : unsupportedModifiers
          ? 'Esta combinação de modificadores pode ser salva, mas bloqueia a execução no motor atual.'
          : method.select.value === 'energia_compensada' && tariffSource.select.value === 'manual'
            ? 'Energia compensada exige origem documental na execução atual.' : '';
      methodWarning.hidden = !methodWarning.textContent;
    }
    [method.select, tariffSource.select, basis.select, graceEnabled.select].forEach((select) =>
      select.addEventListener('change', updateConditional));
    [icms.select, flag.select].forEach((select) => select.addEventListener('change', updateConditional));
    [tariffHfp.input, tariffHp.input, additional.input].forEach((input) =>
      input.addEventListener('input', updateConditional));

    const identification = createFormSection('Identificação', name.field, description);
    const tariff = createFormSection('Método e tarifa', method.field, tariffSource.field,
      companyTariff.field, tariffHfp.field, tariffHp.field, basis.field, componentIndex.field);
    tariff.append(documentaryNote, methodWarning);
    const modifiers = createFormSection('ICMS, bandeira e condições comerciais',
      icms.field, flag.field, pis.field, graceEnabled.field, graceDuration.field,
      graceDiscount.field, additional.field);
    const advanced = createElement('details', { className: 'billing-rule-advanced' });
    advanced.open = Boolean(rule && (rule.billingModifiers.icmsPolicy ||
      rule.billingModifiers.excludeTariffFlag !== null || rule.billingModifiers.excludePisCofins !== null ||
      rule.billingModifiers.gracePeriod.enabled || rule.billingModifiers.recurringAdditionalCost));
    advanced.append(createElement('summary', { textContent: 'ICMS, bandeira e condições comerciais' }), modifiers);
    const collection = createFormSection('Cobrança e vencimento', mode.field, dueBasis.field,
      dueOffset.field, interest.field, fine.field);

    const impacts = createElement('section', { className: 'billing-rule-impact' });
    if (rule) {
      const company = assignments.filter((item) => item.scopeType === 'company').length;
      const clients = assignments.filter((item) => item.scopeType === 'client').length;
      const ucs = assignments.filter((item) => item.scopeType === 'consumer_unit').length;
      impacts.append(createElement('h3', { textContent: 'Vínculos e impacto' }), createElement('p', {
        textContent: `Vínculos ativos: empresa ${company}, clientes ${clients}, UCs diretas ${ucs}. Alterar esta regra afeta novas execuções desses vínculos; snapshots anteriores permanecem.`
      }));
    }

    const actions = createElement('div', { className: 'billing-rule-editor-actions' });
    const cancel = createElement('button', { type: 'button', className: 'secondary-button', textContent: ucId ? 'Voltar para UC' : 'Cancelar' });
    cancel.addEventListener('click', () => navigate(returnPath));
    actions.appendChild(cancel);
    if (canWrite) {
      const save = createElement('button', { type: 'submit', textContent: 'Salvar regra' });
      actions.appendChild(save);
    }

    form.append(heading, identification, tariff, advanced, collection);
    if (rule) form.appendChild(impacts);
    form.appendChild(actions);
    if (readOnly) form.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea')
      .forEach((control) => { control.disabled = true; });
    updateConditional();

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!canWrite || !form.reportValidity()) return;
      if (rule?.billingModifiers.gracePeriod.start || rule?.billingModifiers.gracePeriod.end) {
        toast.error('Esta regra tem datas de carência legadas. Revise a política antes de editar.');
        return;
      }
      const input: BillingRuleInput = {
        nome: name.input.value.trim(), descricao: descriptionInput.value.trim() || null,
        calculationMethod: method.select.value, tariffSource: tariffSource.select.value as BillingRuleInput['tariffSource'],
        discountType: 'none', discountValue: null, tariffBasis: basis.select.value,
        energyComponentIndex: basis.select.value === 'documented_component' ? Number(componentIndex.input.value) : null,
        billingMode: mode.select.value, dueDateBasis: dueBasis.select.value,
        dueDateOffsetDays: Number(dueOffset.input.value), monthlyInterest: decimalValue(interest.input),
        finePercentage: decimalValue(fine.input),
        tariffConfiguration: {
          companyTariff: decimalValue(companyTariff.input), tariffHfp: decimalValue(tariffHfp.input),
          tariffHp: decimalValue(tariffHp.input)
        },
        billingModifiers: {
          excludePisCofins: booleanValue(pis.select.value),
          icmsPolicy: icms.select.value === 'exclude' ? 'exclude' : null,
          excludeTariffFlag: booleanValue(flag.select.value),
          recurringAdditionalCost: decimalValue(additional.input),
          gracePeriod: {
            enabled: booleanValue(graceEnabled.select.value),
            withoutDiscount: graceEnabled.select.value === 'true' ? booleanValue(graceDiscount.select.value) : null,
            durationMonths: graceEnabled.select.value === 'true' && graceDuration.input.value
              ? Number(graceDuration.input.value) : null
          }
        }
      };
      const affected = assignments.length;
      if (savedId && affected && !window.confirm(
        `Esta regra tem ${affected} vínculo(s) ativo(s). Salvar altera novas execuções para os alvos vinculados. Continuar?`
      )) return;
      if (defaultFlow && !window.confirm('Definir esta regra como padrão da empresa para novas execuções?')) return;
      loading.show();
      let ruleSaved = false;
      try {
        if (savedId) {
          const changes: Partial<BillingRuleInput> = { ...input };
          delete changes.discountType;
          delete changes.discountValue;
          await updateBillingRule(savedId, changes);
        } else {
          const created = await createBillingRule(input);
          savedId = created.id;
        }
        ruleSaved = true;
        if (ucId && !id) {
          if (savedId === undefined) throw new Error('A regra ainda não foi salva.');
          const active = (await listBillingRuleAssignments({ scopeType: 'consumer_unit', consumerUnitId: String(ucId), ativo: 'true' }))[0];
          if (active?.grupoRegraCobrancaId !== savedId) {
            if (active) await updateBillingRuleAssignment(active.id, { grupoRegraCobrancaId: savedId });
            else await createBillingRuleAssignment({ grupoRegraCobrancaId: savedId, scopeType: 'consumer_unit', consumerUnitId: ucId });
          }
        }
        if (defaultFlow) {
          if (savedId === undefined) throw new Error('A regra ainda não foi salva.');
          const active = (await listBillingRuleAssignments({ scopeType: 'company', ativo: 'true' }))[0];
          if (active?.grupoRegraCobrancaId !== savedId) {
            if (active) await updateBillingRuleAssignment(active.id, { grupoRegraCobrancaId: savedId });
            else await createBillingRuleAssignment({ grupoRegraCobrancaId: savedId, scopeType: 'company' });
          }
        }
        toast.success('Regra salva.');
        navigate(returnPath);
      } catch (error) {
        const detail = error instanceof Error ? error.message : 'Tente novamente.';
        toast.error(ruleSaved && (ucId || defaultFlow)
          ? `Regra salva, mas o vínculo ${defaultFlow ? 'padrão' : 'com a UC'} falhou: ${detail}`
          : `Não foi possível salvar a regra: ${detail}`);
      } finally {
        loading.hide();
      }
    });
    content.replaceChildren(form);
  }
}
