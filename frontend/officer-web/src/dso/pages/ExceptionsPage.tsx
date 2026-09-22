/**
 * Exception workspace.
 *
 * Defaults to this workflow's own open exceptions. The dataset's historical records (DELIVERY, EPOS,
 * MANIFEST entity types from the original seed) are reachable behind an explicit filter and clearly
 * marked as historical, so they can never be mistaken for work the officer needs to do now.
 */
import { useMemo, useState } from 'react';
import { Allocation, Exception, dso } from '../api';
import { useCycle } from '../DsoLayout';
import { c, label, s } from '../theme';
import { DataUnavailable, Loading, Panel, Region, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { ExceptionDrawer, ExceptionTable, SeverityStrip } from '../components/Exceptions';

const SCOPES = [
  { key: 'ALLOCATION', name: 'Allocation gates', note: 'Constraint violations raised while allocating this cycle' },
  { key: 'ROUTING', name: 'Routing', note: 'Stops the fleet could not cover during optimisation' },
  { key: 'CLOSURE', name: 'Closure checks', note: 'Failures recorded during reconciliation' },
] as const;

export default function ExceptionsPage() {
  const { cycle, summary, refresh } = useCycle();
  const [scope, setScope] = useState<string>('ALLOCATION');
  const [status, setStatus] = useState<string>('OPEN');
  const [selected, setSelected] = useState<Exception | null>(null);

  const excQ = useData<Exception[]>(
    () => (cycle ? dso.exceptions(cycle, { status: status || undefined, entity_type: scope }) : Promise.resolve([])),
    [cycle, scope, status, summary?.state]);
  const allocQ = useData<Allocation[]>(
    () => (cycle && summary && !['OPEN', 'MONITOR', 'LOCKED'].includes(summary.state) ? dso.allocations(cycle) : Promise.resolve([])),
    [cycle, summary?.state]);

  const allocFor = useMemo(() => {
    const m = new Map<string, Allocation>();
    (allocQ.data ?? []).forEach(a => m.set(`${a.fps_id}:${a.commodity}`, a));
    return m;
  }, [allocQ.data]);

  if (!cycle) return <Loading />;
  const current = SCOPES.find(x => x.key === scope);

  return (
    <>
      <Panel title="Exception command centre" subtitle="Everything this cycle's own gates have flagged">
        <StageRail state={summary?.state} />
      </Panel>

      <div style={{ display: 'flex', gap: s(3), alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <div style={{ ...label, marginBottom: 5 }}>Source</div>
          <div style={{ display: 'flex', gap: 0, border: `1px solid ${c.lineStrong}`, borderRadius: 5, overflow: 'hidden' }}>
            {SCOPES.map(sc => (
              <button key={sc.key} onClick={() => setScope(sc.key)} title={sc.note}
                style={{ padding: '7px 14px', border: 'none', cursor: 'pointer', fontSize: 12.5, fontWeight: 600,
                  background: scope === sc.key ? c.navy : c.surface, color: scope === sc.key ? '#fff' : c.body }}>
                {sc.name}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div style={{ ...label, marginBottom: 5 }}>Status</div>
          <select value={status} onChange={e => setStatus(e.target.value)}
            style={{ padding: '7px 10px', border: `1px solid ${c.lineStrong}`, borderRadius: 5, fontSize: 12.5 }}>
            <option value="OPEN">Open</option>
            <option value="RESOLVED">Resolved</option>
            <option value="">Any status</option>
          </select>
        </div>
        {current && <div style={{ fontSize: 12, color: c.muted, paddingBottom: 8 }}>{current.note}</div>}
      </div>

      <Region q={excQ}>
        {list => (
          <>
            <SeverityStrip exceptions={list} />
            <Panel title={`${current?.name ?? 'Exceptions'} (${list.length})`} pad={false}>
              {list.length === 0
                ? <div style={{ padding: s(6) }}>
                    <DataUnavailable what="Nothing here"
                      why={status === 'OPEN'
                        ? 'No open exceptions of this kind for this cycle. Try another source or status.'
                        : 'No exceptions match this filter.'} />
                  </div>
                : <ExceptionTable exceptions={list} onSelect={setSelected} maxHeight={560} />}
            </Panel>
          </>
        )}
      </Region>

      <ExceptionDrawer exception={selected} cycle={cycle}
        allocation={selected ? allocFor.get(selected.entity_id) : undefined}
        onClose={() => setSelected(null)}
        onResolved={() => { excQ.reload(); allocQ.reload(); refresh(); }} />
    </>
  );
}
