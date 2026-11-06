// frontend/src/components/CategoryPicker.ts
// Select de categoria + botao "+ categoria" (cria na hora via prompt).
// Extraido do ClientDocumentsPanel pra reaproveitar no DocumentLinkModal sem duplicar.
import { createElement } from '../dom';
import { createCategory, getCategories, type CategoryRow } from '../services/documentsService';
import { t } from '../services/i18nService';

export function createCategoryPicker(onError: (message: string) => void): {
  wrapper: HTMLElement;
  select: HTMLSelectElement;
} {
  const wrapper = createElement('div', { className: 'document-upload-row' });
  const select = createElement('select');
  const newCategoryButton = createElement('button', {
    className: 'secondary-button',
    textContent: t('clients.category.newButton'),
    type: 'button'
  });

  let categories: CategoryRow[] = [];

  wrapper.append(select, newCategoryButton);

  function renderOptions(): void {
    const previousValue = select.value;
    select.replaceChildren();

    const placeholder = createElement('option', {
      textContent: categories.length === 0 ? t('clients.category.placeholderEmpty') : t('clients.category.placeholderChoose')
    });
    placeholder.value = '';
    select.appendChild(placeholder);

    categories.forEach((category) => {
      const option = createElement('option', { textContent: category.nome });
      option.value = String(category.id);
      select.appendChild(option);
    });

    select.value = categories.some((category) => String(category.id) === previousValue) ? previousValue : '';
  }

  newCategoryButton.addEventListener('click', async () => {
    const nome = window.prompt(t('clients.category.promptName'));
    if (!nome || !nome.trim()) return;

    try {
      const category = await createCategory(nome.trim());
      categories = [...categories, category];
      renderOptions();
      select.value = String(category.id);
    } catch (error) {
      onError(error instanceof Error ? error.message : t('clients.category.createError'));
    }
  });

  (async () => {
    try {
      categories = await getCategories();
    } catch {
      categories = [];
    } finally {
      renderOptions();
    }
  })();

  return { wrapper, select };
}