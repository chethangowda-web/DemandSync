/**
 * Audit & decision trace.
 *
 * Every entry is a real row from the hash-chained audit_events table. The timeline answers WHO did
 * WHAT, WHEN, WHY and with what RESULT — the before/after values on an override are the officer's own
 * recorded decision, not a reconstruction.
 */
import { useMemo, useState } from 'react';
import { AuditEvent, dso } from '../api';
import { useCycle } from '../DsoLayout';
import { c, dateTime, font, label, s, toneFor } from '../theme';
import { Badge, DataUnavailable, Loading, Panel, Region, useData } from '../ui';
import { StageRail } from '../components/Situation';

/** Officer-facing wording for the actions this workflow records. */
const ACTIONS: Record<string, string> = {
  LOGIN_SUCCESS: 'Officer signed in',
  LOGIN_FAILURE: 'Failed sign-in attempt',
  FORECAST_GENERATED: 'Demand forecast generated',
  CHOICE_WINDOW_CLOSED: 'Choice window closed',
  DEMAND_LOCKED: 'Demand sealed',
  CYCLE_ALLOCATED: 'Allocation run',
  ALLOCATION_OVERRIDDEN: 'Allocation overridden by officer',
  CYCLE_OPTIMIZED: 'Routes optimised',
  MANIFEST_VALIDATED: 'Manifest validated',
  MANIFEST_LOCKED: 'Manifest sealed',
  CYCLE_AUTHORIZED: 'Dispatch authorised',
  CYCLE_DISPATCHED: 'Vehicles released',
  DELIVERY_RECORDED: 'Delivery recorded',
  CYCLE_RECONCILED: 'Reconciliation run',
  CYCLE_CLOSED: 'Cycle closed',
  CREDENTIAL_BOOTSTRAP: 'First officer credential provisioned',
  PASSWORD_SET: 'Password set',
};

const DECISIVE = new Set(['ALLOCATION_OVERRIDDEN', 'CYCLE_AUTHORIZED', 'CYCLE_CLOSED', 'DEMAND_LOCKED', 'MANIFEST_LOCKED']);

export default function AuditPage() {
  const { cycle, summary } = useCycle();
  const [onlyDecisions, setOnlyDecisions] = useState(false);
  const [onlyThisCycle, setOnlyThisCycle] = useState(true);

  const q = useData<AuditEvent[]>(() => dso.audit(200), [cycle, summary?.state]);

  const events = useMemo(() => {
    let e = q.data ?? [];
    if (onlyThisCycle && cycle) e = e.filter(x => x.entity_id === cycle || x.entity_type === 'CYCLE' || x.reason?.includes(cycle) || DECISIVE.has(x.action));
    if (onlyDecisions) e = e.filter(x => DECISIVE.has(x.action));
    return e;
  }, [q.data, onlyDecisions, onlyThisCycle, cycle]);

  if (!cycle) return <Loading />;

  return (
    <>
      <Panel title="Audit & decision trace" subtitle="Hash-chained, append-only — entries can never be edited or removed">
        <StageRail state={summary?.state} />
      </Panel>

      <div style={{ display: 'flex', gap: s(4), alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12.5, color: c.body, display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={onlyDecisions} onChange={e => setOnlyDecisions(e.target.checked)} />
          Only officer decisions
        </label>
        <label style={{ fontSize: 12.5, color: c.body, display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={onlyThisCycle} onChange={e => setOnlyThisCycle(e.target.checked)} />
          Related to {cycle}
        </label>
        <span style={{ fontSize: 11.5, color: c.muted }}>
          Showing the most recent {events.length} of up to 200 events
        </span>
      </div>

      <Panel title="Decision timeline">
        <Region q={q}>
          {() => events.length === 0
            ? <DataUnavailable what="No audit events" why="Nothing has been recorded for this filter yet." />
            : (
              <ol style={{ listStyle: 'none', margin: 0, padding: 0, position: 'relative' }}>
                <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: c.line }} />
                {events.map(e => {
                  const decisive = DECISIVE.has(e.action);
                  const failed = e.result !== 'SUCCESS';
                  return (
                    <li key={e.audit_event_id} style={{ display: 'grid', gridTemplateColumns: '16px 1fr',
                      gap: s(4), padding: `${s(3)} 0`, position: 'relative' }}>
                      <span aria-hidden style={{ width: 16, height: 16, borderRadius: '50%', marginTop: 2,
                        background: failed ? c.bad : decisive ? c.navy : c.surface,
                        border: `2px solid ${failed ? c.bad : decisive ? c.navy : c.lineStrong}`, zIndex: 1 }} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: s(3), flexWrap: 'wrap' }}>
                          <span style={{ font: `${decisive ? 700 : 600} 13px ${font.ui}`, color: c.ink }}>
                            {ACTIONS[e.action] ?? e.action.replace(/_/g, ' ').toLowerCase()}
                          </span>
                          {decisive && <Badge t="accent">Officer decision</Badge>}
                          <Badge t={toneFor(e.result)}>{e.result}</Badge>
                          <span style={{ marginLeft: 'auto', fontSize: 11.5, color: c.muted, fontFamily: font.mono }}>
                            {dateTime(e.timestamp)}
                          </span>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: `2px ${s(3)}`,
                          marginTop: 6, fontSize: 12 }}>
                          <span style={label}>Who</span>
                          <span style={{ color: c.body }}>{e.actor_user_id} <span style={{ color: c.faint }}>({e.actor_role})</span></span>
                          <span style={label}>What</span>
                          <span style={{ color: c.body, fontFamily: font.mono, fontSize: 11.5 }}>
                            {e.entity_type} · {e.entity_id}
                          </span>
                          {e.reason && <>
                            <span style={label}>Why</span>
                            <span style={{ color: c.ink, overflowWrap: 'anywhere' }}>{e.reason}</span>
                          </>}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
        </Region>
      </Panel>
    </>
  );
}
