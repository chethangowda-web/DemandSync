/**
 * The operational situation header: what cycle this is, what stage it is in, and how far it has moved.
 *
 * Stage status is computed from the cycle's real backend state (api.ts:stageStatuses) — the 7 stages
 * shown are a view over the 11-state machine, never a second source of truth.
 */
import { Link } from 'react-router-dom';
import { CycleState, stageStatuses } from '../api';
import { c, font, label, s, tone } from '../theme';
import { Badge } from '../ui';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function cycleTitle(cycle: string) {
  const [y, m] = cycle.split('-');
  const idx = Number(m) - 1;
  return MONTHS[idx] ? `${MONTHS[idx]} ${y} Distribution Cycle` : `${cycle} Distribution Cycle`;
}

export function StageRail({ state, compact }: { state: CycleState | undefined; compact?: boolean }) {
  const stages = stageStatuses(state);
  return (
    <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, flexWrap: 'wrap' }}>
      {stages.map((st, i) => {
        const done = st.status === 'COMPLETE';
        const active = st.status === 'ACTIVE';
        const fg = done ? c.ok : active ? c.navy : c.faint;
        return (
          <Link key={st.key} to={st.route} title={`${st.label} — ${st.status}`} style={{
            textDecoration: 'none', display: 'flex', alignItems: 'center', gap: s(2),
            padding: `${s(2)} ${s(3)}`, minWidth: 0,
            borderBottom: `3px solid ${active ? '#F5C518' : done ? c.okLine : 'transparent'}`,
            background: active ? c.accentBg : 'transparent',
          }}>
            <span style={{
              width: 20, height: 20, borderRadius: '50%', flex: '0 0 20px', display: 'grid', placeItems: 'center',
              fontSize: 10, fontWeight: 700, color: done || active ? '#fff' : c.muted,
              background: done ? c.ok : active ? c.navy : c.idleBg, border: `1px solid ${done ? c.ok : active ? c.navy : c.lineStrong}`,
            }}>{done ? '✓' : st.short}</span>
            {!compact && (
              <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                <span style={{ fontSize: 12.5, fontWeight: active ? 700 : 500, color: fg, whiteSpace: 'nowrap' }}>{st.label}</span>
                <span style={{ ...label, fontSize: 9.5, color: c.faint }}>{st.status}</span>
              </span>
            )}
            {i < stages.length - 1 && <span style={{ width: 10, height: 1, background: c.lineStrong, marginLeft: s(2) }} />}
          </Link>
        );
      })}
    </div>
  );
}

export function SituationHeader({ cycle, state, lockedAt, closedAt }:
  { cycle: string; state: CycleState | undefined; lockedAt?: string | null; closedAt?: string | null }) {
  const t = state === 'CLOSED' ? 'ok' : 'accent';
  return (
    <section style={{ background: c.surface, border: `1px solid ${c.line}`, borderRadius: 6, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: s(5),
        padding: `${s(4)} ${s(5)}`, background: c.navy, color: '#fff' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ ...label, color: '#7FA8D4' }}>PDS Operations</div>
          <h1 style={{ font: `700 21px ${font.ui}`, margin: '4px 0 0', letterSpacing: '-0.015em' }}>{cycleTitle(cycle)}</h1>
          <div style={{ fontSize: 11.5, color: '#9FC0E0', marginTop: 5 }}>
            {closedAt ? `Closed ${new Date(closedAt).toLocaleString('en-IN')}`
              : lockedAt ? `Demand locked ${new Date(lockedAt).toLocaleString('en-IN')}`
              : 'Demand not yet locked'}
          </div>
        </div>
        <div style={{ textAlign: 'right', flex: '0 0 auto' }}>
          <div style={{ ...label, color: '#7FA8D4' }}>Cycle status</div>
          <div style={{ marginTop: 6, display: 'inline-block', padding: '5px 14px', borderRadius: 4,
            background: state === 'CLOSED' ? c.ok : '#F5C518', color: state === 'CLOSED' ? '#fff' : c.navyDeep,
            font: `700 13px ${font.ui}`, letterSpacing: '0.06em' }}>{state ?? '—'}</div>
        </div>
      </div>
      <div style={{ padding: `${s(2)} ${s(3)}`, borderTop: `1px solid ${c.line}` }}>
        <StageRail state={state} />
      </div>
    </section>
  );
}

/** Decision banner: what the officer should do at this stage, and where. */
export function NextAction({ state }: { state: CycleState | undefined }) {
  const map: Partial<Record<CycleState, { text: string; to: string; cta: string }>> = {
    OPEN: { text: 'Beneficiary intent is still being collected. Review demand, then lock it to freeze the cycle.', to: '/dso/demand', cta: 'Go to Demand Intelligence' },
    MONITOR: { text: 'Beneficiary intent is still being collected. Review demand, then lock it to freeze the cycle.', to: '/dso/demand', cta: 'Go to Demand Intelligence' },
    LOCKED: { text: 'Demand is sealed. Run the constraint engine to produce an allocation.', to: '/dso/allocation', cta: 'Go to Allocation' },
    ALLOCATED: { text: 'Allocation is proposed. Resolve blocked items, then optimise vehicle routes.', to: '/dso/optimization', cta: 'Go to Optimization' },
    OPTIMIZED: { text: 'Routes are planned. Validate and seal each manifest, then authorise dispatch.', to: '/dso/dispatch', cta: 'Go to Dispatch' },
    AUTHORIZED: { text: 'Dispatch is authorised. Release the vehicles to begin tracking.', to: '/dso/dispatch', cta: 'Go to Dispatch' },
    TRACKING: { text: 'Vehicles are en route. Record deliveries as they are confirmed at each FPS.', to: '/dso/tracking', cta: 'Go to Tracking' },
    DELIVERING: { text: 'Deliveries are being recorded. Reconcile once every manifest is complete.', to: '/dso/reconciliation', cta: 'Go to Reconciliation' },
    RECONCILING: { text: 'Reconciliation found unresolved issues. Review the closure checks.', to: '/dso/reconciliation', cta: 'Review closure gate' },
    AUDITING: { text: 'All closure checks passed. The cycle is ready to close.', to: '/dso/reconciliation', cta: 'Close the cycle' },
    CLOSED: { text: 'This cycle is closed. Its decision trail is permanently auditable.', to: '/dso/audit', cta: 'View audit trail' },
  };
  const a = state ? map[state] : undefined;
  if (!a) return null;
  const done = state === 'CLOSED';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: s(4), padding: `${s(3)} ${s(4)}`,
      background: done ? tone.ok.bg : tone.accent.bg, border: `1px solid ${done ? tone.ok.line : tone.accent.line}`,
      borderRadius: 6 }}>
      <Badge t={done ? 'ok' : 'accent'}>{done ? 'Complete' : 'Next action'}</Badge>
      <span style={{ fontSize: 13, color: c.ink, flex: 1, minWidth: 0 }}>{a.text}</span>
      <Link to={a.to} style={{ font: `600 12.5px ${font.ui}`, color: '#fff', background: done ? c.ok : c.navy,
        padding: '7px 14px', borderRadius: 5, textDecoration: 'none', whiteSpace: 'nowrap' }}>{a.cta} →</Link>
    </div>
  );
}
