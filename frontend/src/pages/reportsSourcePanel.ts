import { createIcon } from '../components/Icon';
import { createElement } from '../dom';
import {
  removeSourceTemplate, setSourceTemplateDrive, setSourceTemplateUpload,
  type SourceTemplateCategory, type SourceTemplateConfig
} from '../services/reportsService';
import { t } from '../services/i18nService';

export type SourceCategoryItem = { categoria: SourceTemplateCategory; label: string; extensao: string; descricaoGoogle: string };

interface SourcePanelContext {
  origens: Record<SourceTemplateCategory, SourceTemplateConfig | null>;
  loading: { show: () => void; hide: () => void };
  toast: { success: (message: string) => void; error: (message: string) => void };
  reloadOrigem: (categoria: SourceTemplateCategory) => Promise<void>;
}

function extrairDriveFileId(valor: string): string {
  const match = valor.match(/\/d\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : valor.trim();
}

export function createSourcePanel(item: SourceCategoryItem, ctx: SourcePanelContext): HTMLElement {
  const panel = createElement('section', { className: 'data-panel reports-config-panel' });
  panel.appendChild(createElement('h3', { textContent: item.label }));

  const origem = ctx.origens[item.categoria];
  if (origem?.tipoOrigem) {
    panel.appendChild(createElement('p', {
      className: 'settings-hint',
      textContent: origem.tipoOrigem === 'drive' ? t('reports.page.sourceDriveTemplate').replace('{id}', origem.driveFileId ?? '') : t('reports.page.sourceFileTemplate').replace('{name}', origem.documentoNome ?? ''),
    }));
    const removeButton = createElement('button', { className: 'danger-button button-with-icon small-button', type: 'button' });
    removeButton.append(createIcon('trash'), document.createTextNode(t('common.remove')));
    removeButton.addEventListener('click', () => void handleRemoveSource(item, ctx));
    panel.appendChild(removeButton);
    return panel;
  }

  panel.appendChild(createElement('p', { className: 'empty-state small', textContent: t('reports.page.generatedFromScratch') }));

  const driveForm = createElement('form', { className: 'page-actions' });
  const driveInput = createElement('input'); driveInput.type = 'text'; driveInput.placeholder = item.descricaoGoogle; driveInput.required = true;
  const driveSubmit = createElement('button', { className: 'small-button', type: 'submit', textContent: t('reports.page.useFromDriveButton') });
  driveForm.append(driveInput, driveSubmit);
  driveForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void handleSetDriveSource(item, extrairDriveFileId(driveInput.value), driveForm, ctx);
  });
  panel.appendChild(driveForm);

  panel.appendChild(createUploadForm(item, ctx));

  return panel;
}

function createUploadForm(item: SourceCategoryItem, ctx: SourcePanelContext): HTMLElement {
  const form = createElement('form', { className: 'page-actions' });
  const fileInput = createElement('input'); fileInput.type = 'file'; fileInput.accept = item.extensao; fileInput.hidden = true;
  const chooseButton = createElement('button', { className: 'secondary-button button-with-icon small-button', type: 'button' });
  chooseButton.append(createIcon('upload'), document.createTextNode(t('reports.page.chooseFileButton')));
  const fileNameLabel = createElement('span', { className: 'settings-hint' });
  const uploadSubmit = createElement('button', { className: 'small-button', type: 'submit', textContent: t('reports.page.uploadButton') });
  uploadSubmit.disabled = true;

  chooseButton.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    fileNameLabel.textContent = file?.name ?? '';
    uploadSubmit.disabled = !file;
  });

  form.append(fileInput, chooseButton, fileNameLabel, uploadSubmit);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const file = fileInput.files?.[0];
    if (file) void handleSetUploadSource(item, file, form, fileNameLabel, ctx);
  });
  return form;
}

async function handleSetDriveSource(item: SourceCategoryItem, driveFileId: string, form: HTMLFormElement, ctx: SourcePanelContext): Promise<void> {
  ctx.loading.show();
  try {
    await setSourceTemplateDrive(item.categoria, driveFileId);
    ctx.toast.success(t('reports.page.templateConfiguredSuccess'));
    form.reset();
    await ctx.reloadOrigem(item.categoria);
  } catch (error) {
    ctx.toast.error(error instanceof Error ? error.message : t('reports.page.templateConfigureError'));
  } finally {
    ctx.loading.hide();
  }
}

async function handleSetUploadSource(
  item: SourceCategoryItem, file: File, form: HTMLFormElement, fileNameLabel: HTMLElement, ctx: SourcePanelContext
): Promise<void> {
  ctx.loading.show();
  try {
    await setSourceTemplateUpload(item.categoria, file);
    ctx.toast.success(t('reports.page.templateConfiguredSuccess'));
    form.reset();
    fileNameLabel.textContent = '';
    await ctx.reloadOrigem(item.categoria);
  } catch (error) {
    ctx.toast.error(error instanceof Error ? error.message : t('reports.page.templateConfigureError'));
  } finally {
    ctx.loading.hide();
  }
}

async function handleRemoveSource(item: SourceCategoryItem, ctx: SourcePanelContext): Promise<void> {
  if (!window.confirm(t('reports.page.confirmRemoveSource').replace('{name}', item.label))) return;
  ctx.loading.show();
  try {
    await removeSourceTemplate(item.categoria);
    ctx.toast.success(t('reports.page.sourceRemovedSuccess'));
    await ctx.reloadOrigem(item.categoria);
  } catch (error) {
    ctx.toast.error(error instanceof Error ? error.message : t('reports.page.sourceRemoveError'));
  } finally {
    ctx.loading.hide();
  }
}
