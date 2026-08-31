import { createDataTable } from '../components/DataTable';
import { createIcon } from '../components/Icon';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import {
  confirmarImportacao,
  criarPreviaImportacao,
  type ImportacaoPrevia,
  type ImportacaoProblema,
  type ImportacaoResultado
} from '../services/importacoesService';

type ImportacaoStage = 'selecionar' | 'previa' | 'resultado';
type TipoCsv = 'clientes' | 'ucs' | 'usinas';
type ProblemaRow = ImportacaoProblema & { local: string };

export function createImportacoesPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  const toast = useToast();
  let stage: ImportacaoStage = 'selecionar';
  let arquivo: File | null = null;
  let tipoCsv: TipoCsv = 'clientes';
  let previa: ImportacaoPrevia | null = null;
  let resultado: ImportacaoResultado | null = null;
  let busy = false;
  let uploadError = '';
  let confirmError = '';

  const layout = createBaseLayout({
    content,
    eyebrow: 'Gestão',
    title: 'Importação em massa'
  });
  render();
  return layout;

  function render(): void {
    if (!canImport()) {
      const denied = createElement('section', { className: 'importacao-panel empty-state' });
      denied.append(
        createIcon('lock', 'empty-state-icon'),
        createElement('strong', { textContent: 'Acesso não permitido' }),
        createElement('span', { textContent: 'Seu perfil não tem permissão para importar cadastros.' })
      );
      content.replaceChildren(denied);
      return;
    }

    if (stage === 'previa' && previa) {
      content.replaceChildren(createPreviewPanel(previa));
      return;
    }
    if (stage === 'resultado' && resultado) {
      content.replaceChildren(createResultPanel(resultado));
      return;
    }
    content.replaceChildren(createUploadPanel());
  }

  function createUploadPanel(): HTMLElement {
    const panel = createElement('section', { className: 'importacao-panel' });
    panel.append(
      createImportacaoHeader('Enviar planilha', 'Envie um arquivo Excel com as três abas esperadas. O HUB valida tudo antes de criar os cadastros.'),
      createTemplateGuide()
    );
    const form = createElement('form', { className: 'importacao-form' });
    const fileField = createElement('label', { className: 'upload-dropzone importacao-dropzone' });
    const fileInput = createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv';
    fileInput.required = true;
    const selectedLabel = createElement('span', { className: 'importacao-file-name', textContent: arquivo?.name ?? 'Escolher planilha Excel (.xlsx) ou CSV' });
    fileField.append(createIcon('upload'), selectedLabel, fileInput);
    fileInput.addEventListener('change', () => {
      arquivo = fileInput.files?.[0] ?? null;
      uploadError = '';
      selectedLabel.textContent = arquivo?.name ?? 'Escolher planilha Excel (.xlsx) ou CSV';
    });
    const csvTypeField = createElement('label', { className: 'form-field' });
    csvTypeField.appendChild(createElement('span', { textContent: 'Tipo do CSV (obrigatório apenas para CSV)' }));
    const csvType = createElement('select');
    [['clientes', 'Clientes'], ['ucs', 'UCs'], ['usinas', 'Usinas']].forEach(([value, label]) => { const option = createElement('option', { textContent: label }); option.value = value; csvType.appendChild(option); });
    csvType.value = tipoCsv;
    csvType.addEventListener('change', () => { tipoCsv = csvType.value as TipoCsv; });
    csvTypeField.appendChild(csvType);
    const hint = createElement('p', { className: 'settings-hint', textContent: 'A prévia não grava dados. Corrija os erros apontados e envie uma nova planilha se necessário.' });
    const actions = createElement('div', { className: 'form-actions' });
    const submit = createElement('button', { className: 'button-with-icon', type: 'submit' });
    submit.append(createIcon('eye'), document.createTextNode('Gerar prévia'));
    if (uploadError) form.appendChild(createElement('p', { className: 'importacao-error', textContent: uploadError }));
    form.addEventListener('submit', (event) => { event.preventDefault(); if (arquivo) void upload(arquivo, arquivo.name.toLowerCase().endsWith('.csv') ? tipoCsv : undefined); else fileInput.reportValidity(); });
    actions.appendChild(submit);
    form.append(fileField, csvTypeField, hint, actions);
    panel.appendChild(form);
    return panel;
  }

  function createPreviewPanel(data: ImportacaoPrevia): HTMLElement {
    const panel = createElement('section', { className: 'content-stack' });
    const header = createElement('section', { className: 'importacao-panel' });
    header.append(createImportacaoHeader('Prévia da importação', 'Revise o resultado. A confirmação só fica disponível quando não houver erros.'));
    header.appendChild(createResumo(data.contagens, data.erros.length));
    if (data.erros.length) {
      header.append(createProblemasPanel('Erros que impedem a confirmação', data.erros, 'importacao-erros'), createPreviewActions(false));
    } else {
      header.append(createElement('p', { className: 'importacao-ready', textContent: `Prévia válida. Nenhum dado foi gravado ainda; confirme antes de ${formatExpiration(data.expiraEm)}.` }), createPreviewActions(true));
    }
    panel.appendChild(header);
    return panel;
  }

  function createPreviewActions(canConfirm: boolean): HTMLElement {
    const actions = createElement('div', { className: 'form-actions' });
    const replace = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Enviar outra planilha' });
    replace.addEventListener('click', reset);
    actions.appendChild(replace);
    if (canConfirm) {
      const confirm = createElement('button', { type: 'button', textContent: busy ? 'Confirmando...' : 'Confirmar importação' });
      confirm.disabled = busy;
      confirm.addEventListener('click', () => { if (previa) void confirmImport(previa.previewId); });
      actions.appendChild(confirm);
    }
    if (confirmError) actions.appendChild(createElement('p', { className: 'importacao-error', textContent: confirmError }));
    return actions;
  }

  function createResultPanel(data: ImportacaoResultado): HTMLElement {
    const panel = createElement('section', { className: 'importacao-panel importacao-result' });
    panel.append(
      createIcon('check', 'importacao-success-icon'),
      createImportacaoHeader('Importação concluída', 'Os cadastros válidos foram processados no escopo da sua empresa.'),
      createResumo(data)
    );
    const actions = createElement('div', { className: 'form-actions' });
    const again = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Nova importação' });
    again.addEventListener('click', reset);
    actions.append(again, createNavigateButton('Ver Clientes', '/clientes'), createNavigateButton('Ver UCs', '/ucs'), createNavigateButton('Ver Usinas', '/usinas'));
    panel.appendChild(actions);
    return panel;
  }

  function createTemplateGuide(): HTMLElement {
    const guide = createElement('section', { className: 'importacao-template-guide' });
    guide.append(createElement('h2', { textContent: 'Formato esperado' }), createElement('p', { textContent: 'No XLSX, use as abas Clientes, UCs e Usinas. CSV UTF-8 aceita somente uma delas por arquivo; selecione o tipo acima.' }));
    const list = createElement('ol');
    ['Clientes — obrigatórios: nome, cpf e email; opcionais: telefone e concessionaria.', 'UCs — obrigatórios: clienteCpf e codigo; opcionais: consumo e concessionaria.', 'Usinas — obrigatórios: nome, uc e kwPico; opcional: concessionaria.'].forEach((item) => list.appendChild(createElement('li', { textContent: item })));
    guide.appendChild(list);
    return guide;
  }

  function createResumo(contagens: ImportacaoResultado, erros = 0): HTMLElement {
    const grid = createElement('div', { className: 'importacao-summary-grid' });
    const validas = contagens.clientes + contagens.ucs + contagens.usinas;
    const rows: Array<[string, number]> = [['Prontas para criar', validas], ['Com erro', erros], ['Clientes', contagens.clientes], ['UCs', contagens.ucs], ['Usinas', contagens.usinas]];
    rows.forEach(([label, value]) => {
      const card = createElement('div', { className: label === 'Com erro' && value ? 'importacao-summary-card danger' : 'importacao-summary-card' });
      card.append(createElement('strong', { textContent: String(value) }), createElement('span', { textContent: label }));
      grid.appendChild(card);
    });
    return grid;
  }

  function createProblemasPanel(title: string, problemas: ImportacaoProblema[], className: string): HTMLElement {
    const section = createElement('section', { className: `importacao-problemas ${className}` });
    section.appendChild(createElement('h2', { textContent: title }));
    const rows: ProblemaRow[] = problemas.map((item) => ({ ...item, local: `${item.tipo} · linha ${item.linha}` }));
    section.appendChild(createDataTable<ProblemaRow>({
      title,
      eyebrow: 'Validação',
      rows,
      emptyMessage: 'Nenhum item.',
      columns: [{ key: 'local', label: 'Local' }, { key: 'erro', label: 'Mensagem' }]
    }));
    return section;
  }

  async function upload(file: File, csvType?: TipoCsv): Promise<void> {
    busy = true;
    uploadError = '';
    loading.show();
    render();
    try {
      previa = await criarPreviaImportacao(file, csvType);
      confirmError = '';
      stage = 'previa';
    } catch (error) {
      uploadError = error instanceof Error ? error.message : 'Não foi possível gerar a prévia da importação.';
    } finally {
      busy = false;
      loading.hide();
      render();
    }
  }

  async function confirmImport(id: number): Promise<void> {
    busy = true;
    confirmError = '';
    loading.show();
    render();
    try {
      resultado = await confirmarImportacao(id);
      stage = 'resultado';
      toast.success('Importação concluída.');
    } catch (error) {
      confirmError = error instanceof Error ? error.message : 'Não foi possível confirmar a importação.';
    } finally {
      busy = false;
      loading.hide();
      render();
    }
  }

  function reset(): void {
    stage = 'selecionar';
    arquivo = null;
    previa = null;
    resultado = null;
    uploadError = '';
    confirmError = '';
    render();
  }
}

function canImport(): boolean {
  const role = getCurrentUser()?.role;
  return role === 'owner' || role === 'admin' || role === 'operator';
}

function createImportacaoHeader(eyebrow: string, title: string): HTMLElement {
  const header = createElement('div', { className: 'panel-title' });
  const content = createElement('div');
  content.append(createElement('span', { className: 'eyebrow', textContent: eyebrow }), createElement('h2', { textContent: title }));
  header.appendChild(content);
  return header;
}

function createNavigateButton(label: string, path: string): HTMLElement {
  const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: label });
  button.addEventListener('click', () => { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); });
  return button;
}

function formatExpiration(value: string): string {
  return new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
