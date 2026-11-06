import { createElement } from '../dom';
import { confirmRegulatoryTariffs, previewRegulatoryTariffs, previewRegulatoryTariffsFromCkan, type RegulatoryTariffPreview } from '../services/regulatoryTariffsService';
import { t } from '../services/i18nService';

const REGULATORY_TARIFF_MAX_BYTES = 100 * 1024 * 1024;

function formatFileSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MiB`;
}

export function createRegulatoryTariffModal(onImported: () => Promise<void>): HTMLElement {
  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const overlay = createElement('div', { className: 'modal-overlay importacoes-modal-overlay' });
  const card = createElement('section', { className: 'importacoes-modal-card' });
  card.setAttribute('role', 'dialog'); card.setAttribute('aria-modal', 'true'); card.setAttribute('aria-label', t('billing.tariffModal.ariaLabel'));
  const header = createElement('header', { className: 'modal-header' });
  const close = createElement('button', { className: 'modal-close', type: 'button', textContent: '×' });
  close.setAttribute('aria-label', t('billing.tariffModal.closeAriaLabel'));
  const dismiss = () => { overlay.remove(); opener?.focus(); };
  close.addEventListener('click', dismiss);
  header.append(createElement('h2', { textContent: t('billing.tariffModal.title') }), close);
  const body = createElement('div', { className: 'content-stack' });
  const instruction = createElement('p', { className: 'settings-hint', textContent: t('billing.tariffModal.instruction') });
  const method = createElement('select', { className: 'regulatory-tariff-control' }) as HTMLSelectElement;
  method.setAttribute('aria-label', t('billing.tariffModal.methodAriaLabel'));
  method.append(new Option(t('billing.tariffModal.syncViaApi'), 'ckan'), new Option(t('billing.tariffModal.importCsv'), 'csv'));
  const ckanFields = createElement('div', { className: 'content-stack' });
  const distributor = createElement('select', { className: 'regulatory-tariff-control' }) as HTMLSelectElement;
  distributor.setAttribute('aria-label', t('billing.tariffModal.distributorAriaLabel'));
  distributor.appendChild(new Option('COPEL-DIS', 'COPEL-DIS'));
  const year = createElement('input', { className: 'regulatory-tariff-control' }) as HTMLInputElement;
  year.type = 'number'; year.value = '2026'; year.min = '2010'; year.max = String(new Date().getFullYear() + 1);
  year.setAttribute('aria-label', t('billing.tariffModal.yearAriaLabel'));
  ckanFields.append(createElement('p', { className: 'settings-hint', textContent: t('billing.tariffModal.ckanHint') }), distributor, year);
  const csvFields = createElement('div', { className: 'content-stack' });
  const link = createElement('a', { className: 'secondary-button', textContent: t('billing.tariffModal.openOfficialPortal') }) as HTMLAnchorElement;
  link.href = 'https://dadosabertos.aneel.gov.br/dataset/componentes-tarifarias'; link.target = '_blank'; link.rel = 'noreferrer';
  const sourceUrl = createElement('input') as HTMLInputElement;
  sourceUrl.type = 'url'; sourceUrl.placeholder = t('billing.tariffModal.sourceUrlPlaceholder'); sourceUrl.required = true;
  sourceUrl.setAttribute('aria-label', t('billing.tariffModal.sourceUrlAriaLabel'));
  const file = createElement('input') as HTMLInputElement;
  file.type = 'file'; file.accept = '.csv,text/csv'; file.setAttribute('aria-label', t('billing.tariffModal.fileAriaLabel'));
  const fileInfo = createElement('p', { className: 'settings-hint', textContent: t('billing.tariffModal.sizeLimit') });
  const previewButton = createElement('button', { type: 'button', textContent: t('billing.tariffModal.validateAndPreview') });
  const result = createElement('div', { className: 'importacao-problemas' });
  let preview: RegulatoryTariffPreview | null = null;
  const syncMethod = () => {
    const fromApi = method.value === 'ckan';
    ckanFields.hidden = !fromApi; csvFields.hidden = fromApi;
    instruction.textContent = fromApi
      ? t('billing.tariffModal.syncInstruction')
      : t('billing.tariffModal.csvInstruction');
  };
  const invalidate = () => {
    preview = null; result.replaceChildren();
    const selected = file.files?.[0];
    fileInfo.textContent = selected ? `${selected.name} (${formatFileSize(selected.size)})` : t('billing.tariffModal.sizeLimit');
  };
  file.addEventListener('change', invalidate);
  sourceUrl.addEventListener('input', invalidate);
  method.addEventListener('change', () => { invalidate(); syncMethod(); });
  distributor.addEventListener('change', invalidate); year.addEventListener('input', invalidate);
  previewButton.addEventListener('click', async () => {
    const selected = file.files?.[0];
    if (method.value === 'csv' && !selected) { file.focus(); return; }
    if (selected && selected.size > REGULATORY_TARIFF_MAX_BYTES) {
      result.replaceChildren(createElement('p', { className: 'importacao-error', textContent: t('billing.tariffModal.fileOverLimit') }));
      return;
    }
    if (method.value === 'csv' && !sourceUrl.checkValidity()) { sourceUrl.reportValidity(); return; }
    previewButton.disabled = true; file.disabled = true; sourceUrl.disabled = true; method.disabled = true; distributor.disabled = true; year.disabled = true;
    previewButton.textContent = method.value === 'ckan' ? t('billing.tariffModal.checkingAndValidating') : t('billing.tariffModal.sendingAndProcessing'); result.textContent = '';
    try {
      preview = method.value === 'ckan'
        ? await previewRegulatoryTariffsFromCkan(distributor.value, Number(year.value))
        : await previewRegulatoryTariffs(selected!, sourceUrl.value.trim());
      renderPreview();
    }
    catch (error) {
      const message = error instanceof Error && (/100 MiB|413/.test(error.message)) ? t('billing.tariffModal.fileOverLimit')
        : error instanceof TypeError ? t('billing.tariffModal.uploadConnectionError')
        : error instanceof Error ? error.message : t('billing.tariffModal.validateError');
      result.appendChild(createElement('p', { className: 'importacao-error', textContent: message }));
    }
    finally { previewButton.disabled = false; file.disabled = false; sourceUrl.disabled = false; method.disabled = false; distributor.disabled = false; year.disabled = false; previewButton.textContent = t('billing.tariffModal.validateAndPreview'); }
  });
  function renderPreview(): void {
    if (!preview) return;
    const counts = createElement('p', { className: preview.status === 'ready' ? 'importacao-ready' : 'importacao-error', textContent: t('billing.tariffModal.previewCountsTemplate')
      .replace('{validos}', String(preview.validos)).replace('{ignorados}', String(preview.ignorados))
      .replace('{duplicados}', String(preview.duplicados)).replace('{conflitos}', String(preview.conflitos))
      .replace('{rejeitados}', String(preview.rejeitados)) });
    const list = createElement('ul');
    preview.linhas.slice(0, 20).forEach((row) => list.appendChild(createElement('li', { textContent: row.motivo ?? `${row.official_distributor ?? ''} ${row.component ?? ''} — ${row.situacao}` })));
    const confirm = createElement('button', { type: 'button', textContent: t('billing.tariffModal.confirmImport') });
    confirm.disabled = preview.status !== 'ready';
    confirm.addEventListener('click', async () => {
      if (!preview) return; confirm.disabled = true; confirm.textContent = t('billing.tariffModal.publishing');
      try {
        const done = await confirmRegulatoryTariffs(preview.previewId);
        result.replaceChildren(createElement('p', { className: 'importacao-ready', textContent: t('billing.tariffModal.importDoneTemplate').replace('{created}', String(done.created)).replace('{unchanged}', String(done.unchanged)) }));
        await onImported();
      }
      catch (error) { confirm.disabled = false; confirm.textContent = t('billing.tariffModal.confirmImport'); result.appendChild(createElement('p', { className: 'importacao-error', textContent: error instanceof Error ? error.message : t('billing.tariffModal.confirmError') })); }
    });
    const source = preview.ckan ? createElement('p', { className: 'settings-hint', textContent: t('billing.tariffModal.ckanSourceTemplate').replace('{resourceId}', String(preview.ckan.resourceId)).replace('{found}', String(preview.ckan.found)) }) : null;
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
