// Field Food Inspector API client. Every value comes from the backend; nothing is mocked.
import { api, post } from '../api/client';

export interface Summary {
  inspector_id: string; name: string; district: string | null;
  fps_in_district: number; pending: number; submitted: number; today: number;
}

export interface RiskFactor {
  key: string; label: string; level: 'HIGH' | 'MEDIUM' | 'LOW'; detail: string; weight: number;
}

export interface Target {
  fps_id: string; fps_name: string; district: string; taluk: string | null;
  latitude: number | null; longitude: number | null; status: string;
  risk_score: number; risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_factors: RiskFactor[]; recommended_focus: string[];
  last_inspection: string | null; last_finding: string | null;
  inventory: { commodity: string; closing_stock_kg: number | null; cycle: string }[];
  grievances_recent: number; grievances_open: number;
  epos_failed_90d: number; epos_odd_hours_90d: number;
}

export interface Inspection {
  inspection_id: string; fps_id: string; inspector_id: string;
  inspection_date: string | null; status: 'DRAFT' | 'SUBMITTED' | 'SEALED';
  finding: string | null; verification: Record<string, boolean>;
  checklist: Record<string, boolean>; findings: Finding[];
  evidence: EvidenceItem[]; notes: string;
  submitted_at: string | null; updated_at: string | null;
  stock_expected_kg?: number | null; stock_observed_kg?: number | null;
}

export interface Finding {
  category: string; finding: string; severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  notes: string; evidence: string[];
}

export interface EvidenceItem { type: 'photo' | 'document' | 'note' | 'observation'; label: string }

export const inspectorApi = {
  summary: () => api<Summary>('/api/v1/inspector/summary'),
  targets: (limit = 50) => api<{ district: string | null; count: number; high_risk: number; targets: Target[] }>(
    `/api/v1/inspector/targets?limit=${limit}`),
  target: (fpsId: string) => api<any>(`/api/v1/inspector/targets/${encodeURIComponent(fpsId)}`),
  start: (fpsId: string) => post<any>('/api/v1/inspector/inspections', { fps_id: fpsId }),
  list: (status?: string) => api<{ inspections: any[] }>(
    `/api/v1/inspector/inspections${status ? `?status=${status}` : ''}`),
  detail: (id: string) => api<any>(`/api/v1/inspector/inspections/${encodeURIComponent(id)}`),
  update: (id: string, body: object) =>
    api<Inspection>(`/api/v1/inspector/inspections/${encodeURIComponent(id)}`,
      { method: 'PATCH', body: JSON.stringify(body) }),
  submit: (id: string) => post<{ inspection_id: string; fps_id: string; submitted_by: string;
    timestamp: string; status: string }>(`/api/v1/inspector/inspections/${encodeURIComponent(id)}/submit`, {}),
};
