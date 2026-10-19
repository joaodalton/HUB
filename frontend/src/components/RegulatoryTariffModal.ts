import { createElement } from '../dom';
import { confirmRegulatoryTariffs, previewRegulatoryTariffs, previewRegulatoryTariffsFromCkan, type RegulatoryTariffPreview } from '../services/regulatoryTariffsService';

const REGULATORY_TARIFF_MAX_BYTES = 100 * 1024 * 1024;

function formatFileSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MiB`;
}

export function createRegulatoryTariffModal(onImported: () => Promise<void>): HTMLElement {
  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const overlay = createElement('div', { className: 'modal-overlay importacoes-modal-overlay' });
  const card = createElement('section', { className: 'importacoes-modal-card' });
  card.setAttribute('role', 'dialog'); card.setAttribute('aria-modal', 'true'); card.setAttribute('aria-label', 'Atualizar base tarifária ANEEL');
  const header = createElement('header', { className: 'modal-header' });
  const close = createElement('button', { className: 'modal-close', type: 'button', textContent: '×' });
  close.setAttribute('aria-label', 'Fechar atualização tarifária');
  const dismiss = () => { overlay.remove(); opener?.focus(); };
  close.addEventListener('click', dismiss);
  header.append(createElement('h2', { textContent: 'Atualizar base tarifária ANEEL' }), close);
  const body = createElement('div', { className: 'content-stack' });
  const instruction = createElement('p', { className: 'settings-hint', textContent: '1. Baixe o CSV oficial de Componentes Tarifárias. 2. Envie o arquivo para prévia. 3. Confirme somente sem conflitos.' });
  const method = createElement('select', { className: 'regulatory-tariff-control' }) as HTMLSelectElement;
  method.setAttribute('aria-label', 'Método de atualização ANEEL');
  method.append(new Option('Sincronizar pela API', 'ckan'), new Option('Importar CSV', 'csv'));
  const ckanFields = createElement('div', { className: 'content-stack' });
  const distributor = createElement('select', { className: 'regulatory-tariff-control' }) as HTMLSelectElement;
  distributor.setAttribute('aria-label', 'Distribuidora');
  distributor.appendChild(new Option('COPEL-DIS', 'COPEL-DIS'));
  const year = createElement('input', { className: 'regulatory-tariff-control' }) as HTMLInputElement;
  year.type = 'number'; year.value = '2026'; year.min = '2010'; year.max = String(new Date().getFullYear() + 1);
  year.setAttribute('aria-label', 'Ano do recurso ANEEL');
  ckanFields.append(createElement('p', { className: 'settings-hint', textContent: 'Distribuidora: COPEL-DIS. Período: recurso anual da ANEEL.' }), distributor, year);
  const csvFields = createElement('div', { className: 'content-stack' });
  const link = createElement('a', { className: 'secondary-button', textContent: 'Abrir portal oficial da ANEEL' }) as HTMLAnchorElement;
  link.href = 'https://dadosabertos.aneel.gov.br/dataset/componentes-tarifarias'; link.target = '_blank'; link.rel = 'noreferrer';
  const sourceUrl = createElement('input') as HTMLInputElement;
  sourceUrl.type = 'url'; sourceUrl.placeholder = 'URL do recurso oficial baixado'; sourceUrl.required = true;
  sourceUrl.setAttribute('aria-label', 'URL do recurso oficial ANEEL');
  const file = createElement('input') as HTMLInputElement;
  file.type = 'file'; file.accept = '.csv,text/csv'; file.setAttribute('aria-label', 'Arquivo CSV ANEEL');
  const fileInfo = createElement('p', { className: 'settings-hint', textContent: 'Limite: 100 MiB.' });
  const previewButton = createElement('button', { type: 'button', textContent: 'Validar e visualizar' });
  const result = createElement('div', { className: 'importacao-problemas' });
  let preview: RegulatoryTariffPreview | null = null;
  const syncMethod = () => {
    const fromApi = method.value === 'ckan';
    ckanFields.hidden = !fromApi; csvFields.hidden = fromApi;
    instruction.textContent = fromApi
      ? 'Consulte a fonte oficial, revise a prévia e confirme somente sem conflitos.'
      : 'Baixe o CSV oficial de Componentes Tarifárias, envie para prévia e confirme somente sem conflitos.';
  };
  const invalidate = () => {
    preview = null; result.replaceChildren();
    const selected = file.files?.[0];
    fileInfo.textContent = selected ? `${selected.name} (${formatFileSize(selected.size)})` : 'Limite: 100 MiB.';
  };
  file.addEventListener('change', invalidate);
  sourceUrl.addEventListener('input', invalidate);
  method.addEventListener('change', () => { invalidate(); syncMethod(); });
  distributor.addEventListener('change', invalidate); year.addEventListener('input', invalidate);
  previewButton.addEventListener('click', async () => {
    const selected = file.files?.[0];
    if (method.value === 'csv' && !selected) { file.focus(); return; }
    if (selected && selected.size > REGULATORY_TARIFF_MAX_BYTES) {
      result.replaceChildren(createElement('p', { className: 'importacao-error', textContent: 'Arquivo excede o limite de 100 MiB.' }));
      return;
    }
    if (method.value === 'csv' && !sourceUrl.checkValidity()) { sourceUrl.reportValidity(); return; }
    previewButton.disabled = true; file.disabled = true; sourceUrl.disabled = true; method.disabled = true; distributor.disabled = true; year.disabled = true;
    previewButton.textContent = method.value === 'ckan' ? 'Consultando e validando registros...' : 'Enviando e processando...'; result.textContent = '';
    try {
      preview = method.value === 'ckan'
        ? await previewRegulatoryTariffsFromCkan(distributor.value, Number(year.value))
        : await previewRegulatoryTariffs(selected!, sourceUrl.value.trim());
      renderPreview();
    }
    catch (error) {
      const message = error instanceof Error && (/100 MiB|413/.test(error.message)) ? 'Arquivo excede o limite de 100 MiB.'
        : error instanceof TypeError ? 'Não foi possível enviar o arquivo. Verifique a conexão e tente novamente.'
        : error instanceof Error ? error.message : 'Não foi possível validar o arquivo.';
      result.appendChild(createElement('p', { className: 'importacao-error', textContent: message }));
    }
    finally { previewButton.disabled = false; file.disabled = false; sourceUrl.disabled = false; method.disabled = false; distributor.disabled = false; year.disabled = false; previewButton.textContent = 'Validar e visualizar'; }
  });
  function renderPreview(): void {
    if (!preview) return;
    const counts = createElement('p', { className: preview.status === 'ready' ? 'importacao-ready' : 'importacao-error', textContent: `Válidos: ${preview.validos}; ignorados: ${preview.ignorados}; duplicados: ${preview.duplicados}; conflitos: ${preview.conflitos}; rejeitados: ${preview.rejeitados}.` });
    const list = createElement('ul');
    preview.linhas.slice(0, 20).forEach((row) => list.appendChild(createElement('li', { textContent: row.motivo ?? `${row.official_distributor ?? ''} ${row.component ?? ''} — ${row.situacao}` })));
    const confirm = createElement('button', { type: 'button', textContent: 'Confirmar importação' });
    confirm.disabled = preview.status !== 'ready';
    confirm.addEventListener('click', async () => {
      if (!preview) return; confirm.disabled = true; confirm.textContent = 'Publicando...';
      try { const done = await confirmRegulatoryTariffs(preview.previewId); result.replaceChildren(createElement('p', { className: 'importacao-ready', textContent: `Importação concluída: ${done.created} adicionada(s), ${done.unchanged} mantida(s).` })); await onImported(); }
      catch (error) { confirm.disabled = false; confirm.textContent = 'Confirmar importação'; result.appendChild(createElement('p', { className: 'importacao-error', textContent: error instanceof Error ? error.message : 'Não foi possível confirmar.' })); }
    });
    const source = preview.ckan ? createElement('p', { className: 'settings-hint', textContent: `CKAN: recurso ${preview.ckan.resourceId}; ${preview.ckan.found} registro(s) encontrado(s).` }) : null;
    result.replaceChildren(counts, ...(source ? [source] : []), list, confirm);
  }
  overlay.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { dismiss(); return; }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(card.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input:not([disabled])'));
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  csvFields.append(link, sourceUrl, file, fileInfo); syncMethod();
  body.append(instruction, method, ckanFields, csvFields, previewButton, result); card.append(header, body); overlay.appendChild(card);
  queueMicrotask(() => close.focus());
  return overlay;
}
