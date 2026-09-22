/**
 * Typed access to the real Phase 2 DSO API. Every function here maps 1:1 onto an endpoint that exists
 * in backend/api/dso.py — there is no mock layer, no fixture data and no client-side invention of
 * operational figures. If the backend has no answer, the response carries null and the UI says so.
 */
import { api, post as rawPost } from '../api/client';

export const CYCLE_STATES = ['OPEN', 'MONITOR', 'LOCKED', 'ALLOCATED', 'OPTIMIZED', 'AUTHORIZED', 'TRACKING',
  'DELIVERING', 'RECONCILING', 'AUDITING', 'CLOSED'] as const;
export type CycleState = typeof CYCLE_STATES[number];

export interface CycleRow { cycle: string; state: CycleState; choice_window_start: string | null; choice_window_end: string | null; locked_at: string | null; closed_at: string | null; }

export interface Summary {
  cycle: string; state: CycleState; locked_at: string | null; closed_at: string | null;
  intent: { submissions: number; beneficiaries: number; kg: number; eligible_beneficiaries: number; participation_pct: number | null };
  forecast: { kg: number | null; baseline_kg: number | null; generated: boolean; vs_baseline_pct: number | null; intent_vs_forecast_kg: number | null };
  demand_lock: { locked: boolean; sha256_hash: string | null; locked_at: string | null; locked_by: string | null };
  allocation: { rows: number; allocated_kg: number; approved: number; blocked: number; overridden: number };
  exceptions: { critical: number; medium: number; low: number; open_total: number };
  manifests: { by_status: Record<string, number>; count: number; total_kg: number; route_km: number };
  fleet: { by_status: Record<string, number>; total: number; available: number };
  coverage: { active_fps: number; fps_with_approved_allocation: number; pct: number | null };
  delivery: { records: number; delivered_kg: number; variance: number; rejected: number };
}

export interface DemandRow {
  fps_id: string; commodity: string; intent_demand_kg: number; intent_count: number;
  baseline_demand_kg: number | null; baseline_cycles_used: number;
  forecast_demand_kg: number | null; forecast_confidence: number | null;
  intent_minus_forecast_kg?: number; forecast_minus_baseline_kg?: number;
}

export interface Allocation { allocation_id: string; fps_id: string; commodity: string; requested_kg: number; allocated_kg: number; warehouse_id: string; status: 'APPROVED' | 'BLOCKED'; source: string | null; approved_by: string | null; approved_at: string | null; }

export interface Exception { exception_id: string; entity_type: string; entity_id: string; rule_code: string; severity: 'HIGH' | 'MEDIUM' | 'LOW'; reason: string; detected_at: string; assigned_to: string | null; status: string; resolution: string | null; resolved_at: string | null; }

export interface Manifest { manifest_id: string; warehouse_id: string; vehicle_id: string; manifest_status: string; total_kg: number; route_distance_km: number | null; route_duration_min: number | null; constraint_status: string; created_by: string | null; created_at: string | null; }

export interface ManifestDetail extends Manifest {
  cycle: string; distance_basis: string;
  items: { manifest_item_id: string; fps_id: string; commodity: string; planned_kg: number; sequence_number: number; allocation_id: string }[];
  route: { fps_id: string; stop_sequence: number; latitude: number; longitude: number; distance_from_previous_km: number | null; eta_minutes: number | null; route_status: string }[];
}

export interface Vehicle { vehicle_id: string; vehicle_number: string; vehicle_type: string; capacity_kg: number; current_status: string; warehouse_id: string; latitude: number | null; longitude: number | null; manifest_id: string | null; manifest_status: string | null; assigned_kg: number | null; route_distance_km: number | null; utilisation_pct: number | null; }

export interface Fleet { cycle: string; vehicles: Vehicle[]; totals: { fleet_size: number; available: number; assigned_this_cycle: number; fleet_capacity_kg: number; assigned_load_kg: number }; }

export interface Delivery { delivery_id: string; manifest_id: string; fps_id: string; vehicle_id: string; commodity: string; planned_kg: number; delivered_kg: number; variance_kg: number; delivery_date: string | null; status: 'VERIFIED' | 'VARIANCE' | 'REJECTED'; verified_by: string | null; allocation_id: string; }

export interface RouteStop { manifest_id: string; vehicle_id: string; warehouse_id: string; stop_sequence: number; fps_id: string; latitude: number; longitude: number; distance_from_previous_km: number | null; eta_minutes: number | null; route_status: string; }
export interface TelemetryPoint { telemetry_id: string; vehicle_id: string; timestamp: string; latitude: number | null; longitude: number | null; speed_kmph: number | null; status: string; manifest_id: string; }

export interface AuditEvent { audit_event_id: string; actor_user_id: string; actor_role: string; action: string; entity_type: string; entity_id: string; result: string; reason: string | null; timestamp: string; }

export interface AiForecast { service: string; prediction: number; unit: string; confidence: number; reason: string; supporting_data: Record<string, unknown>; model_version: string; generated_at: string; affected_entities: string[]; what_next: string; }

export type ClosureChecks = Record<string, boolean>;

const q = (o: Record<string, string | undefined>) => {
  const p = Object.entries(o).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v!)}`);
  return p.length ? `?${p.join('&')}` : '';
};

export const dso = {
  cycles: () => api<{ cycles: CycleRow[] }>('/api/v1/cycles').then(r => r.cycles),
  cycle: (c: string) => api<any>(`/api/v1/cycles/${c}`),
  summary: (c: string) => api<Summary>(`/api/v1/cycles/${c}/summary`),

  demand: (c: string) => api<{ rows: DemandRow[]; participation: { submitted: number; eligible: number; participation_pct: number }; forecast_generated: boolean }>(`/api/v1/cycles/${c}/demand`),
  runForecast: (c: string) => rawPost(`/api/v1/cycles/${c}/forecast`),
  aiForecast: (c: string, fps: string, commodity: string) => api<AiForecast>(`/api/v1/ai/forecast?cycle=${c}&fps_id=${fps}&commodity=${commodity}`),
  demandLock: (c: string) => api<{ sha256_hash: string; hash_verified: boolean; locked_at: string; locked_by: string }>(`/api/v1/cycles/${c}/demand-lock`),
  closeChoiceWindow: (c: string) => rawPost(`/api/v1/cycles/${c}/choice-window/close`),

  constraintsPreview: (c: string) => api<{ fps_commodity_pairs: number; blocking_exceptions: number; warning_exceptions: number; findings: any[] }>(`/api/v1/cycles/${c}/constraints/preview`),
  allocate: (c: string) => rawPost(`/api/v1/cycles/${c}/allocate`),
  allocations: (c: string) => api<{ allocations: Allocation[] }>(`/api/v1/cycles/${c}/allocations`).then(r => r.allocations),
  exceptions: (c: string, opts: { status?: string; entity_type?: string } = {}) =>
    api<{ exceptions: Exception[] }>(`/api/v1/cycles/${c}/exceptions${q(opts)}`).then(r => r.exceptions),
  override: (c: string, fps: string, commodity: string, allocated_kg: number, reason: string) =>
    rawPost(`/api/v1/cycles/${c}/allocations/${fps}/${commodity}/override`, { allocated_kg, reason }),

  optimize: (c: string) => rawPost(`/api/v1/cycles/${c}/optimize`),
  manifests: (c: string) => api<{ manifests: Manifest[] }>(`/api/v1/cycles/${c}/manifests`).then(r => r.manifests),
  manifest: (id: string) => api<ManifestDetail>(`/api/v1/manifests/${id}`),
  validateManifest: (id: string) => rawPost(`/api/v1/manifests/${id}/validate`),
  lockManifest: (id: string) => rawPost(`/api/v1/manifests/${id}/lock`),
  lockVerification: (id: string) => api<{ sha256_hash: string; hash_verified: boolean }>(`/api/v1/manifests/${id}/lock-verification`),
  qr: (id: string) => api<{ qr_png_base64: string }>(`/api/v1/manifests/${id}/qr`),

  fleet: (c: string) => api<Fleet>(`/api/v1/cycles/${c}/fleet`),
  authorize: (c: string) => rawPost(`/api/v1/cycles/${c}/authorize`),
  dispatch: (c: string) => rawPost(`/api/v1/cycles/${c}/dispatch`),
  tracking: (c: string) => api<{ planned_routes: RouteStop[]; telemetry: TelemetryPoint[] }>(`/api/v1/cycles/${c}/tracking`),
  deliver: (id: string, items: { fps_id: string; commodity: string; delivered_kg: number }[]) => rawPost(`/api/v1/manifests/${id}/deliver`, { items }),
  deliveries: (c: string) => api<{ deliveries: Delivery[] }>(`/api/v1/cycles/${c}/deliveries`).then(r => r.deliveries),

  closureChecks: (c: string) => api<{ checks: ClosureChecks; passed: boolean }>(`/api/v1/cycles/${c}/closure-checks`),
  reconcile: (c: string) => rawPost<{ checks: ClosureChecks; passed: boolean; state: string }>(`/api/v1/cycles/${c}/reconcile`),
  close: (c: string) => rawPost(`/api/v1/cycles/${c}/close`),

  audit: (limit = 120) => api<{ events: AuditEvent[] }>(`/api/v1/auth/audit?limit=${limit}`).then(r => r.events),
};

/** The 7 officer-facing stages, as a view over the 11 backend states. */
export const STAGES: { key: string; label: string; short: string; states: CycleState[]; route: string }[] = [
  { key: 'MONITOR', label: 'Monitor', short: '01', states: ['OPEN', 'MONITOR'], route: '/dso/demand' },
  { key: 'LOCK', label: 'Validate & Lock', short: '02', states: ['LOCKED'], route: '/dso/demand' },
  { key: 'ALLOCATE', label: 'Allocate', short: '03', states: ['ALLOCATED'], route: '/dso/allocation' },
  { key: 'OPTIMIZE', label: 'Optimize', short: '04', states: ['OPTIMIZED'], route: '/dso/optimization' },
  { key: 'AUTHORIZE', label: 'Authorize', short: '05', states: ['AUTHORIZED'], route: '/dso/dispatch' },
  { key: 'TRACK', label: 'Track & Deliver', short: '06', states: ['TRACKING', 'DELIVERING'], route: '/dso/tracking' },
  { key: 'CLOSE', label: 'Reconcile & Close', short: '07', states: ['RECONCILING', 'AUDITING', 'CLOSED'], route: '/dso/reconciliation' },
];

export type StageStatus = 'COMPLETE' | 'ACTIVE' | 'PENDING';

export function stageStatuses(state: CycleState | undefined): { key: string; label: string; short: string; status: StageStatus; route: string }[] {
  const i = state ? CYCLE_STATES.indexOf(state) : -1;
  return STAGES.map(st => {
    const idx = st.states.map(x => CYCLE_STATES.indexOf(x));
    const status: StageStatus = i > Math.max(...idx) ? 'COMPLETE' : idx.includes(i) ? 'ACTIVE' : 'PENDING';
    return { key: st.key, label: st.label, short: st.short, status, route: st.route };
  });
}
