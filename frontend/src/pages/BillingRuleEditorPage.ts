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
import { t } from '../services/i18nService';

function METHODS(): string[][] {
  return [
    ['energia_compensada', t('billing.ruleEditor.methodEnergiaCompensada')], ['energia_recebida', t('billing.ruleEditor.methodEnergiaRecebida')],
    ['valor_total_fatura', t('billing.ruleEditor.methodValorTotalFatura')], ['tarifa_fixa', t('billing.ruleEditor.methodTarifaFixa')],
    ['tarifa_fixa_com_desconto', t('billing.ruleEditor.methodTarifaFixaComDesconto')], ['tarifa_especifica', t('billing.ruleEditor.methodTarifaEspecifica')],
    ['economia_gerada', t('billing.ruleEditor.methodEconomiaGerada')]
  ];
}
function TARIFF_SOURCES(): string[][] {
  return [['invoice', t('billing.ruleEditor.sourceInvoice')], ['manual', t('billing.ruleEditor.sourceManual')]];
}
function BASES(): string[][] {
  return [
    ['compensated', t('billing.ruleEditor.basisCompensated')], ['consumed', t('billing.ruleEditor.basisConsumed')],
    ['gd1', t('billing.ruleEditor.basisGd1')], ['gd2', t('billing.ruleEditor.basisGd2')], ['documented_component', t('billing.ruleEditor.basisDocumentedComponent')]
  ];
}
function MODES(): string[][] {
  return [['auto', t('billing.ruleEditor.modeAuto')], ['unified', t('billing.ruleEditor.modeUnified')], ['separate', t('billing.ruleEditor.modeSeparate')]];
}
function DUE_BASES(): string[][] {
  return [
    ['invoice_due_date', t('billing.ruleEditor.dueInvoiceDueDate')], ['invoice_issue_date', t('billing.ruleEditor.dueInvoiceIssueDate')],
    ['reading_date', t('billing.ruleEditor.dueReadingDate')], ['calculation_date', t('billing.ruleEditor.dueCalculationDate')]
  ];
}

function options(values: string[][]): Array<{ value: string; label: string }> {
  return [{ value: '', label: t('billing.ruleEditor.select') }, ...values.map(([value, label]) => ({ value, label }))];
}

function help(field: HTMLElement, label: string, explanation: string): void {
  field.querySelector('span')?.appendChild(createContextHelp(label, explanation));
}

function decimalField(label: string, value: string | null) {
  const control = createInput(label, 'text', value ?? '');
  control.input.inputMode = 'decimal';
  control.input.pattern = '-?[0-9]{1,12}(\\.[0-9]{1,6})?';
  control.input.title = t('billing.ruleEditor.decimalTooltip');
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
  const layout = createBaseLayout({ content, eyebrow: t('billing.ruleEditor.eyebrow'), title: id ? t('billing.ruleEditor.titleEdit') : t('billing.ruleEditor.titleNew') });
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
        textContent: error instanceof Error ? error.message : t('billing.ruleEditor.loadError')
      }));
    } finally {
      loading.hide();
    }
  }

  function render(): void {
    const readOnly = !canWrite;
    const form = createElement('form', { className: 'billing-rule-form' });
    const heading = createElement('div', { className: 'billing-rule-editor-heading' });
    const breadcrumb = createElement('a', { textContent: t('billing.ruleEditor.breadcrumb') });
    breadcrumb.href = '/regras-cobranca';
    breadcrumb.addEventListener('click', (event) => { event.preventDefault(); navigate('/regras-cobranca'); });
    heading.append(breadcrumb, document.createTextNode(` / ${id ? t('billing.ruleEditor.titleEdit') : t('billing.ruleEditor.titleNew')}`));
    const status = createElement('span', {
      className: 'status-badge tone-info',
      textContent: rule ? rule.ativo ? t('billing.ruleEditor.statusActive') : t('billing.ruleEditor.statusInactive') : t('billing.ruleEditor.statusNew')
    });
    heading.appendChild(status);
    if (defaultFlow) heading.appendChild(createElement('span', {
      textContent: t('billing.ruleEditor.defaultFlowNote')
    }));

    const name = createInput(t('billing.ruleEditor.fieldNome'), 'text', rule?.nome ?? '', true);
    name.input.maxLength = 150;
    const description = createElement('label', { className: 'form-field form-field-wide' });
    const descriptionInput = createElement('textarea');
    descriptionInput.value = rule?.descricao ?? '';
    description.append(createElement('span', { textContent: t('billing.ruleEditor.fieldDescricao') }), descriptionInput);

    const method = createSelectField(t('billing.ruleEditor.fieldMetodoTarifario'), rule?.calculationMethod ?? '', options(METHODS()));
    method.select.required = true;
    help(method.field, t('billing.ruleEditor.fieldMetodoTarifario'), t('billing.ruleEditor.helpMetodoTarifario'));
    const tariffSource = createSelectField(t('billing.ruleEditor.fieldOrigemTarifa'), rule?.tariffSource ?? '', options(TARIFF_SOURCES()));
    tariffSource.select.required = true;
    const companyTariff = decimalField(t('billing.ruleEditor.fieldTarifaEmpresa'), rule?.tariffConfiguration.companyTariff ?? null);
    help(companyTariff.field, t('billing.ruleEditor.fieldTarifaEmpresa'), t('billing.ruleEditor.helpTarifaEmpresa'));
    const tariffHfp = decimalField(t('billing.ruleEditor.fieldTarifaHfp'), rule?.tariffConfiguration.tariffHfp ?? null);
    const tariffHp = decimalField(t('billing.ruleEditor.fieldTarifaHp'), rule?.tariffConfiguration.tariffHp ?? null);
    const basis = createSelectField(t('billing.ruleEditor.fieldBaseEnergetica'), rule?.tariffBasis ?? '', options(BASES()));
    basis.select.required = true;
    const componentIndex = createInput(t('billing.ruleEditor.fieldIndiceComponente'), 'number', rule?.energyComponentIndex?.toString() ?? '');
    componentIndex.input.min = '0';
    componentIndex.input.step = '1';
    const documentaryNote = createElement('p', {
      className: 'billing-rule-note',
      textContent: t('billing.ruleEditor.documentaryNote')
    });

    const icms = createSelectField(t('billing.ruleEditor.fieldIcms'), rule?.billingModifiers.icmsPolicy ?? '', [
      { value: '', label: t('billing.ruleEditor.icmsNotConfigured') }, { value: 'exclude', label: t('billing.ruleEditor.icmsExclude') }
    ]);
    help(icms.field, t('billing.ruleEditor.fieldIcms'), t('billing.ruleEditor.helpIcms'));
    const flag = createSelectField(t('billing.ruleEditor.fieldBandeira'), String(rule?.billingModifiers.excludeTariffFlag ?? ''), [
      { value: '', label: t('billing.ruleEditor.icmsNotConfigured') }, { value: 'true', label: t('billing.ruleEditor.flagSemBandeira') },
      { value: 'false', label: t('billing.ruleEditor.flagComBandeira') }
    ]);
    help(flag.field, t('billing.ruleEditor.fieldBandeira'), t('billing.ruleEditor.helpBandeira'));
    const pis = createSelectField(t('billing.ruleEditor.fieldPisCofins'), String(rule?.billingModifiers.excludePisCofins ?? ''), [
      { value: '', label: t('billing.ruleEditor.icmsNotConfigured') }, { value: 'true', label: t('billing.ruleEditor.pisExcludeWithProof') },
      { value: 'false', label: t('billing.ruleEditor.pisNotExclude') }
    ]);
    help(pis.field, t('billing.ruleEditor.fieldPisCofins'), t('billing.ruleEditor.helpPisCofins'));
    const graceEnabled = createSelectField(t('billing.ruleEditor.fieldCarencia'), String(rule?.billingModifiers.gracePeriod.enabled ?? ''), [
      { value: '', label: t('billing.ruleEditor.carenciaNotConfigured') }, { value: 'true', label: t('billing.ruleEditor.carenciaActive') }, { value: 'false', label: t('billing.ruleEditor.carenciaInactive') }
    ]);
    const graceDuration = createInput(t('billing.ruleEditor.fieldCarenciaDuracao'), 'number', rule?.billingModifiers.gracePeriod.durationMonths?.toString() ?? '');
    graceDuration.input.min = '1';
    graceDuration.input.step = '1';
    const graceDiscount = createSelectField(t('billing.ruleEditor.fieldCarenciaSemDesconto'), String(rule?.billingModifiers.gracePeriod.withoutDiscount ?? ''), [
      { value: '', label: t('billing.ruleEditor.icmsNotConfigured') }, { value: 'true', label: t('billing.ruleEditor.yes') }, { value: 'false', label: t('billing.ruleEditor.no') }
    ]);
    const additional = decimalField(t('billing.ruleEditor.fieldAdicionalRecorrente'), rule?.billingModifiers.recurringAdditionalCost ?? null);
    help(additional.field, t('billing.ruleEditor.fieldAdicionalRecorrente'), t('billing.ruleEditor.helpAdicionalRecorrente'));

    const mode = createSelectField(t('billing.ruleEditor.fieldModoCobranca'), rule?.billingMode ?? '', options(MODES()));
    mode.select.required = true;
    const dueBasis = createSelectField(t('billing.ruleEditor.fieldBaseVencimento'), rule?.dueDateBasis ?? '', options(DUE_BASES()));
    dueBasis.select.required = true;
    const dueOffset = createInput(t('billing.ruleEditor.fieldDeslocamentoVencimento'), 'number', rule?.dueDateOffsetDays?.toString() ?? '');
    dueOffset.input.required = true;
    dueOffset.input.step = '1';
    const interest = decimalField(t('billing.ruleEditor.fieldJurosMensais'), rule?.monthlyInterest ?? null);
    const fine = decimalField(t('billing.ruleEditor.fieldMulta'), rule?.finePercentage ?? null);

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
        ? t('billing.ruleEditor.warningUnsupportedMethod')
        : unsupportedModifiers
          ? t('billing.ruleEditor.warningUnsupportedModifiers')
          : method.select.value === 'energia_compensada' && tariffSource.select.value === 'manual'
            ? t('billing.ruleEditor.warningCompensadaManual') : '';
      methodWarning.hidden = !methodWarning.textContent;
    }
    [method.select, tariffSource.select, basis.select, graceEnabled.select].forEach((select) =>
      select.addEventListener('change', updateConditional));
    [icms.select, flag.select].forEach((select) => select.addEventListener('change', updateConditional));
    [tariffHfp.input, tariffHp.input, additional.input].forEach((input) =>
      input.addEventListener('input', updateConditional));

    const identification = createFormSection(t('billing.ruleEditor.sectionIdentificacao'), name.field, description);
    const tariff = createFormSection(t('billing.ruleEditor.sectionMetodoTarifa'), method.field, tariffSource.field,
      companyTariff.field, tariffHfp.field, tariffHp.field, basis.field, componentIndex.field);
    tariff.append(documentaryNote, methodWarning);
    const modifiers = createFormSection(t('billing.ruleEditor.sectionIcmsBandeira'),
      icms.field, flag.field, pis.field, graceEnabled.field, graceDuration.field,
      graceDiscount.field, additional.field);
    const advanced = createElement('details', { className: 'billing-rule-advanced' });
    advanced.open = Boolean(rule && (rule.billingModifiers.icmsPolicy ||
      rule.billingModifiers.excludeTariffFlag !== null || rule.billingModifiers.excludePisCofins !== null ||
      rule.billingModifiers.gracePeriod.enabled || rule.billingModifiers.recurringAdditionalCost));
    advanced.append(createElement('summary', { textContent: t('billing.ruleEditor.sectionIcmsBandeira') }), modifiers);
    const collection = createFormSection(t('billing.ruleEditor.sectionCobrancaVencimento'), mode.field, dueBasis.field,
      dueOffset.field, interest.field, fine.field);

    const impacts = createElement('section', { className: 'billing-rule-impact' });
    if (rule) {
      const company = assignments.filter((item) => item.scopeType === 'company').length;
      const clients = assignments.filter((item) => item.scopeType === 'client').length;
      const ucs = assignments.filter((item) => item.scopeType === 'consumer_unit').length;
      impacts.append(createElement('h3', { textContent: t('billing.ruleEditor.impactTitle') }), createElement('p', {
        textContent: t('billing.ruleEditor.impactTextTemplate')
          .replace('{company}', String(company)).replace('{clients}', String(clients)).replace('{ucs}', String(ucs))
      }));
    }

    const actions = createElement('div', { className: 'billing-rule-editor-actions' });
    const cancel = createElement('button', { type: 'button', className: 'secondary-button', textContent: ucId ? t('billing.ruleEditor.backToUc') : t('billing.ruleEditor.cancel') });
    cancel.addEventListener('click', () => navigate(returnPath));
    actions.appendChild(cancel);
    if (canWrite) {
      const save = createElement('button', { type: 'submit', textContent: t('billing.ruleEditor.saveRule') });
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
        toast.error(t('billing.ruleEditor.legacyGraceError'));
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
        t('billing.ruleEditor.confirmAssignmentsTemplate').replace('{count}', String(affected))
      )) return;
      if (defaultFlow && !window.confirm(t('billing.ruleEditor.confirmDefault'))) return;
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
          if (savedId === undefined) throw new Error(t('billing.ruleEditor.notSavedYetError'));
          const active = (await listBillingRuleAssignments({ scopeType: 'consumer_unit', consumerUnitId: String(ucId), ativo: 'true' }))[0];
          if (active?.grupoRegraCobrancaId !== savedId) {
            if (active) await updateBillingRuleAssignment(active.id, { grupoRegraCobrancaId: savedId });
            else await createBillingRuleAssignment({ grupoRegraCobrancaId: savedId, scopeType: 'consumer_unit', consumerUnitId: ucId });
          }
        }
        if (defaultFlow) {
          if (savedId === undefined) throw new Error(t('billing.ruleEditor.notSavedYetError'));
          const active = (await listBillingRuleAssignments({ scopeType: 'company', ativo: 'true' }))[0];
          if (active?.grupoRegraCobrancaId !== savedId) {
            if (active) await updateBillingRuleAssignment(active.id, { grupoRegraCobrancaId: savedId });
            else await createBillingRuleAssignment({ grupoRegraCobrancaId: savedId, scopeType: 'company' });
          }
        }
        toast.success(t('billing.ruleEditor.ruleSaved'));
        navigate(returnPath);
      } catch (error) {
        const detail = error instanceof Error ? error.message : t('billing.ruleEditor.tryAgain');
        toast.error(ruleSaved && (ucId || defaultFlow)
          ? t('billing.ruleEditor.savedButLinkFailedTemplate').replace('{type}', defaultFlow ? t('billing.ruleEditor.defaultLinkLabel') : t('billing.ruleEditor.ucLinkLabel')).replace('{detail}', detail)
          : t('billing.ruleEditor.saveErrorTemplate').replace('{detail}', detail));
      } finally {
        loading.hide();
      }
    });
    content.replaceChildren(form);
  }
}
