import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { saveSettings, resetAppearanceToDefaults, applyAppearanceSettings, applyThemeVariables, DEFAULT_SETTINGS, type AppSettings } from '../services/settingsService';
import { refreshSidebarBrand } from '../components/Sidebar';
import { getThemePreference, setThemePreference, type ThemePreference } from '../services/themeService';
import { createPanelHeader } from './settingsShared';
import { t } from '../services/i18nService';

// ---------- Aparencia ----------

export function createAppearancePanel(
  settings: AppSettings,
  loaded: boolean,
  notify: (message: string) => void,
  notifyError: (message: string) => void
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel appearance-panel' });
  const header = createPanelHeader(t('settings.appearance.heading'), t('settings.appearance.description'));

  if (!loaded) {
    panel.append(header, createElement('p', {
      className: 'settings-hint',
      textContent: t('settings.appearance.loading')
    }));
    return panel;
  }

  const body = createElement('div', { className: 'settings-form' });
  const themeTitle = createElement('span', { className: 'settings-subheading', textContent: t('settings.appearance.themeSubheading') });
  const themeOptions = createElement('div', { className: 'theme-options' });
  const currentTheme = getThemePreference();
  ([['dark', t('settings.appearance.themeDark')], ['light', t('settings.appearance.themeLight')], ['system', t('settings.appearance.themeSystem')]] as const).forEach(([value, label]) => {
    const option = createElement('label', { className: 'theme-option' });
    const input = createElement('input');
    input.type = 'radio'; input.name = 'hub-theme'; input.value = value; input.checked = currentTheme === value;
    input.addEventListener('change', () => { if (input.checked) setThemePreference(value as ThemePreference); });
    option.append(input, createElement('span', { textContent: label }));
    themeOptions.appendChild(option);
  });

  const logoField = createElement('label', { className: 'form-field' });
  const logoLabel = createElement('span', { textContent: t('settings.appearance.logoLabel') });
  const logoRow = createElement('div', { className: 'logo-row' });
  const preview = createElement('div', { className: 'logo-preview' });
  const logoInput = createElement('input');
  const logoButton = createElement('button', { className: 'secondary-button', textContent: t('settings.appearance.changeLogo'), type: 'button' });

  logoInput.type = 'file';
  logoInput.accept = 'image/png,image/jpeg';
  logoInput.hidden = true;
  renderLogoPreview(preview, settings.logoDataUrl);

  logoButton.addEventListener('click', () => logoInput.click());
  logoInput.addEventListener('change', async () => {
    const file = logoInput.files?.[0];
    if (!file) return;

    logoButton.disabled = true;
    logoButton.textContent = t('settings.appearance.uploading');

    try {
      const logoDataUrl = await readFileAsDataUrl(file);
      await saveSettings({ logoDataUrl });
      renderLogoPreview(preview, logoDataUrl);
      notify(t('settings.appearance.logoUpdated'));
    } catch {
      notifyError(t('settings.appearance.logoError'));
    } finally {
      logoButton.disabled = false;
      logoButton.textContent = t('settings.appearance.changeLogo');
      logoInput.value = '';
    }
  });

  logoRow.append(preview, logoButton, logoInput);
  logoField.append(logoLabel, logoRow);

  const language = createSelectField(t('settings.appearance.languageLabel'), settings.language, [
    { value: 'pt-BR', label: 'Português (Brasil)' },
    { value: 'en-US', label: 'English' }
  ]);
  const languageHint = createElement('p', {
    className: 'settings-hint',
    textContent: t('settings.appearance.languageHint')
  });

  const companyName = createInput(t('settings.appearance.companyName'), 'text', settings.companyName);

  const colorsTitle = createElement('span', { className: 'settings-subheading', textContent: t('settings.appearance.colorsSubheading') });
  const colorGrid = createElement('div', { className: 'color-field-grid' });
  const backgroundColor = createColorField(t('settings.appearance.backgroundColor'), settings.backgroundColor);
  const cardColor = createColorField(t('settings.appearance.cardColor'), settings.cardColor);
  const textColor = createColorField(t('settings.appearance.textColor'), settings.textColor);
  const accentColor = createColorField(t('settings.appearance.accentColor'), settings.accentColor);

  const colorFields = [
    { field: backgroundColor, key: 'backgroundColor' as const },
    { field: cardColor, key: 'cardColor' as const },
    { field: textColor, key: 'textColor' as const },
    { field: accentColor, key: 'accentColor' as const }
  ];

  function previewColors(): void {
    applyThemeVariables({
      backgroundColor: backgroundColor.input.value,
      cardColor: cardColor.input.value,
      textColor: textColor.input.value,
      accentColor: accentColor.input.value
    });
  }

  colorFields.forEach(({ field }) => field.input.addEventListener('input', previewColors));

  colorGrid.append(backgroundColor.field, cardColor.field, textColor.field, accentColor.field);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('settings.appearance.save'), type: 'button' });
  const resetButton = createElement('button', { className: 'secondary-button', textContent: t('common.restoreDefault'), type: 'button' });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = t('common.saving');

    try {
      await saveSettings({
        companyName: companyName.input.value.trim(),
        language: language.select.value,
        backgroundColor: backgroundColor.input.value,
        cardColor: cardColor.input.value,
        textColor: textColor.input.value,
        accentColor: accentColor.input.value
      });
      notify(t('settings.appearance.saved'));
      refreshSidebarBrand();
    } catch {
      notifyError(t('settings.appearance.saveError'));
      applyAppearanceSettings();
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = t('settings.appearance.save');
    }
  });

  resetButton.addEventListener('click', async () => {
    colorFields.forEach(({ field, key }) => {
      field.input.value = DEFAULT_SETTINGS[key];
      field.input.dispatchEvent(new Event('input'));
    });

    try {
      await resetAppearanceToDefaults();
      notify(t('settings.appearance.restored'));
    } catch {
      notifyError(t('settings.appearance.restoreError'));
    }
  });

  body.append(themeTitle, themeOptions, logoField, language.field, languageHint, companyName.field, colorsTitle, colorGrid);
  actions.append(saveButton, resetButton);
  panel.append(header, body, actions);

  return panel;
}

function createColorField(label: string, value: string): { field: HTMLElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'form-field color-field' });
  const text = createElement('span', { textContent: label });
  const row = createElement('div', { className: 'color-field-row' });
  const input = createElement('input');
  const hexLabel = createElement('span', { className: 'color-hex', textContent: value });

  input.type = 'color';
  input.value = value;
  input.addEventListener('input', () => { hexLabel.textContent = input.value; });

  row.append(input, hexLabel);
  field.append(text, row);

  return { field, input };
}

function renderLogoPreview(container: HTMLElement, logoDataUrl: string): void {
  container.replaceChildren();

  if (!logoDataUrl) {
    container.textContent = t('settings.appearance.noLogo');
    return;
  }

  const image = createElement('img');
  image.src = logoDataUrl;
  image.alt = t('settings.appearance.logoAlt');
  image.className = 'logo-preview-image';
  container.appendChild(image);
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.addEventListener('load', () => resolve(String(reader.result)));
    reader.addEventListener('error', () => reject(reader.error));
    reader.readAsDataURL(file);
  });
}
