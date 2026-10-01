import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { saveSettings, resetAppearanceToDefaults, applyAppearanceSettings, applyThemeVariables, DEFAULT_SETTINGS, type AppSettings } from '../services/settingsService';
import { refreshSidebarBrand } from '../components/Sidebar';
import { getThemePreference, setThemePreference, type ThemePreference } from '../services/themeService';
import { createPanelHeader } from './settingsShared';

// ---------- Aparencia ----------

export function createAppearancePanel(
  settings: AppSettings,
  loaded: boolean,
  notify: (message: string) => void,
  notifyError: (message: string) => void
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel appearance-panel' });
  const header = createPanelHeader('Aparência', 'Identidade visual e preferências do HUB');

  if (!loaded) {
    panel.append(header, createElement('p', {
      className: 'settings-hint',
      textContent: 'Carregando aparencia salva...'
    }));
    return panel;
  }

  const body = createElement('div', { className: 'settings-form' });
  const themeTitle = createElement('span', { className: 'settings-subheading', textContent: 'Tema' });
  const themeOptions = createElement('div', { className: 'theme-options' });
  const currentTheme = getThemePreference();
  ([['dark', 'Escuro'], ['light', 'Claro'], ['system', 'Sistema']] as const).forEach(([value, label]) => {
    const option = createElement('label', { className: 'theme-option' });
    const input = createElement('input');
    input.type = 'radio'; input.name = 'hub-theme'; input.value = value; input.checked = currentTheme === value;
    input.addEventListener('change', () => { if (input.checked) setThemePreference(value as ThemePreference); });
    option.append(input, createElement('span', { textContent: label }));
    themeOptions.appendChild(option);
  });

  const logoField = createElement('label', { className: 'form-field' });
  const logoLabel = createElement('span', { textContent: 'Logotipo' });
  const logoRow = createElement('div', { className: 'logo-row' });
  const preview = createElement('div', { className: 'logo-preview' });
  const logoInput = createElement('input');
  const logoButton = createElement('button', { className: 'secondary-button', textContent: 'Alterar logo', type: 'button' });

  logoInput.type = 'file';
  logoInput.accept = 'image/png,image/jpeg';
  logoInput.hidden = true;
  renderLogoPreview(preview, settings.logoDataUrl);

  logoButton.addEventListener('click', () => logoInput.click());
  logoInput.addEventListener('change', async () => {
    const file = logoInput.files?.[0];
    if (!file) return;

    logoButton.disabled = true;
    logoButton.textContent = 'Enviando...';

    try {
      const logoDataUrl = await readFileAsDataUrl(file);
      await saveSettings({ logoDataUrl });
      renderLogoPreview(preview, logoDataUrl);
      notify('Logo atualizada.');
    } catch {
      notifyError('Nao foi possivel salvar a logo.');
    } finally {
      logoButton.disabled = false;
      logoButton.textContent = 'Alterar logo';
      logoInput.value = '';
    }
  });

  logoRow.append(preview, logoButton, logoInput);
  logoField.append(logoLabel, logoRow);

  const language = createSelectField('Idioma', settings.language, [
    { value: 'pt-BR', label: 'Português (Brasil)' },
    { value: 'en-US', label: 'English' }
  ]);
  const languageHint = createElement('p', {
    className: 'settings-hint',
    textContent: 'A troca de idioma so guarda a preferencia por enquanto -- ainda nao traduz os textos da interface.'
  });

  const companyName = createInput('Nome da empresa', 'text', settings.companyName);

  const colorsTitle = createElement('span', { className: 'settings-subheading', textContent: 'Cores do tema' });
  const colorGrid = createElement('div', { className: 'color-field-grid' });
  const backgroundColor = createColorField('Fundo', settings.backgroundColor);
  const cardColor = createColorField('Fundo dos cards', settings.cardColor);
  const textColor = createColorField('Texto geral', settings.textColor);
  const accentColor = createColorField('Cor de seleção', settings.accentColor);

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
  const saveButton = createElement('button', { textContent: 'Salvar aparência', type: 'button' });
  const resetButton = createElement('button', { className: 'secondary-button', textContent: 'Restaurar padrão', type: 'button' });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    try {
      await saveSettings({
        companyName: companyName.input.value.trim(),
        language: language.select.value,
        backgroundColor: backgroundColor.input.value,
        cardColor: cardColor.input.value,
        textColor: textColor.input.value,
        accentColor: accentColor.input.value
      });
      notify('Aparência salva.');
      refreshSidebarBrand();
    } catch {
      notifyError('Nao foi possivel salvar a aparencia no backend.');
      applyAppearanceSettings();
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar aparência';
    }
  });

  resetButton.addEventListener('click', async () => {
    colorFields.forEach(({ field, key }) => {
      field.input.value = DEFAULT_SETTINGS[key];
      field.input.dispatchEvent(new Event('input'));
    });

    try {
      await resetAppearanceToDefaults();
      notify('Cores restauradas para o padrão.');
    } catch {
      notifyError('Nao foi possivel restaurar o padrao no backend.');
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
    container.textContent = 'Sem logo';
    return;
  }

  const image = createElement('img');
  image.src = logoDataUrl;
  image.alt = 'Logotipo configurado';
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
