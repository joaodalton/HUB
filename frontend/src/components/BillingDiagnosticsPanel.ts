import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { analyzeBillingPdf, type PdfDiagnostic, type PdfDiagnosticStage } from '../services/billingDiagnosticsService';
import { t } from '../services/i18nService';

function stageLabel(stage: string): string {
  const map: Record<string, string> = {
    UPLOAD: t('billing.diagnostics.stageUpload'), EXTRACTION: t('billing.diagnostics.stageExtraction'),
    NORMALIZATION: t('billing.diagnostics.stageNormalization'), UC_MATCHING: t('billing.diagnostics.stageUcMatching'),
    RULE_RESOLUTION: t('billing.diagnostics.stageRuleResolution'), TARIFF_RESOLUTION: t('billing.diagnostics.stageTariffResolution'),
    ENERGY_RESOLUTION: t('billing.diagnostics.stageEnergyResolution'), COMMERCIAL_DEDUCTIONS: t('billing.diagnostics.stageCommercialDeductions'),
    FIO_B: t('billing.diagnostics.stageFioB'), FINAL_CALCULATION: t('billing.diagnostics.stageFinalCalculation'),
    SNAPSHOT: t('billing.diagnostics.stageSnapshot')
  };
  return map[stage] ?? stage;
}

export function createBillingDiagnosticsPanel(): HTMLElement {
  const panel = createElement('section', { className: 'content-stack billing-diagnostics' });
  const toast = useToast();
  let file: File | null = null;
  let busy = false;
  let error = '';
  let result: PdfDiagnostic | null = null;

  render();
  return panel;

  async function upload(): Promise<void> {
    if (!file || busy) return;
    busy = true;
    error = '';
    result = null;
    render();
    try {
      result = await analyzeBillingPdf(file);
      file = null;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : t('billing.diagnostics.analyzeError');
    } finally {
      busy = false;
      render();
    }
  }

  function render(): void {
    const header = createElement('section', { className: 'settings-panel billing-diagnostics-card' });
    header.append(
      createElement('span', { className: 'eyebrow', textContent: t('billing.diagnostics.eyebrow') }),
      createElement('h2', { textContent: t('billing.diagnostics.title') }),
      hint(t('billing.diagnostics.intro'))
    );
    const controls = createElement('section', { className: 'settings-panel billing-diagnostics-card' });
    controls.appendChild(createElement('h3', { textContent: t('billing.diagnostics.analyzePdf') }));
    const uploadControls = createElement('div', { className: 'billing-diagnostics-upload' });
    const fileField = createElement('label', { className: 'form-field' });
    const fileInput = createElement('input', { className: 'billing-diagnostics-file' });
    fileInput.type = 'file';
    fileInput.accept = '.pdf,application/pdf';
    fileInput.disabled = busy;
    fileInput.addEventListener('change', () => { file = fileInput.files?.[0] ?? null; render(); });
    fileField.append(createElement('span', { textContent: t('billing.diagnostics.fileField') }), fileInput);
    uploadControls.append(fileField, button(t('billing.diagnostics.processPdf'), () => void upload(), busy || !file));
    controls.appendChild(uploadControls);
    if (file) controls.appendChild(hint(`${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} ${t('billing.diagnostics.sizeUnit')}`));
    if (busy) controls.appendChild(hint(t('billing.diagnostics.processing')));
    if (error) controls.appendChild(createElement('p', { className: 'importacao-error', textContent: error }));
    panel.replaceChildren(header, controls);
    if (result) panel.appendChild(renderResult(result));
  }

  function renderResult(data: PdfDiagnostic): HTMLElement {
    const output = createElement('section', { className: 'settings-panel billing-diagnostics-card' });
    const title = createElement('div', { className: 'billing-diagnostics-stage-header' });
    title.append(createElement('h3', { textContent: t('billing.diagnostics.resultTitle') }), badge(data.status));
    output.append(
      title,
      summary(t('billing.diagnostics.executionTitle'), [
        [t('billing.diagnostics.tempId'), value(data.executionId)],
        [t('billing.diagnostics.duration'), data.durationMs === null ? null : `${data.durationMs} ms`],
        [t('billing.diagnostics.file'), value(data.pdf?.name)],
        [t('billing.diagnostics.sha256'), value(data.pdf?.sha256)],
        [t('billing.diagnostics.extraction'), value(data.extractionStatus)],
        [t('billing.diagnostics.normalization'), value(data.normalizationStatus)],
        [t('billing.diagnostics.gdEligibility'), value(data.billingEligibility?.status)],
        [t('billing.diagnostics.eligibilityReason'), value(data.billingEligibility?.reason)]
      ]),
      structured(t('billing.diagnostics.pdfTechInfo'), data.pdf),
      structured(t('billing.diagnostics.extractedFields'), data.extracted),
      structured(t('billing.diagnostics.normalizedJson'), data.normalized),
      structured(t('billing.diagnostics.compensationEvents'), data.compensations),
      structured(t('billing.diagnostics.missingFields'), data.missingFields),
      structured(t('billing.diagnostics.warnings'), data.warnings),
      structured(t('billing.diagnostics.blockers'), data.blockers)
    );
    if (data.error) output.appendChild(structured(t('billing.diagnostics.technicalError'), data.error));
    const stages = createElement('div', { className: 'billing-diagnostics-details' });
    stages.appendChild(createElement('h3', { textContent: t('billing.diagnostics.processingStages') }));
    data.stages.forEach((stage) => stages.appendChild(stageCard(stage)));
    output.appendChild(stages);
    return output;
  }

  function structured(title: string, data: unknown): HTMLElement {
    const details = createElement('details', { className: 'billing-diagnostics-structured' });
    const json = JSON.stringify(data ?? null, null, 2);
    const copy = button(t('billing.diagnostics.copyJson'), () => {
      void navigator.clipboard.writeText(json).then(
        () => toast.success(t('billing.diagnostics.jsonCopied')),
        () => toast.error(t('billing.diagnostics.jsonCopyError'))
      );
    }, false);
    details.append(createElement('summary', { textContent: title }), copy, createElement('pre', { textContent: json }));
    return details;
  }
}

function stageCard(stage: PdfDiagnosticStage): HTMLElement {
  const card = createElement('section', { className: 'billing-diagnostics-stage' });
  const heading = createElement('div', { className: 'billing-diagnostics-stage-header' });
  heading.append(createElement('strong', { textContent: stageLabel(stage.stage) }), badge(stage.status));
  card.append(heading, summary(t('billing.diagnostics.executionTitle'), [
    [t('billing.diagnostics.stageTime'), stage.timestamp ? new Date(stage.timestamp).toLocaleString('pt-BR') : null],
    [t('billing.diagnostics.duration'), stage.durationMs === null ? null : `${stage.durationMs} ms`],
    [t('billing.diagnostics.stageComponent'), value(stage.component)], [t('billing.diagnostics.stageVersion'), value(stage.version)]
  ]));
  if (stage.inputs && Object.keys(stage.inputs).length) card.appendChild(jsonDetails(t('billing.diagnostics.stageInputs'), stage.inputs));
  if (stage.outputs && Object.keys(stage.outputs).length) card.appendChild(jsonDetails(t('billing.diagnostics.stageOutputs'), stage.outputs));
  if (stage.warnings?.length) card.appendChild(jsonDetails(t('billing.diagnostics.warnings'), stage.warnings));
  if (stage.blockers?.length) card.appendChild(jsonDetails(t('billing.diagnostics.blockers'), stage.blockers));
  return card;
}

function jsonDetails(title: string, data: unknown): HTMLElement {
  const details = createElement('details', { className: 'billing-diagnostics-structured' });
  details.append(createElement('summary', { textContent: title }), createElement('pre', { textContent: JSON.stringify(data, null, 2) }));
  return details;
}

function summary(title: string, rows: Array<[string, string | null]>): HTMLElement {
  const section = createElement('section', { className: 'billing-diagnostics-summary' });
  section.appendChild(createElement('h3', { textContent: title }));
  const list = createElement('dl');
  rows.forEach(([label, content]) => list.append(createElement('dt', { textContent: label }), createElement('dd', { textContent: content ?? '—' })));
  section.appendChild(list);
  return section;
}

function button(label: string, action: () => void, disabled: boolean): HTMLButtonElement {
  const element = createElement('button', { className: 'secondary-button', type: 'button', textContent: label });
  element.disabled = disabled;
  element.addEventListener('click', action);
  return element;
}

function badge(status: string): HTMLElement {
  const tone = status === 'SUCCESS' || status === 'NORMALIZED' ? 'success'
    : status === 'FAILED' || status === 'ERROR' ? 'danger' : status === 'NOT_EXECUTED' || status === 'SKIPPED' ? 'neutral' : 'warning';
  return createElement('span', { className: `billing-diagnostics-badge tone-${tone}`, textContent: status });
}

function hint(text: string): HTMLElement { return createElement('p', { className: 'settings-hint', textContent: text }); }
function value(raw: unknown): string | null { return raw === null || raw === undefined ? null : String(raw); }
