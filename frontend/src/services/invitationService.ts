import { apiRequest } from './apiClient';
import type { UserRole } from './userService';

type ApiResponse<T> = { data: T };
export type InvitationRow = { id: number; email: string; role: UserRole; status: 'pending' | 'accepted' | 'expired' | 'revoked'; invitedBy: number | null; expiresAt: string | null; acceptedAt: string | null; criadoEm: string | null; link?: string };

export async function getInvitations(): Promise<InvitationRow[]> { return (await apiRequest<ApiResponse<InvitationRow[]>>('/convites')).data; }
export async function createInvitation(data: { email: string; role: Exclude<UserRole, 'owner'> }): Promise<InvitationRow> { return (await apiRequest<ApiResponse<InvitationRow>>('/convites', { method: 'POST', body: data })).data; }
export async function revokeInvitation(id: number): Promise<InvitationRow> { return (await apiRequest<ApiResponse<InvitationRow>>(`/convites/${id}/revogar`, { method: 'POST' })).data; }
