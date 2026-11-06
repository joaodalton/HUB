import { describe, it, expect, vi } from 'vitest';
import { createCheckoutPage } from '../pages/CheckoutPage';
import * as pedidoPlanoService from '../services/pedidoPlanoService';
import { ApiRequestError } from '../services/apiClient';

describe('CheckoutPage', () => {
  it('renderiza os campos principais do checkout', () => {
    const page = createCheckoutPage();
    expect(page.querySelectorAll('input[name="plano"]').length).toBe(3);
    expect(page.querySelectorAll('input[name="billingType"]').length).toBe(3);
    expect(page.querySelector('input[type="email"]')).not.toBeNull();
  });

  it('bloqueia o submit sem plano e forma de pagamento selecionados', async () => {
    const createSpy = vi.spyOn(pedidoPlanoService, 'criarPedidoPlano');
    const page = createCheckoutPage();
    document.body.appendChild(page);

    (page.querySelector('input[type="email"]') as HTMLInputElement).value = 'cliente@email.com';
    (page.querySelector('input[type="text"]') as HTMLInputElement).value = 'Fulano de Tal';

    const form = page.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(createSpy).not.toHaveBeenCalled();
    expect((page.querySelector('.login-error') as HTMLElement).hidden).toBe(false);
  });

  it('envia o pedido de plano com os dados preenchidos e mostra sucesso', async () => {
    const createSpy = vi.spyOn(pedidoPlanoService, 'criarPedidoPlano').mockResolvedValue({
      id: 1,
      email: 'cliente@email.com',
      planoChave: 'starter',
      externalReference: 'ref-1',
      asaasCustomerId: 'cus_1',
      asaasSubscriptionId: 'sub_1',
      status: 'PENDING'
    });
    const page = createCheckoutPage();
    document.body.appendChild(page);

    (page.querySelector('input[value="starter"]') as HTMLInputElement).click();
    (page.querySelector('input[value="PIX"]') as HTMLInputElement).click();
    (page.querySelector('input[type="email"]') as HTMLInputElement).value = 'cliente@email.com';
    const textInputs = page.querySelectorAll('input[type="text"]');
    (textInputs[0] as HTMLInputElement).value = 'Fulano de Tal';
    (textInputs[1] as HTMLInputElement).value = '123.456.789-00';

    const form = page.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(createSpy).toHaveBeenCalledWith('cliente@email.com', 'starter', {
      name: 'Fulano de Tal',
      cpfCnpj: '123.456.789-00',
      mobilePhone: undefined,
      billingType: 'PIX'
    });
    expect(page.querySelector('input[type="email"]')).toBeNull();
    expect(page.textContent).toContain('Pagamento iniciado');
  });

  it('mostra a mensagem de erro da API quando o pedido falha', async () => {
    vi.spyOn(pedidoPlanoService, 'criarPedidoPlano').mockRejectedValue(new ApiRequestError(409, 'E-mail já possui assinatura ativa.'));
    const page = createCheckoutPage();
    document.body.appendChild(page);

    (page.querySelector('input[value="starter"]') as HTMLInputElement).click();
    (page.querySelector('input[value="BOLETO"]') as HTMLInputElement).click();
    (page.querySelector('input[type="email"]') as HTMLInputElement).value = 'cliente@email.com';
    const textInputs = page.querySelectorAll('input[type="text"]');
    (textInputs[0] as HTMLInputElement).value = 'Fulano de Tal';
    (textInputs[1] as HTMLInputElement).value = '123.456.789-00';

    const form = page.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(page.textContent).toContain('E-mail já possui assinatura ativa.');
  });
});
