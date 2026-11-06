import { describe, it, expect, vi, afterEach } from 'vitest';
import { createCadastroEmpresaPage } from '../pages/CadastroEmpresaPage';
import * as pedidoPlanoService from '../services/pedidoPlanoService';
import { ApiRequestError } from '../services/apiClient';

describe('CadastroEmpresaPage', () => {
  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('mostra erro de link invalido quando o token esta ausente', () => {
    window.history.pushState({}, '', '/cadastro-empresa');
    const page = createCadastroEmpresaPage();
    expect(page.querySelector('form')).toBeNull();
    expect(page.querySelector('.login-error')?.textContent).toContain('Link inválido');
  });

  it('renderiza o formulario quando o token esta presente', () => {
    window.history.pushState({}, '', '/cadastro-empresa?token=abc123');
    const page = createCadastroEmpresaPage();
    expect(page.querySelector('form')).not.toBeNull();
    expect(page.querySelectorAll('input[type="text"]').length).toBe(2);
    expect(page.querySelector('input[type="password"]')).not.toBeNull();
  });

  it('conclui o cadastro com os dados preenchidos e mostra sucesso', async () => {
    window.history.pushState({}, '', '/cadastro-empresa?token=abc123');
    const concludeSpy = vi.spyOn(pedidoPlanoService, 'concluirCadastroPedidoPlano').mockResolvedValue({ empresaId: 10 });
    const page = createCadastroEmpresaPage();
    document.body.appendChild(page);

    const textInputs = page.querySelectorAll('input[type="text"]');
    (textInputs[0] as HTMLInputElement).value = 'Minha Empresa';
    (textInputs[1] as HTMLInputElement).value = 'minha-empresa';
    (page.querySelector('input[type="password"]') as HTMLInputElement).value = 'senha123';

    const form = page.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(concludeSpy).toHaveBeenCalledWith('abc123', 'Minha Empresa', 'minha-empresa', 'senha123');
    expect(page.textContent).toContain('Empresa criada');
  });

  it('mostra a mensagem de erro da API quando a conclusao falha', async () => {
    window.history.pushState({}, '', '/cadastro-empresa?token=abc123');
    vi.spyOn(pedidoPlanoService, 'concluirCadastroPedidoPlano').mockRejectedValue(new ApiRequestError(409, 'Esse identificador já está em uso.'));
    const page = createCadastroEmpresaPage();
    document.body.appendChild(page);

    const textInputs = page.querySelectorAll('input[type="text"]');
    (textInputs[0] as HTMLInputElement).value = 'Minha Empresa';
    (textInputs[1] as HTMLInputElement).value = 'minha-empresa';
    (page.querySelector('input[type="password"]') as HTMLInputElement).value = 'senha123';

    const form = page.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(page.textContent).toContain('Esse identificador já está em uso.');
  });
});
