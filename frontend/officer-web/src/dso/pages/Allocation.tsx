/**
 * Allocation workspace — stage 03.
 *
 * The allocation table is a working surface, not a spreadsheet dump: it defaults to what needs a
 * decision (blocked items), and every override goes through the audited drawer with a mandatory reason.
 */
import { useMemo, useState } from 'react';
import { useCycle } from '../DsoLayout';
import { Allocation as Alloc, Exception, dso } from '../api';
import { c, font, kg, label, num, s } from '../theme';
import { Badge, Bar, DataUnavailable, ErrorNote, Loading, Metric, MetricStrip, Panel, Region, Table, td, tdMono, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { ActionCard } from '../components/Gate';
import { ExceptionDrawer } from '../components/Exceptions';

export default function AllocationPage() {
  const { cycle, summary, refresh } = useCycle();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ exc: Exception; alloc?: Alloc } | null>(null);
  const [status, setStatus] = useState<'BLOCKED' | 'ALL'>('BLOCKED');
  const [commodity, setCommodity] = useState<'ALL' | 'RICE' | 'WHEAT'>('ALL');
  const [fpsFilter, setFpsFilter] = useState('');

  const allocQ = useData<Alloc[]>(() => (cycle ? dso.allocations(cycle) : Promise.resolve([])), [cycle, summary?.state]);
  const excQ = useData<Exception[]>(() => (cycle ? dso.exceptions(cycle, { status: 'OPEN', entity_type: 'ALLOCATION' }) : Promise.resolve([])), [cycle, summary?.state]);

  const excByEntity = useMemo(() => {
    const m = new Map<string, Exception[]>();
    (excQ.data ?? []).forEach(e => { const k = e.entity_id; m.set(k, [...(m.get(k) ?? []), e]); });
    return m;
  }, [excQ.data]);

  if (!cycle) return <Loading />;
  const notAllocatedYet = summary && ['OPEN', 'MONITOR', 'LOCKED'].includes(summary.state);

  const rows = (allocQ.data ?? []).filter(a => {
    if (status === 'BLOCKED' && a.status !== 'BLOCKED') return false;
    if (commodity !== 'ALL' && a.commodity !== commodity) return false;
    if (fpsFilter && !a.fps_id.toLowerCase().includes(fpsFilter.toLowerCase())) return false;
    return true;
  });

  const allocate = async () => {
    setBusy(true); setErr(null);
    try { await dso.allocate(cycle); allocQ.reload(); excQ.reload(); refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); } finally { setBusy(false); }
  };

  const openFor = (a: Alloc) => {
    const list = excByEntity.get(`${a.fps_id}:${a.commodity}`) ?? [];
    const exc = list.find(e => e.severity === 'HIGH') ?? list[0];
    if (exc) setSelected({ exc, alloc: a });
  };

  return (
    <>
      <Panel title="Allocation control" subtitle="Stage 03 · six constraint gates over the sealed demand">
        <StageRail state={summary?.state} />
      </Panel>

      {err && <ErrorNote error={err} />}

      {notAllocatedYet ? (
        <ActionCard
          title="Run allocation"
          body={summary?.state === 'LOCKED'
            ? <>Demand is sealed. Running allocation evaluates all six constraint gates — NFSA entitlement floor, FPS capacity, warehouse stock, vehicle capacity, route feasibility and demand coverage — and proposes a quantity for every FPS and commodity. Anything a gate blocks is recorded as an exception rather than silently adjusted.</>
            : <>Demand must be locked before an allocation can be proposed. The cycle is currently {summary?.state}.</>}
          action="Run allocation"
          disabled={summary?.state !== 'LOCKED'}
          busy={busy}
          onAction={allocate}
        />
      ) : (
        <MetricStrip>
          <Metric name="Allocation lines" value={num(summary?.allocation.rows)} hint={`${summary?.allocation.approved ?? 0} approved`} />
          <Metric name="Allocated volume" value={kg(summary?.allocation.allocated_kg)} hint="Across all shops and commodities" />
          <Metric name="Blocked" value={num(summary?.allocation.blocked)} t={summary?.allocation.blocked ? 'bad' : 'ok'}
            hint={summary?.allocation.blocked ? 'Will not be routed until resolved' : 'Nothing blocked'} />
          <Metric name="Overridden" value={num(summary?.allocation.overridden)} hint="Audited officer decisions" />
          <Metric name="FPS coverage" value={summary?.coverage.pct !== null && summary ? `${summary.coverage.pct}%` : '—'}
            hint={summary ? `${summary.coverage.fps_with_approved_allocation} of ${summary.coverage.active_fps} shops` : undefined} />
        </MetricStrip>
      )}

      {!notAllocatedYet && (
        <Panel title={`Allocations (${rows.length}${status === 'BLOCKED' ? ' blocked' : ''})`} pad={false}
          subtitle="“Requested” is submitted intent; “Allocated” is the engine’s proposal after the gates"
          action={
            <div style={{ display: 'flex', gap: s(2), alignItems: 'center', flexWrap: 'wrap' }}>
              <select value={status} onChange={e => setStatus(e.target.value as any)}
                style={{ padding: '5px 8px', border: `1px solid ${c.lineStrong}`, borderRadius: 4, fontSize: 12 }}>
                <option value="BLOCKED">Needs attention</option>
                <option value="ALL">All lines</option>
              </select>
              <select value={commodity} onChange={e => setCommodity(e.target.value as any)}
                style={{ padding: '5px 8px', border: `1px solid ${c.lineStrong}`, borderRadius: 4, fontSize: 12 }}>
                <option value="ALL">All commodities</option><option value="RICE">Rice</option><option value="WHEAT">Wheat</option>
              </select>
              <input value={fpsFilter} onChange={e => setFpsFilter(e.target.value)} placeholder="Filter FPS…"
                style={{ padding: '5px 9px', border: `1px solid ${c.lineStrong}`, borderRadius: 4, fontSize: 12, width: 140 }} />
            </div>
          }>
          <Region q={allocQ}>
            {() => rows.length === 0
              ? <div style={{ padding: s(5) }}>
                  <DataUnavailable what={status === 'BLOCKED' ? 'Nothing blocked' : 'No allocations match'}
                    why={status === 'BLOCKED' ? 'Every allocation line passed the constraint gates. Switch to “All lines” to review them.' : undefined} />
                </div>
              : (
                <Table head={['FPS', 'Commodity', 'Requested', 'Allocated', 'Warehouse', 'Source', 'Status', '']} maxHeight={520}>
                  {rows.slice(0, 400).map(a => {
                    const blocked = a.status === 'BLOCKED';
                    const hasExc = excByEntity.has(`${a.fps_id}:${a.commodity}`);
                    return (
                      <tr key={a.allocation_id} style={{ background: blocked ? c.badBg : undefined }}>
                        <td style={tdMono}>{a.fps_id}</td>
                        <td style={td}>{a.commodity}</td>
                        <td style={td}>{kg(a.requested_kg)}</td>
                        <td style={td}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
                            <span style={{ fontWeight: 600, color: c.ink, minWidth: 74 }}>{kg(a.allocated_kg)}</span>
                            <Bar value={Number(a.allocated_kg)} max={Math.max(Number(a.allocated_kg), Number(a.requested_kg), 1)}
                              t={blocked ? 'bad' : 'ok'} />
                          </div>
                        </td>
                        <td style={tdMono}>{a.warehouse_id}</td>
                        <td style={{ ...td, fontSize: 11.5, color: a.source === 'DSO_OVERRIDE' ? c.accent : c.muted }}>
                          {a.source === 'DSO_OVERRIDE' ? 'Officer override' : a.source || '—'}
                        </td>
                        <td style={td}><Badge>{a.status}</Badge></td>
                        <td style={{ ...td, textAlign: 'right' }}>
                          {hasExc
                            ? <button onClick={() => openFor(a)} style={{ font: `600 11.5px ${font.ui}`, padding: '4px 10px',
                                borderRadius: 4, border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.navy, cursor: 'pointer' }}>
                                Review
                              </button>
                            : <span style={{ color: c.faint, fontSize: 11.5 }}>—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </Table>
              )}
          </Region>
          {rows.length > 400 && <div style={{ padding: s(3), fontSize: 11.5, color: c.muted }}>Showing 400 of {rows.length}.</div>}
        </Panel>
      )}

      <ExceptionDrawer exception={selected?.exc ?? null} allocation={selected?.alloc} cycle={cycle}
        onClose={() => setSelected(null)}
        onResolved={() => { allocQ.reload(); excQ.reload(); refresh(); }} />
    </>
  );
}
