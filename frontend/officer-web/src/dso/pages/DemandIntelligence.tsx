/**
 * Demand Intelligence — stages 01 MONITOR and 02 VALIDATE & LOCK.
 *
 * Shows the four demand series per FPS, runs the XGBoost forecast, and performs the irreversible
 * choice-window close that seals demand with a SHA-256 hash.
 */
import { useState } from 'react';
import { useCycle } from '../DsoLayout';
import { DemandRow, dso } from '../api';
import { c, font, kg, label, num, s } from '../theme';
import { Badge, DataUnavailable, ErrorNote, Loading, Panel, Region, Table, td, tdMono, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { DemandChart } from '../components/DemandChart';
import { DemandSignal } from '../components/DemandSignal';
import { ActionCard } from '../components/Gate';

export default function DemandIntelligence() {
  const { cycle, summary, refresh } = useCycle();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [onlyGaps, setOnlyGaps] = useState(false);

  const q = useData<DemandRow[]>(() => (cycle ? dso.demand(cycle).then(d => d.rows) : Promise.resolve([])), [cycle, summary?.state]);

  if (!cycle) return <Loading />;
  const locked = !!summary?.demand_lock.locked;
  const canLock = summary?.state === 'OPEN' || summary?.state === 'MONITOR';

  const run = async (what: string, fn: () => Promise<unknown>) => {
    setBusy(what); setErr(null);
    try { await fn(); q.reload(); refresh(); } catch (e: any) { setErr(e?.message || String(e)); } finally { setBusy(null); }
  };

  const rows = (q.data ?? []).filter(r => {
    if (filter && !r.fps_id.toLowerCase().includes(filter.toLowerCase())) return false;
    if (onlyGaps && (r.intent_minus_forecast_kg === undefined || Math.abs(r.intent_minus_forecast_kg) < 1)) return false;
    return true;
  });

  return (
    <>
      <Panel title="Demand intelligence" subtitle="Stage 01–02 · what beneficiaries asked for, and sealing it">
        <StageRail state={summary?.state} />
      </Panel>

      {err && <ErrorNote error={err} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(300px, 1fr)', gap: s(5), alignItems: 'start' }}>
        <Panel title="Demand by commodity">
          <Region q={q}>
            {all => all.length === 0
              ? <DataUnavailable what="No demand data" why="No intent, forecast or historical baseline exists for this cycle." />
              : <div style={{ display: 'flex', flexDirection: 'column', gap: s(4) }}>
                  <DemandChart rows={all} height={280} />
                  <DemandSignal rows={all} />
                </div>}
          </Region>
        </Panel>

        <div style={{ display: 'flex', flexDirection: 'column', gap: s(5) }}>
          <ActionCard
            title="Generate forecast"
            body={summary?.forecast.generated
              ? <>A forecast exists for this cycle ({kg(summary.forecast.kg)}). Re-running retrains the model on current history and replaces it.</>
              : <>Train the XGBoost model on historical demand and produce a forecast for every FPS and commodity. Shops with fewer than three cycles of history fall back to their historical average, labelled as such.</>}
            action={summary?.forecast.generated ? 'Re-run forecast' : 'Generate forecast'}
            busy={busy === 'forecast'}
            onAction={() => run('forecast', () => dso.runForecast(cycle))}
          />

          {locked ? (
            <Panel title="Demand lock">
              <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
                <Badge t="ok">SEALED — IMMUTABLE</Badge>
                <div style={{ fontSize: 12.5, color: c.body, lineHeight: 1.6 }}>
                  Demand for this cycle was frozen and hashed. The snapshot cannot be altered, and new beneficiary
                  submissions are refused for this cycle.
                </div>
                <div>
                  <div style={label}>SHA-256</div>
                  <div style={{ fontFamily: font.mono, fontSize: 10.5, color: c.muted, overflowWrap: 'anywhere', marginTop: 3 }}>
                    {summary?.demand_lock.sha256_hash}
                  </div>
                </div>
                <div style={{ fontSize: 11.5, color: c.faint }}>
                  Locked by {summary?.demand_lock.locked_by} · {summary?.demand_lock.locked_at && new Date(summary.demand_lock.locked_at).toLocaleString('en-IN')}
                </div>
              </div>
            </Panel>
          ) : (
            <ActionCard
              title="Close choice window"
              body={<>Freeze demand for this cycle. An immutable snapshot of aggregated intent is written and sealed with a SHA-256 hash, and no further beneficiary submissions are accepted. <strong>This cannot be undone.</strong></>}
              action="Lock demand"
              danger
              disabled={!canLock}
              busy={busy === 'lock'}
              note={!canLock ? <div style={{ fontSize: 12, color: c.muted }}>Only available while the cycle is OPEN — it is currently {summary?.state}.</div> : undefined}
              onAction={() => { if (confirm('Lock demand for this cycle? This is irreversible.')) run('lock', () => dso.closeChoiceWindow(cycle)); }}
            />
          )}
        </div>
      </div>

      <Panel title={`Demand by FPS (${rows.length})`} pad={false}
        action={
          <div style={{ display: 'flex', gap: s(3), alignItems: 'center' }}>
            <label style={{ fontSize: 11.5, color: c.muted, display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={onlyGaps} onChange={e => setOnlyGaps(e.target.checked)} />
              Only where intent ≠ forecast
            </label>
            <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter FPS…"
              style={{ padding: '5px 9px', border: `1px solid ${c.lineStrong}`, borderRadius: 4, fontSize: 12, width: 150 }} />
          </div>
        }>
        <Region q={q}>
          {() => rows.length === 0
            ? <div style={{ padding: s(5) }}><DataUnavailable what="No rows match" /></div>
            : (
              <Table head={['FPS', 'Commodity', 'Intent', 'Baseline', 'Forecast', 'Intent − Forecast', 'Forecast − Baseline']} maxHeight={460}>
                {rows.slice(0, 400).map((r, i) => (
                  <tr key={i}>
                    <td style={tdMono}>{r.fps_id}</td>
                    <td style={td}>{r.commodity}</td>
                    <td style={td}>{kg(r.intent_demand_kg)}</td>
                    <td style={td}>{r.baseline_demand_kg === null ? <span style={{ color: c.faint }}>unavailable</span> : kg(r.baseline_demand_kg)}</td>
                    <td style={td}>{r.forecast_demand_kg === null ? <span style={{ color: c.faint }}>not generated</span> : kg(r.forecast_demand_kg)}</td>
                    <td style={{ ...td, color: r.intent_minus_forecast_kg === undefined ? c.faint : r.intent_minus_forecast_kg < 0 ? c.warn : c.body }}>
                      {r.intent_minus_forecast_kg === undefined ? '—' : `${r.intent_minus_forecast_kg > 0 ? '+' : ''}${num(r.intent_minus_forecast_kg)} kg`}
                    </td>
                    <td style={{ ...td, color: r.forecast_minus_baseline_kg === undefined ? c.faint : c.body }}>
                      {r.forecast_minus_baseline_kg === undefined ? '—' : `${r.forecast_minus_baseline_kg > 0 ? '+' : ''}${num(r.forecast_minus_baseline_kg)} kg`}
                    </td>
                  </tr>
                ))}
              </Table>
            )}
        </Region>
        {rows.length > 400 && <div style={{ padding: s(3), fontSize: 11.5, color: c.muted }}>Showing the first 400 of {rows.length} rows — narrow the filter to see others.</div>}
      </Panel>
    </>
  );
}
