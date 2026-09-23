// Auditor operations API client. Read-only; every value comes from the backend.
import { api, post } from '../api/client';

const q = (district?: string | null) => (district ? `?district=${encodeURIComponent(district)}` : '');

export const auditorApi = {
  cycles: () => api<any>('/api/v1/auditor/cycles'),
  stages: (cycle: string) => api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/stages`),
  overview: (cycle: string) => api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/overview`),
  demand: (cycle: string) => api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/demand`),
  manifests: (cycle: string, district?: string | null) =>
    api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/manifests${q(district)}`),
  manifest: (id: string) => api<any>(`/api/v1/auditor/manifests/${encodeURIComponent(id)}`),
  reconciliation: (cycle: string, district?: string | null, limit = 100, offset = 0) =>
    api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/reconciliation${q(district)}${district ? '&' : '?'}limit=${limit}&offset=${offset}`),
  exceptions: (cycle: string, opts?: { severity?: string; status?: string; district?: string | null }) =>
    api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/exceptions` +
      `?${[opts?.severity && `severity=${opts.severity}`, opts?.status && `status=${opts.status}`,
        opts?.district && `district=${encodeURIComponent(opts.district)}`].filter(Boolean).join('&')}`),
  trace: (cycle: string, action?: string, limit = 200, offset = 0) =>
    api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/trace?limit=${limit}&offset=${offset}${action ? `&action=${encodeURIComponent(action)}` : ''}`),
  closure: (cycle: string) => api<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/closure`),
  ask: (cycle: string, body: { question?: string; intent?: string }) =>
    post<any>(`/api/v1/auditor/cycles/${encodeURIComponent(cycle)}/ask`, body),
};
