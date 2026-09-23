// System Admin API client. Reads are live backend state; the three account
// mutations are audited, reason-gated, and backend-authorized (MANAGE_USERS).
import { api } from '../api/client';

export const adminApi = {
  stages: () => api<any>('/api/v1/admin/stages'),
  overview: () => api<any>('/api/v1/admin/overview'),
  users: (opts?: { role?: string; status?: string; q?: string; limit?: number; offset?: number }) =>
    api<any>(`/api/v1/admin/users?${[
      opts?.role && `role=${encodeURIComponent(opts.role)}`,
      opts?.status && `status=${encodeURIComponent(opts.status)}`,
      opts?.q && `q=${encodeURIComponent(opts.q)}`,
      `limit=${opts?.limit ?? 100}`, `offset=${opts?.offset ?? 0}`].filter(Boolean).join('&')}`),
  user: (id: string) => api<any>(`/api/v1/admin/users/${encodeURIComponent(id)}`),
  updateUser: (id: string, body: { status?: string; role?: string; reason: string }) =>
    api<any>(`/api/v1/admin/users/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  unlockUser: (id: string, reason: string) =>
    api<any>(`/api/v1/admin/users/${encodeURIComponent(id)}/unlock`, { method: 'POST', body: JSON.stringify({ reason }) }),
  rbac: () => api<any>('/api/v1/admin/rbac'),
  datasets: () => api<any>('/api/v1/admin/datasets'),
  health: () => api<any>('/api/v1/admin/health'),
  integrations: () => api<any>('/api/v1/admin/integrations'),
  security: () => api<any>('/api/v1/admin/security'),
  configuration: () => api<any>('/api/v1/admin/configuration'),
  final: () => api<any>('/api/v1/admin/final'),
  ask: (body: { question?: string; intent?: string }) =>
    api<any>('/api/v1/admin/ask', { method: 'POST', body: JSON.stringify(body) }),
};
