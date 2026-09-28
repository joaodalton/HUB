import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { analyzeBillingPdf, type PdfDiagnostic, type PdfDiagnosticStage } from '../services/billingDiagnosticsService';

const STAGES: Record<string, string> = {
  UPLOAD: 'Upload', EXTRACTION: 'Extração', NORMALIZATION: 'Normalização', UC_MATCHING: 'Identificação da UC',
  RULE_RESOLUTION: 'Regra comercial', TARIFF_RESOLUTION: 'Tarifa', ENERGY_RESOLUTION: 'Energia elegível',
  COMMERCIAL_DEDUCTIONS: 'Deduções comerciais', FIO_B: 'Fio B', FINAL_CALCULATION: 'Cálculo final', SNAPSHOT: 'Snapshot'
};

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
      error = cause instanceof Error ? cause.message : 'Não foi possível analisar o PDF.';
    } finally {
      busy = false;
      render();
    }
  }

  function render(): void {
    const header = createElement('section', { className: 'settings-panel billing-diagnostics-card' });
    header.append(
      createElement('span', { className: 'eyebrow', textContent: 'Configurações · Administração' }),
      createElement('h2', { textContent: 'Diagnóstico do motor' }),
      hint('Laboratório técnico: analise a extração e normalização de um PDF Copel. Nenhum cadastro ou cobrança é criado.')
    );
    const controls = createElement('section', { className: 'settings-panel billing-diagnostics-card' });
    controls.appendChild(createElement('h3', { textContent: 'Analisar PDF' }));
    const uploadControls = createElement('div', { className: 'billing-diagnostics-upload' });
    const fileField = createElement('label', { className: 'form-field' });
    const fileInput = createElement('input', { className: 'billing-diagnostics-file' });
    fileInput.type = 'file';
    fileInput.accept = '.pdf,application/pdf';
    fileInput.disabled = busy;
    fileInput.addEventListener('change', () => { file = fileInput.files?.[0] ?? null; render(); });
    fileField.append(createElement('span', { textContent: 'Arquivo PDF' }), fileInput);
    uploadControls.append(fileField, button('Processar PDF', () => void upload(), busy || !file));
    controls.appendChild(uploadControls);
    if (file) controls.appendChild(hint(`${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MiB`));
    if (busy) controls.appendChild(hint('Enviando e processando PDF… O resultado será exibido após a normalização.'));
    if (error) controls.appendChild(createElement('p', { className: 'importacao-error', textContent: error }));
    panel.replaceChildren(header, controls);
    if (result) panel.appendChild(renderResult(result));
  }

  function renderResult(data: PdfDiagnostic): HTMLElement {
    const output = createElement('section', { className: 'settings-panel billing-diagnostics-card' });
    const title = createElement('div', { className: 'billing-diagnostics-stage-header' });
    title.append(createElement('h3', { textContent: 'Resultado técnico' }), badge(data.status));
    output.append(
      title,
      summary('Execução', [
        ['Identificador temporário', value(data.executionId)],
        ['Duração', data.durationMs === null ? null : `${data.durationMs} ms`],
        ['Arquivo', value(data.pdf?.name)],
        ['SHA-256', value(data.pdf?.sha256)],
        ['Extração', value(data.extractionStatus)],
        ['Normalização', value(data.normalizationStatus)],
        ['Elegibilidade GD', value(data.billingEligibility?.status)],
        ['Motivo da elegibilidade', value(data.billingEligibility?.reason)]
      ]),
      structured('Informações técnicas do PDF', data.pdf),
      structured('Campos extraídos', data.extracted),
      structured('JSON normalizado', data.normalized),
      structured('Eventos de compensação', data.compensations),
      structured('Campos não identificados', data.missingFields),
      structured('Warnings', data.warnings),
      structured('Blockers', data.blockers)
    );
    if (data.error) output.appendChild(structured('Erro técnico', data.error));
    const stages = createElement('div', { className: 'billing-diagnostics-details' });
    stages.appendChild(createElement('h3', { textContent: 'Etapas do processamento' }));
    data.stages.forEach((stage) => stages.appendChild(stageCard(stage)));
    output.appendChild(stages);
    return output;
  }

  function structured(title: string, data: unknown): HTMLElement {
    const details = createElement('details', { className: 'billing-diagnostics-structured' });
    const json = JSON.stringify(data ?? null, null, 2);
    const copy = button('Copiar JSON', () => {
      void navigator.clipboard.writeText(json).then(
        () => toast.success('JSON copiado.'),
        () => toast.error('Não foi possível copiar o JSON.')
      );
    }, false);
    details.append(createElement('summary', { textContent: title }), copy, createElement('pre', { textContent: json }));
    return details;
  }
}

function stageCard(stage: PdfDiagnosticStage): HTMLElement {
  const card = createElement('section', { className: 'billing-diagnostics-stage' });
  const heading = createElement('div', { className: 'billing-diagnostics-stage-header' });
  heading.append(createElement('strong', { textContent: STAGES[stage.stage] ?? stage.stage }), badge(stage.status));
  card.append(heading, summary('Execução', [
    ['Horário', stage.timestamp ? new Date(stage.timestamp).toLocaleString('pt-BR') : null],
    ['Duração', stage.durationMs === null ? null : `${stage.durationMs} ms`],
    ['Componente', value(stage.component)], ['Versão', value(stage.version)]
  ]));
  if (stage.inputs && Object.keys(stage.inputs).length) card.appendChild(jsonDetails('Entradas', stage.inputs));
  if (stage.outputs && Object.keys(stage.outputs).length) card.appendChild(jsonDetails('Saídas', stage.outputs));
  if (stage.warnings?.length) card.appendChild(jsonDetails('Warnings', stage.warnings));
  if (stage.blockers?.length) card.appendChild(jsonDetails('Blockers', stage.blockers));
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
