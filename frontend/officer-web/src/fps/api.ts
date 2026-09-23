// FPS Owner operations API client. Every value comes from the backend; nothing is mocked.
import { api, post } from '../api/client';

export interface Shop { fps_id: string; fps_name: string; district: string; taluk: string | null; status: string }

export const fpsApi = {
  me: (fpsId?: string) =>
    api<any>(`/api/v1/fps/me${fpsId ? `?fps_id=${encodeURIComponent(fpsId)}` : ''}`),
  shops: () => api<{ shops: Shop[] }>('/api/v1/fps/me/shops'),
  overview: () => api<any>('/api/v1/fps/me/overview'),
  stock: () => api<any>('/api/v1/fps/me/stock'),
  incoming: () => api<any>('/api/v1/fps/me/incoming'),
  receive: (body: { commodity: string; quantity_kg: number; reason: string; reference?: string }) =>
    post<any>('/api/v1/fps/me/stock/receive', body),
  adjust: (body: { commodity: string; quantity_kg: number; reason: string }) =>
    post<any>('/api/v1/fps/me/stock/adjust', body),
  epos: () => api<any>('/api/v1/fps/me/epos'),
  transactions: (status?: string, limit = 50, offset = 0) =>
    api<any>(`/api/v1/fps/me/transactions?limit=${limit}&offset=${offset}${status ? `&status=${status}` : ''}`),
  beneficiaries: (q?: string, pendingOnly = false, limit = 50, offset = 0) =>
    api<any>(`/api/v1/fps/me/beneficiaries?limit=${limit}&offset=${offset}` +
      `${q ? `&q=${encodeURIComponent(q)}` : ''}${pendingOnly ? '&pending_only=true' : ''}`),
  beneficiary: (id: string) => api<any>(`/api/v1/fps/me/beneficiaries/${encodeURIComponent(id)}`),
  distribute: (body: { beneficiary_id: string; commodity: string; quantity_kg: number; client_ref?: string }) =>
    post<any>('/api/v1/fps/me/distribute', body),
  reconciliation: () => api<any>('/api/v1/fps/me/reconciliation'),
  reviewVariance: (body: { commodity: string; note: string }) =>
    post<any>('/api/v1/fps/me/reconciliation/review', body),
  requests: () => api<any>('/api/v1/fps/me/requests'),
  createRequest: (body: { commodity: string; requested_kg: number; reason: string; requested_delivery_date?: string }) =>
    post<any>('/api/v1/fps/me/requests', body),
  submitRequest: (id: string) => post<any>(`/api/v1/fps/me/requests/${encodeURIComponent(id)}/submit`, {}),
  receiveRequest: (id: string) => post<any>(`/api/v1/fps/me/requests/${encodeURIComponent(id)}/receive`, {}),
  withdrawRequest: (id: string) =>
    api<any>(`/api/v1/fps/me/requests/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  closeStatus: () => api<any>('/api/v1/fps/me/close-day'),
  closeDay: () => post<any>('/api/v1/fps/me/close-day', {}),
  alerts: () => api<any>('/api/v1/fps/me/alerts'),
  insights: () => api<any>('/api/v1/fps/me/insights'),
};
