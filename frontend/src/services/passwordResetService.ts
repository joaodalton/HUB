import { apiRequest } from './apiClient';

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function solicitarResetSenha(email: string): Promise<string> {
  const response = await apiRequest<ApiResponse<null>>('/auth/esqueci-senha', {
    method: 'POST',
    body: { email }
  });
  return response.message;
}

export async function redefinirSenha(token: string, senha: string): Promise<string> {
  const response = await apiRequest<ApiResponse<null>>('/auth/redefinir-senha', {
    method: 'POST',
    body: { token, senha }
  });
  return response.message;
}