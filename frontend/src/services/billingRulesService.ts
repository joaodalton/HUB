import { apiRequest } from './apiClient';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type BillingRule = {
  id: number;
  empresaId: number;
  nome: string;
  descricao: string | null;
  ativo: boolean;
  padrao: boolean;
  calculationMethod: string;
  tariffSource: 'invoice' | 'manual';
  manualTariff: string | null;
  tariffConfiguration: {
    companyTariff: string | null;
    tariffHfp: string | null;
    tariffHp: string | null;
  };
  billingModifiers: {
    excludePisCofins: boolean | null;
    icmsPolicy: 'exclude' | null;
    excludeTariffFlag: boolean | null;
    recurringAdditionalCost: string | null;
    gracePeriod: {
      enabled: boolean | null;
      withoutDiscount: boolean | null;
      durationMonths: number | null;
      start: string | null;
      end: string | null;
    };
  };
  discountType: 'none' | 'percentage' | 'fixed';
  discountValue: string | null;
  tariffBasis: string;
  energyComponentIndex: number | null;
  billingMode: string;
  dueDateBasis: string;
  dueDateOffsetDays: number;
  monthlyInterest: string | null;
  finePercentage: string | null;
  revision: number;
  criadoEm: string;
  atualizadoEm: string;
};

export type BillingRuleAssignment = {
  id: number;
  empresaId: number;
  grupoRegraCobrancaId: number;
  scopeType: 'company' | 'client' | 'consumer_unit';
  clientId: number | null;
  consumerUnitId: number | null;
  ativo: boolean;
  criadoEm: string;
  atualizadoEm: string;
};

export type BillingRuleInput = Pick<BillingRule, 'nome' | 'descricao' | 'calculationMethod' |
  'tariffSource' | 'discountType' | 'discountValue' | 'tariffBasis' | 'energyComponentIndex' |
  'billingMode' | 'dueDateBasis' | 'dueDateOffsetDays' | 'monthlyInterest' | 'finePercentage'> & {
  tariffConfiguration: Pick<BillingRule['tariffConfiguration'], 'companyTariff' | 'tariffHfp' | 'tariffHp'>;
  billingModifiers: Pick<BillingRule['billingModifiers'], 'excludePisCofins' | 'icmsPolicy' |
    'excludeTariffFlag' | 'recurringAdditionalCost'> & {
    gracePeriod: Pick<BillingRule['billingModifiers']['gracePeriod'], 'enabled' | 'withoutDiscount' | 'durationMonths'>;
  };
};

export async function listBillingRules(): Promise<BillingRule[]> {
  return (await apiRequest<ApiResponse<BillingRule[]>>('/billing-rules')).data;
}

export async function getBillingRule(id: number): Promise<BillingRule> {
  return (await apiRequest<ApiResponse<BillingRule>>(`/billing-rules/${id}`)).data;
}

export async function createBillingRule(input: BillingRuleInput): Promise<BillingRule> {
  return (await apiRequest<ApiResponse<BillingRule>>('/billing-rules', { method: 'POST', body: input })).data;
}

export async function updateBillingRule(id: number, input: Partial<BillingRuleInput> &
  Partial<Pick<BillingRule, 'ativo' | 'padrao'>>): Promise<BillingRule> {
  return (await apiRequest<ApiResponse<BillingRule>>(`/billing-rules/${id}`, { method: 'PATCH', body: input })).data;
}

export async function listBillingRuleAssignments(filters: Record<string, string> = {}): Promise<BillingRuleAssignment[]> {
  const query = new URLSearchParams(filters).toString();
  return (await apiRequest<ApiResponse<BillingRuleAssignment[]>>(
    `/billing-rule-assignments${query ? `?${query}` : ''}`)).data;
}

export async function createBillingRuleAssignment(input: {
  grupoRegraCobrancaId: number;
  scopeType: BillingRuleAssignment['scopeType'];
  clientId?: number;
  consumerUnitId?: number;
}): Promise<BillingRuleAssignment> {
  return (await apiRequest<ApiResponse<BillingRuleAssignment>>('/billing-rule-assignments', {
    method: 'POST', body: input
  })).data;
}

export async function updateBillingRuleAssignment(id: number, input: {
  grupoRegraCobrancaId?: number;
  ativo?: boolean;
}): Promise<BillingRuleAssignment> {
  return (await apiRequest<ApiResponse<BillingRuleAssignment>>(`/billing-rule-assignments/${id}`, {
    method: 'PATCH', body: input
  })).data;
}
