import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { createInput, createSelect } from '../components/formFields';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { apiRequest } from '../services/apiClient';
import type { AuthUser } from '../services/authService';
import {
  getEmpresas,
  getEmpresaDetalhe,
  updateEmpresa,
  deleteEmpresa,
  entraEmpresa,
  sairPlataforma,
  type EmpresaRow,
  type EmpresaDetalhe,
  type EmpresaUpdatePayload,
} from '../services/empresaService';

export function createEmpresasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const layout = createBaseLayout({
    content,
    eyebrow: 'Plataforma',
    title: 'Empresas',
  });

  let empresas: EmpresaRow[] = [];
  let detalhe: EmpresaDetalhe | null = null;
  let mostraDetalhe = false;
  let loading = false;
  let platformView: { ativo: boolean; empresaId: number | null; empresaNome: string | null } | null = null;

  async function refreshAuthMe(): Promise<void> {
    try {
      const json = await apiRequest<{ success: boolean; data: AuthUser | null }>('/auth/me');
      if (json.success && json.data) {
        const u = json.data;
        if (u.isPlatformAdmin) {
          platformView = {
            ativo: !!u.platformViewEmpresaId,
            empresaId: u.platformViewEmpresaId ?? null,
            empresaNome: u.platformViewEmpresaNome ?? null,
          };
        } else {
          platformView = null;
        }
        render();
      }
    } catch {
      // ignora falhas
    }
  }

  async function loadEmpresas(): Promise<void> {
    loading = true;
    render();
    try {
      empresas = await getEmpresas();
    } catch (error) {
      loading = false;
      render();
      if (error instanceof Error && error.message && !error.message.includes('Token de autenticacao')) {
        toast.error(error.message);
      }
      return;
    }
    loading = false;
    await refreshAuthMe();
    render();
  }

  loadEmpresas();

  async function handleEntrar(empresa: EmpresaRow): Promise<void> {
    try {
      await entraEmpresa(empresa.id);
      await refreshAuthMe();
      window.location.href = '/clientes';
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível entrar na empresa.');
    }
  }

  function openEditModal(empresa: EmpresaDetalhe): void {
    const overlay = createEmpresaModal(empresa, async (payload) => {
      try {
        const atualizada = await updateEmpresa(empresa.id, payload);
        toast.success(`Empresa "${atualizada.nome}" atualizada.`);
        overlay.remove();
        detalhe = atualizada;
        mostraDetalhe = true;
        await loadEmpresas();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar a empresa.');
      }
    });
    document.body.appendChild(overlay);
  }

  async function handleExcluir(empresa: EmpresaRow): Promise<void> {
    const overlay = createConfirmExclusaoOverlay(empresa, async (frase) => {
      try {
        await deleteEmpresa(empresa.id, frase);
        toast.success(`Empresa "${empresa.nome}" excluída com sucesso.`);
        detalhe = null;
        mostraDetalhe = false;
        await loadEmpresas();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível excluir a empresa.');
      }
    });
    document.body.appendChild(overlay);
  }

  function handleSairPlataforma(): void {
    sairPlataforma().then(() => {
      refreshAuthMe();
      window.location.href = '/empresas';
    }).catch((error) => {
      toast.error(error instanceof Error ? error.message : 'Não foi possível sair do contexto.');
    });
  }

  function render(): void {
    content.replaceChildren(
      createPlatformViewBar(),
      createPageHeader(),
      ...renderBody()
    );
  }

  function createPlatformViewBar(): HTMLElement {
    if (!platformView || !platformView.ativo) return createElement('div');

    const bar = createElement('div', { className: 'platform-view-bar' });
    const label = createElement('span', { className: 'platform-view-label', textContent: 'Visualizando como' });
    const nome = createElement('strong', { className: 'platform-view-nome', textContent: platformView.empresaNome ?? '' });
    const sairBtn = createElement('button', {
      className: 'platform-view-sair',
      textContent: 'Sair',
      type: 'button',
    });
    sairBtn.addEventListener('click', handleSairPlataforma);
    bar.append(label, nome, sairBtn);
    return bar;
  }

  function createPageHeader(): HTMLElement {
    const header = createElement('div', { className: 'page-header-row' });

    const titleRow = createElement('div', { className: 'page-title-row' });
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Plataforma' });
    const heading = createElement('h1', { textContent: 'Empresas' });
    titleRow.append(eyebrow, heading);

    const actionsRow = createElement('div', { className: 'page-actions-row' });
    const novoBtn = createElement('button', { className: 'button-with-icon primary', type: 'button' });
    novoBtn.append(createIcon('plus'), document.createTextNode('Nova empresa'));
    novoBtn.addEventListener('click', () => {
      document.body.appendChild(createEmpresaModal(null, async () => {}));
    });
    actionsRow.appendChild(novoBtn);

    header.append(titleRow, actionsRow);
    return header;
  }

  function renderBody(): HTMLElement[] {
    if (loading) {
      return [createElement('div', { className: 'loading-state', textContent: 'Carregando empresas...' })];
    }

    if (mostraDetalhe && detalhe) {
      return [createDetalhePanel(detalhe, () => {
        mostraDetalhe = false;
        detalhe = null;
        render();
      })];
    }

    if (empresas.length === 0) {
      const empty = createElement('div', { className: 'empty-state' });
      empty.append(
        createElement('p', { textContent: 'Nenhuma empresa cadastrada.' }),
        createElement('span', { textContent: 'Crie uma empresa clicando em "Nova empresa".' }),
      );
      return [empty];
    }

    return [createEmpresasLista(empresas, handleEntrar, openEditModal, handleExcluir)];
  }

  // ----------------------------------------------------------------------
  // Lista de empresas
  // ----------------------------------------------------------------------

  function createEmpresasLista(
    empresas: EmpresaRow[],
    onEntrar: (empresa: EmpresaRow) => void,
    onEditar: (empresa: EmpresaDetalhe) => void,
    onExcluir: (empresa: EmpresaRow) => void,
  ): HTMLElement {
    const wrapper = createElement('div', { className: 'table-wrap' });
    const table = createElement('table', { className: 'data-table' });

    const thead = createElement('thead');
    thead.innerHTML = `
      <tr>
        <th>Nome</th>
        <th>Proprietário (email)</th>
        <th>Clientes</th>
        <th>Status</th>
        <th class="align-right">Ações</th>
      </tr>
    `;

    const tbody = createElement('tbody');
    for (const empresa of empresas) {
      const row = createElement('tr');

      const nomeCell = createElement('td');
      const nomeLink = createElement('button', {
        className: 'secondary-link',
        type: 'button',
        textContent: empresa.nome,
      });
      nomeLink.addEventListener('click', () => onEntrar(empresa));
      nomeCell.appendChild(nomeLink);

      row.appendChild(nomeCell);
      row.appendChild(createElement('td', { textContent: empresa.ownerEmail ?? '-' }));
      row.appendChild(createElement('td', { textContent: String(empresa.totalClientes ?? 0) }));
      row.appendChild(createElement('td', { textContent: empresa.status }));

      const actionsCell = createElement('td');
      const actionsWrap = createElement('div', { className: 'table-actions' });

      const editarBtn = createElement('button', {
        className: 'icon-button secondary',
        type: 'button',
        title: 'Editar empresa',
      });
      editarBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
      </svg>`;
      editarBtn.addEventListener('click', () => {
        getEmpresaDetalhe(empresa.id).then((detalhe) => {
          if (detalhe) onEditar(detalhe);
        }).catch(() => {
          toast.error('Não foi possível carregar os dados para edição.');
        });
      });

      const excluirBtn = createElement('button', {
        className: 'icon-button danger',
        type: 'button',
        title: 'Excluir empresa',
      });
      excluirBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M7 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
      </svg>`;
      excluirBtn.addEventListener('click', () => onExcluir(empresa));

      actionsWrap.append(editarBtn, excluirBtn);
      actionsCell.appendChild(actionsWrap);
      row.appendChild(actionsCell);
      tbody.appendChild(row);
    }

    table.appendChild(thead);
    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
  }

  // ----------------------------------------------------------------------
  // Painel de detalhe da empresa
  // ----------------------------------------------------------------------

  function createDetalhePanel(detalhe: EmpresaDetalhe, onVoltar: () => void): HTMLElement {
    const panel = createElement('section', { className: 'detail-panel' });

    const header = createElement('div', { className: 'detail-header' });
    const voltarBtn = createElement('button', {
      className: 'icon-button neutral',
      type: 'button',
      title: 'Voltar à lista',
    });
    voltarBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="19" y1="12" x2="5" y2="12"/>
      <polyline points="12 19 5 12 12 5"/>
    </svg>`;
    voltarBtn.addEventListener('click', onVoltar);

    const titleGroup = createElement('div', { className: 'detail-title-group' });
    const nomeTag = createElement('span', { className: 'section-tag', textContent: 'Empresa' });
    const nome = createElement('h2', { textContent: detalhe.nome });
    titleGroup.append(nomeTag, nome);
    header.append(voltarBtn, titleGroup);
    panel.appendChild(header);

    const grid = createElement('div', { className: 'detail-grid' });

    const cadastrais = createElement('div', { className: 'detail-card' });
    cadastrais.append(
      createDetailRow('Nome', detalhe.nome),
      createDetailRow('Slug', detalhe.slug),
      createDetailRow('Razão social', detalhe.razaoSocial ?? '-'),
      createDetailRow('CNPJ', detalhe.cnpj ?? '-'),
      createDetailRow('E-mail', detalhe.email ?? '-'),
      createDetailRow('Telefone', detalhe.telefone ?? '-'),
      createDetailRow('Status', detalhe.status),
    );
    grid.appendChild(cadastrais);

    const contadores = createElement('div', { className: 'detail-card' });
    contadores.append(
      createDetailRow('Usuários', String(detalhe.totalUsuarios)),
      createDetailRow('Clientes', String(detalhe.totalClientes)),
      createDetailRow('UCs', String(detalhe.totalUcs)),
      createDetailRow('Usinas', String(detalhe.totalUsinas)),
      createDetailRow('Pendências', String(detalhe.totalPendencias)),
      createDetailRow('Faturas', String(detalhe.totalFaturas)),
      createDetailRow('Rateios', String(detalhe.totalRateios)),
      createDetailRow('Documentos', String(detalhe.totalDocumentos)),
      createDetailRow('Convites', String(detalhe.totalConvites)),
    );
    grid.appendChild(contadores);

    panel.appendChild(grid);
    return panel;
  }

  function createDetailRow(label: string, value: string): HTMLElement {
    const row = createElement('div', { className: 'detail-row' });
    const labelEl = createElement('span', { className: 'detail-label', textContent: label });
    const valueEl = createElement('span', { className: 'detail-value', textContent: value });
    row.append(labelEl, valueEl);
    return row;
  }

  // ----------------------------------------------------------------------
  // Modal de criação/edição de empresa
  // ----------------------------------------------------------------------

  function createEmpresaModal(
    empresa: EmpresaDetalhe | null,
    onSave: (payload: EmpresaUpdatePayload) => void,
  ): HTMLElement {
    const isEdit = empresa !== null;
    const overlay = createElement('div', { className: 'modal-overlay' });
    const panel = createElement('article', { className: isEdit ? 'empresa-card' : 'client-card' });
    const form = createElement('form', { className: 'client-form' });

    const title = isEdit ? 'Editar empresa' : 'Nova empresa';
    const header = createElement('div', { className: 'form-header' });
    const titleDiv = createElement('div');
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Empresas' });
    const heading = createElement('h2', { textContent: title });
    const closeBtn = createElement('button', { className: 'icon-button', type: 'button', title: 'Fechar' });
    closeBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="18" y1="6" x2="6" y2="18"/>
      <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>`;

    const fields = createElement('div', { className: 'form-grid' });

    const nomeField = createInput('Nome', 'text', empresa?.nome ?? '', true);
    const razaoField = createInput('Razão social', 'text', empresa?.razaoSocial ?? '', false);
    const cnpjField = createInput('CNPJ', 'text', empresa?.cnpj ?? '', false);
    const emailField = createInput('E-mail', 'email', empresa?.email ?? '', false);
    const telefoneField = createInput('Telefone', 'text', empresa?.telefone ?? '', false);
    const statusField = createSelect('Status', empresa?.status ?? 'ativa', ['ativa', 'inativa']);

    const slugField = createElement('div', { className: 'form-field' });
    const slugLabel = createElement('label', { className: 'form-label', textContent: 'Slug' });
    const slugValue = createElement('span', { textContent: empresa?.slug ?? '' });
    slugField.append(slugLabel, slugValue);

    fields.append(
      nomeField.field,
      razaoField.field,
      cnpjField.field,
      emailField.field,
      telefoneField.field,
      statusField.field,
      slugField,
    );

    const actions = createElement('div', { className: 'form-actions' });
    const submitBtn = createElement('button', {
      className: 'primary-button',
      textContent: 'Salvar alterações',
      type: 'submit',
    }) as HTMLButtonElement;
    const cancelBtn = createElement('button', {
      className: 'secondary-button',
      textContent: 'Cancelar',
      type: 'button',
    }) as HTMLButtonElement;
    const deleteBtn = createElement('button', {
      className: 'danger-button',
      textContent: 'Excluir empresa',
      type: 'button',
    }) as HTMLButtonElement;

    actions.append(submitBtn, cancelBtn, deleteBtn);

    titleDiv.append(eyebrow, heading);
    header.append(titleDiv, closeBtn);

    form.append(header, fields, actions);
    panel.appendChild(form);
    overlay.appendChild(panel);

    closeBtn.addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submitBtn.disabled = true;
      submitBtn.textContent = 'Salvando...';

      const payload: EmpresaUpdatePayload = {
        nome: nomeField.input.value.trim() || undefined,
        razaoSocial: razaoField.input.value.trim() || undefined,
        cnpj: cnpjField.input.value.trim() || undefined,
        email: emailField.input.value.trim() || undefined,
        telefone: telefoneField.input.value.trim() || undefined,
        status: statusField.select.value || undefined,
      };

      try {
        await onSave(payload);
        submitBtn.disabled = false;
        submitBtn.textContent = 'Salvar alterações';
      } catch (error) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Salvar alterações';
        toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar.');
      }
    });

    cancelBtn.addEventListener('click', () => overlay.remove());

    if (empresa) {
      deleteBtn.addEventListener('click', () => {
        overlay.remove();
        const empresaRow: EmpresaRow = {
          id: empresa.id,
          nome: empresa.nome,
          slug: empresa.slug,
          status: empresa.status,
          cnpj: empresa.cnpj,
          email: empresa.email,
          telefone: empresa.telefone,
          totalUsuarios: empresa.totalUsuarios,
          totalClientes: empresa.totalClientes,
          ownerEmail: empresa.ownerEmail,
        };
        const confirmOverlay = createConfirmExclusaoOverlay(empresaRow, async (frase) => {
          try {
            await deleteEmpresa(empresa.id, frase);
            toast.success(`Empresa "${empresa.nome}" excluída com sucesso.`);
            await loadEmpresas();
          } catch (error) {
            toast.error(error instanceof Error ? error.message : 'Não foi possível excluir.');
          }
        });
        document.body.appendChild(confirmOverlay);
      });
    }

    return overlay;
  }

  // ----------------------------------------------------------------------
  // Overlay de confirmação de exclusão
  // ----------------------------------------------------------------------

  const FRASES_CONFERENCIA: string[] = [
    'CONFIRMAR',
    'EXCLUIR',
    'DELETAR',
    'APAGAR',
    'CONCORDO',
    'AFIRMATIVO',
  ];

  function createConfirmExclusaoOverlay(
    empresa: EmpresaRow,
    onConfirm: (frase: string) => void,
  ): HTMLElement {
    const overlay = createElement('div', { className: 'confirm-overlay' });
    const box = createElement('div', { className: 'confirm-box danger' });

    const title = createElement('h3', { textContent: `Excluir empresa "${empresa.nome}"` });
    const message = createElement('p', {
      textContent: 'Digite a palavra-chave exata para confirmar a exclusão definitiva desta empresa.',
    });

    const inputGroup = createElement('div', { className: 'confirm-input-group' });
    const inputLabel = createElement('label', { className: 'confirm-input-label', textContent: FRASES_CONFERENCIA[0] });
    const input = document.createElement('input');
    input.className = 'confirm-input';
    input.type = 'text';
    input.placeholder = FRASES_CONFERENCIA[0];
    input.maxLength = 20;

    const submitBtn = createElement('button', {
      className: 'confirm-submit primary-button',
      textContent: 'Excluir',
      type: 'button',
    }) as HTMLButtonElement;

    input.addEventListener('input', () => {
      submitBtn.disabled = input.value.trim() !== FRASES_CONFERENCIA[0];
    });
    submitBtn.disabled = true;

    submitBtn.addEventListener('click', () => {
      if (input.value.trim() === FRASES_CONFERENCIA[0]) {
        onConfirm(input.value.trim());
        overlay.remove();
      }
    });

    inputGroup.append(inputLabel, input, submitBtn);
    box.append(title, message, inputGroup);
    overlay.appendChild(box);

    return overlay;
  }

  return layout;
}
