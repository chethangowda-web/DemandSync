export type StageStatus = 'COMPLETE' | 'ACTIVE' | 'PENDING';
export interface Stage { key: string; label: string; status: StageStatus; }

// The real 11-state backend cycle machine (backend/services/beneficiary.py:CYCLE_STATES), grouped into
// the 7 stages the DSO UI shows. Status is always computed from the cycle's actual `state` -- see
// stagesFor() below -- never hardcoded.
export const CYCLE_STATES = ['OPEN', 'MONITOR', 'LOCKED', 'ALLOCATED', 'OPTIMIZED', 'AUTHORIZED', 'TRACKING',
  'DELIVERING', 'RECONCILING', 'AUDITING', 'CLOSED'] as const;

const STAGE_DEFS: { key: string; label: string; states: string[] }[] = [
  { key: 'MONITOR', label: '01 MONITOR', states: ['OPEN', 'MONITOR'] },
  { key: 'LOCK', label: '02 LOCK', states: ['LOCKED'] },
  { key: 'ALLOCATE', label: '03 ALLOCATE', states: ['ALLOCATED'] },
  { key: 'OPTIMIZE', label: '04 OPTIMIZE', states: ['OPTIMIZED'] },
  { key: 'AUTHORIZE', label: '05 AUTHORIZE', states: ['AUTHORIZED'] },
  { key: 'TRACK', label: '06 TRACK & DELIVER', states: ['TRACKING', 'DELIVERING'] },
  { key: 'CLOSE', label: '07 RECONCILE & CLOSE', states: ['RECONCILING', 'AUDITING', 'CLOSED'] },
];

export function stagesFor(cycleState: string): Stage[] {
  const idx = CYCLE_STATES.indexOf(cycleState as any);
  return STAGE_DEFS.map(d => {
    const stateIdxs = d.states.map(s => CYCLE_STATES.indexOf(s as any));
    const status: StageStatus = idx > Math.max(...stateIdxs) ? 'COMPLETE' : stateIdxs.includes(idx) ? 'ACTIVE' : 'PENDING';
    return { key: d.key, label: d.label, status };
  });
}

export interface AISignal { service: string; prediction: number; confidence: number; reason: string; supporting_data: any; model_version: string; generated_at: string; }
