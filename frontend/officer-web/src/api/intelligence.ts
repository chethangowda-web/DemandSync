/**
 * Phase 8 — typed client for the cross-portal intelligence API.
 * Every function maps 1:1 onto backend/api/intelligence.py. Read-only,
 * except POST /ask which only logs an advisory ai_predictions row.
 */
import { api, post as rawPost } from './client';

export interface Insight {
  insight_id: string;
  type: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  summary: string;
  recommendation: string | null;
  entity_type: string | null;
  entity_id: string | null;
  commodity?: string;
  evidence: { record: string; field?: string; value?: unknown; detail?: string }[];
  calculation: Record<string, unknown>;
  source_records: string[];
  model_type: string;
  model_version: string | null;
  dataset_version: string | null;
  generated_at: string;
  confidence: number | null;
  confidence_display: string;
  stale?: boolean;
  data_timestamp?: string | null;
  status: 'ADVISORY';
}

export interface BriefSection { title: string; lines: string[]; }
export interface OpsBrief {
  cycle: string;
  sections: BriefSection[];
  fps_needing_attention: string[];
  counts: Record<string, number>;
}

export interface AskResponse {
  answer: string;
  evidence: { record: string; value?: unknown; detail?: string }[];
  calculations: unknown[];
  sources: string[];
  intent: string;
  model: string;
  model_version: string;
  advisory: boolean;
  cycle?: string;
  generated_at: string;
}

const q = (o: Record<string, string | undefined>) => {
  const p = Object.entries(o).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v!)}`);
  return p.length ? `?${p.join('&')}` : '';
};

export const intel = {
  dsoSummary: (cycle?: string) =>
    api<{ cycle: string; brief: OpsBrief; insights: Insight[]; counts: Record<string, number> }>(
      `/api/v1/intelligence/dso/summary${q({ cycle })}`),
  dsoDemand: (cycle?: string) =>
    api<{ cycle: string; model: string; note: string; signals: unknown[] }>(
      `/api/v1/intelligence/dso/demand${q({ cycle })}`),
  dsoAnomalies: (cycle?: string) =>
    api<{ cycle: string; anomalies: Insight[] }>(`/api/v1/intelligence/dso/anomalies${q({ cycle })}`),
  dsoRisks: (cycle?: string, kind?: string) =>
    api<{ cycle: string; risks: Insight[] }>(`/api/v1/intelligence/dso/risks${q({ cycle, kind })}`),
  dsoBrief: (cycle?: string) => api<OpsBrief>(`/api/v1/intelligence/dso/brief${q({ cycle })}`),
  dsoExceptions: (cycle?: string) =>
    api<{ cycle: string; exceptions: Insight[] }>(`/api/v1/intelligence/dso/exceptions${q({ cycle })}`),
  allocationExplanation: (cycle: string, fps_id: string, commodity: string) =>
    api<{ answer: string; detail: unknown; evidence: unknown[]; advisory: boolean }>(
      `/api/v1/intelligence/dso/allocation-explanation${q({ cycle, fps_id, commodity })}`),
  inspectorSummary: (cycle?: string) => api<any>(`/api/v1/intelligence/inspector/summary${q({ cycle })}`),
  fpsSummary: (cycle?: string) => api<any>(`/api/v1/intelligence/fps/me/summary${q({ cycle })}`),
  auditorSummary: (cycle?: string) => api<any>(`/api/v1/intelligence/auditor/summary${q({ cycle })}`),
  adminSummary: () => api<{ insights: Insight[]; counts: Record<string, number> }>(
    '/api/v1/intelligence/admin/summary'),
  beneficiarySummary: () => api<any>('/api/v1/intelligence/beneficiary/me/summary'),
  ask: (body: { question: string; context_entity_type?: string; context_entity_id?: string; cycle?: string }) =>
    rawPost<AskResponse>('/api/v1/intelligence/ask', body),
};
