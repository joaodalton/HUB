// frontend/src/pages/pendencias/PendenciasEditorModal.ts
import { createElement } from '../../dom';
import { createFormSection, createInput, createSelect, createSelectField } from '../../components/formFields';
import {
  CATEGORIAS_POR_TIPO,
  createPendencia,
  PRIORIDADES,
  roleLabel,
  ROLES,
  updatePendencia,
  type PendenciaPayload,
  type PendenciaPrioridade,
  type PendenciaRow,
  type ResponsavelTipo
} from '../../services/pendenciasService';
import { addExtraCategoria } from '../../services/pendenciaCategoriasService';
import type { UserRole } from '../../services/userService';
import { createVinculacaoSelect, type PendenciasContext } from './shared';

// Toggle usuario/cargo + o select correspondente abaixo -- so um dos dois
// selects fica visivel por vez (regra de exclusividade e aplicada no
// backend, aqui e so UX pra deixar claro que e "ou um ou outro").
function createResponsavelField(ctx: PendenciasContext, pendencia: PendenciaRow | null) {
  const tipoInicial: ResponsavelTipo = pendencia?.responsavelTipo ?? 'usuario';
  const tipo = createSelectField('Tipo de responsável', tipoInicial, [
    { value: 'usuario', label: 'Usuário' },
    { value: 'cargo', label: 'Cargo' }
  ]);
  const usuario = createVinculacaoSelect(
    'Responsável (usuário)',
    ctx.state.users.map((item) => ({ id: item.id, label: item.nome })),
    pendencia?.responsavelTipo === 'usuario' ? pendencia.responsavelId : null
  );
  const cargo = createSelectField(
    'Responsável (cargo)',
    pendencia?.responsavelTipo === 'cargo' && pendencia.responsavelCargo ? pendencia.responsavelCargo : ROLES[0],
    ROLES.map((role) => ({ value: role, label: roleLabel(role) }))
  );

  function updateVisibility(): void {
    const isCargo = tipo.select.value === 'cargo';
    usuario.field.style.display = isCargo ? 'none' : '';
    cargo.field.style.display = isCargo ? '' : 'none';
  }
  tipo.select.addEventListener('change', updateVisibility);
  updateVisibility();

  function getPayload(): Pick<PendenciaPayload, 'responsavelTipo' | 'responsavelId' | 'responsavelCargo'> {
    if (tipo.select.value === 'cargo') {
      return { responsavelTipo: 'cargo', responsavelId: null, responsavelCargo: cargo.select.value as UserRole };
    }
    return {
      responsavelTipo: 'usuario',
      responsavelId: usuario.select.value ? Number(usuario.select.value) : null,
      responsavelCargo: null
    };
  }

  return { tipoField: tipo.field, usuarioField: usuario.field, cargoField: cargo.field, getPayload };
}

// Select de categoria + botao "+ categoria" -- mesmo espirito do
// CategoryPicker.ts (usado em Documentos), mas Pendencia nao tem model de
// categoria proprio: as extras ficam em Setting (ver
// pendenciaCategoriasService.ts). Nao fecha o modal, so atualiza a lista
// na hora -- a categoria recem-criada ja fica selecionada.
function createCategoriaField(ctx: PendenciasContext, selected: string): { field: HTMLElement; select: HTMLSelectElement } {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: 'Categoria' });
  const row = createElement('div', { className: 'select-with-button' });
  const select = createElement('select');
  const addButton = createElement('button', { className: 'secondary-button', textContent: '+ categoria', type: 'button' });

  function renderOptions(value: string): void {
    const todas = [...CATEGORIAS_POR_TIPO.pendencia, ...ctx.state.categoriaExtras.filter((item) => !CATEGORIAS_POR_TIPO.pendencia.includes(item))];
    select.replaceChildren();
    todas.forEach((nome) => {
      const option = createElement('option', { textContent: nome });
      option.value = nome;
      select.appendChild(option);
    });
    select.value = todas.includes(value) ? value : todas[0];
  }

  addButton.addEventListener('click', async () => {
    const nome = window.prompt('Nome da nova categoria de pendência (ex: Idade, Contrato...):');
    if (!nome || !nome.trim()) return;

    addButton.disabled = true;
    try {
      ctx.state.categoriaExtras = await addExtraCategoria(nome.trim(), ctx.state.categoriaExtras);
      renderOptions(nome.trim());
    } catch {
      ctx.toast.error('Não foi possível salvar a nova categoria.');
    } finally {
      addButton.disabled = false;
    }
  });

  renderOptions(selected);
  row.append(select, addButton);
  field.append(text, row);
  return { field, select };
}

export function openPendenciaEditor(ctx: PendenciasContext, pendencia: PendenciaRow | null): void {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: pendencia ? 'Pendência' : 'Nova pendência' });
  const heading = createElement('h2', { textContent: pendencia ? pendencia.titulo : 'Cadastrar pendência' });
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });

  const titulo = createInput('Título', 'text', pendencia?.titulo ?? '', true);
  const categoria = createCategoriaField(ctx, pendencia?.categoria ?? CATEGORIAS_POR_TIPO.pendencia[0]);
  const prioridade = createSelect('Prioridade', pendencia?.prioridade ?? 'media', PRIORIDADES);
  const prazo = createInput('Prazo', 'datetime-local', pendencia?.prazo ? pendencia.prazo.slice(0, 16) : '', false);

  const descricao = createElement('label', { className: 'form-field form-field-wide' });
  const descricaoLabel = createElement('span', { textContent: 'Descrição' });
  const descricaoInput = createElement('textarea');
  descricaoInput.rows = 3;
  descricaoInput.value = pendencia?.descricao ?? '';
  descricao.append(descricaoLabel, descricaoInput);

  const clienteField = createVinculacaoSelect('Cliente (opcional)', ctx.state.clients.map((item) => ({ id: item.id, label: item.nome })), pendencia?.clienteId ?? null);
  const ucField = createVinculacaoSelect('UC (opcional)', ctx.state.ucs.map((item) => ({ id: item.id, label: item.codigo })), pendencia?.ucId ?? null);
  const usinaField = createVinculacaoSelect('Usina (opcional)', ctx.state.plants.map((item) => ({ id: item.id, label: item.nome })), pendencia?.usinaId ?? null);
  const responsavel = createResponsavelField(ctx, pendencia);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar pendência', type: 'submit' });

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  actions.appendChild(saveButton);

  closeButton.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) overlay.remove();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!titulo.input.value.trim()) {
      titulo.input.reportValidity();
      return;
    }

    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    const payload: PendenciaPayload = {
      titulo: titulo.input.value.trim(),
      categoria: categoria.select.value,
      descricao: descricaoInput.value.trim(),
      clienteId: clienteField.select.value ? Number(clienteField.select.value) : null,
      ucId: ucField.select.value ? Number(ucField.select.value) : null,
      usinaId: usinaField.select.value ? Number(usinaField.select.value) : null,
      prazo: prazo.input.value,
      prioridade: prioridade.select.value as PendenciaPrioridade,
      ...responsavel.getPayload()
    };

    ctx.loading.show();
    try {
      if (pendencia) {
        await updatePendencia(pendencia.id, payload);
        ctx.toast.success('Pendência atualizada.');
      } else {
        await createPendencia(payload);
        ctx.toast.success('Pendência criada.');
      }
      overlay.remove();
      await ctx.loadAll();
    } catch (error) {
      ctx.toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a pendência.');
    } finally {
      ctx.loading.hide();
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar pendência';
    }
  });

  form.append(
    header,
    createFormSection('Informações principais', titulo.field, categoria.field, prioridade.field, prazo.field, descricao),
    createFormSection('Relacionamento', clienteField.field, ucField.field, usinaField.field),
    createFormSection('Responsável', responsavel.tipoField, responsavel.usuarioField, responsavel.cargoField),
    actions
  );
  panel.appendChild(form);
  overlay.appendChild(panel);
  document.body.appendChild(overlay);
}
