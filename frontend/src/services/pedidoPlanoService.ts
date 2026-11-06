import { apiRequest } from './apiClient';
import type { ApiResponse } from './apiClient';

export type PedidoPlanoResult = {
  id: number;
  email: string;
  planoChave: string;
  externalReference: string;
  asaasCustomerId: string;
  asaasSubscriptionId: string;
  status: string;
};

export async function criarPedidoPlano(
  email: string,
  planoChave: string,
  dadosPagamento: { name: string; cpfCnpj: string; mobilePhone?: string; billingType: string }
): Promise<PedidoPlanoResult> {
  const response = await apiRequest<ApiResponse<PedidoPlanoResult>>('/platform/pedidos-plano', {
    method: 'POST',
    body: { email, planoChave, dadosPagamento }
  });
  return response.data;
}

export async function concluirCadastroPedidoPlano(
  token: string, nomeEmpresa: string, slug: string, senha: string
): Promise<{ empresaId: number }> {
  const response = await apiRequest<ApiResponse<{ empresaId: number }>>('/platform/pedidos-plano/concluir', {
    method: 'POST',
    body: { token, nomeEmpresa, slug, senha }
  });
  return response.data;
}
