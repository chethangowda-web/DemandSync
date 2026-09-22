/**
 * Command Centre — the single screen that answers "what is happening, what needs me, and what next".
 *
 * Every figure comes from GET /cycles/{c}/summary; nothing on this page is computed from assumptions
 * and nothing is filled in when the backend returns null.
 */
import { useNavigate } from 'react-router-dom';
import { useCycle } from '../DsoLayout';
import { AiForecast, DemandRow, Exception, dso } from '../api';
import { c, kg, label, num, pct, s } from '../theme';
import { Badge, DataUnavailable, ErrorNote, Loading, Metric, MetricStrip, Panel, Region, useData } from '../ui';
import { SituationHeader, NextAction } from '../components/Situation';
import { DemandChart } from '../components/DemandChart';
import { DemandSignal } from '../components/DemandSignal';
import { AIBrief } from '../components/AIBrief';
import { ExceptionTable, SeverityStrip } from '../components/Exceptions';

export default function CommandCentre() {
  const { cycle, summary, summaryError, refresh } = useCycle();
  const navigate = useNavigate();

  const demandQ = useData<DemandRow[]>(
    () => (cycle ? dso.demand(cycle).then(d => d.rows) : Promise.resolve([])), [cycle]);
  const excQ = useData<Exception[]>(
    () => (cycle ? dso.exceptions(cycle, { status: 'OPEN', entity_type: 'ALLOCATION' }) : Promise.resolve([])), [cycle]);

  // One real AI envelope for the brief: the first FPS+commodity that actually has a forecast.
  const aiQ = useData<AiForecast | null>(async () => {
    if (!cycle || !demandQ.data) return null;
    const row = demandQ.data.find(r => r.forecast_demand_kg !== null && r.forecast_demand_kg !== undefined);
    if (!row) return null;
    try { return await dso.aiForecast(cycle, row.fps_id, row.commodity); } catch { return null; }
  }, [cycle, demandQ.data]);

  if (!cycle) return <Loading what="Loading cycles" />;
  if (summaryError) return <ErrorNote error={summaryError} onRetry={refresh} />;
  if (!summary) return <Loading what="Loading situation" />;

  const sm = summary;
  const fleetHint = sm.fleet.total ? `${sm.fleet.available} of ${sm.fleet.total} available` : 'No fleet recorded';

  return (
    <>
      <SituationHeader cycle={cycle} state={sm.state} lockedAt={sm.locked_at} closedAt={sm.closed_at} />
      <NextAction state={sm.state} />

      <MetricStrip>
        <Metric name="Beneficiary intents" value={num(sm.intent.submissions)} emphasis
          hint={sm.intent.participation_pct !== null
            ? `${sm.intent.beneficiaries} of ${num(sm.intent.eligible_beneficiaries)} eligible (${sm.intent.participation_pct}%)`
            : 'Participation unavailable'} />
        <Metric name="Intent volume" value={kg(sm.intent.kg)}
          hint={sm.forecast.intent_vs_forecast_kg !== null
            ? `${sm.forecast.intent_vs_forecast_kg >= 0 ? '+' : ''}${num(sm.forecast.intent_vs_forecast_kg)} kg vs forecast`
            : 'Comparison unavailable'} />
        <Metric name="Forecast demand" value={sm.forecast.generated ? kg(sm.forecast.kg) : '—'}
          hint={sm.forecast.vs_baseline_pct !== null ? `${pct(sm.forecast.vs_baseline_pct)} vs baseline`
            : sm.forecast.generated ? 'Baseline unavailable' : 'No forecast generated yet'} />
        <Metric name="Allocated" value={sm.allocation.rows ? kg(sm.allocation.allocated_kg) : '—'}
          t={sm.allocation.blocked > 0 ? 'warn' : undefined}
          hint={sm.allocation.rows ? `${sm.allocation.approved} approved · ${sm.allocation.blocked} blocked` : 'Not yet allocated'} />
        <Metric name="Exceptions" value={num(sm.exceptions.open_total)}
          t={sm.exceptions.critical > 0 ? 'bad' : sm.exceptions.open_total > 0 ? 'warn' : 'ok'}
          hint={`${sm.exceptions.critical} critical · ${sm.exceptions.medium} medium`} />
        <Metric name="Fleet ready" value={`${num(sm.fleet.available)} / ${num(sm.fleet.total)}`} hint={fleetHint} />
        <Metric name="FPS coverage" value={sm.coverage.pct !== null ? `${sm.coverage.pct}%` : '—'}
          hint={`${num(sm.coverage.fps_with_approved_allocation)} of ${num(sm.coverage.active_fps)} active shops`} />
      </MetricStrip>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.45fr) minmax(320px, 1fr)', gap: s(5), alignItems: 'start' }}>
        {/* ---------------------------------------------------------- left: intelligence */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: s(5), minWidth: 0 }}>
          <Panel title="Demand intelligence"
            subtitle="What was asked for, what the model predicts, and what normally happens">
            <Region q={demandQ}>
              {rows => rows.length === 0
                ? <DataUnavailable what="No demand recorded" why="No beneficiary intent or historical baseline exists for this cycle yet." />
                : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: s(4) }}>
                    <DemandChart rows={rows} />
                    <DemandSignal rows={rows} />
                  </div>
                )}
            </Region>
          </Panel>

          <Panel title="Exception command centre"
            subtitle="Scoped to this cycle's own constraint gates"
            action={<button onClick={() => navigate('/dso/exceptions')} style={{ background: 'none', border: 'none',
              color: c.accent, font: '600 12px Inter, system-ui', cursor: 'pointer' }}>Open workspace →</button>}>
            <Region q={excQ}>
              {list => (
                <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
                  <SeverityStrip exceptions={list} />
                  {list.length === 0
                    ? <DataUnavailable what="No open exceptions" why="Nothing on this cycle's allocation gates currently needs attention." />
                    : <ExceptionTable exceptions={list.slice(0, 8)} onSelect={() => navigate('/dso/exceptions')} maxHeight={280} />}
                  {list.length > 8 && <div style={{ fontSize: 11.5, color: c.muted }}>Showing 8 of {list.length} — open the workspace for the rest.</div>}
                </div>
              )}
            </Region>
          </Panel>
        </div>

        {/* ---------------------------------------------------------- right: brief + status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: s(5), minWidth: 0 }}>
          <Panel title="AI operations brief" subtitle="Advisory signals — the officer decides">
            {demandQ.loading || aiQ.loading ? <Loading what="Assessing" />
              : <AIBrief summary={sm} ai={aiQ.data ?? null} />}
          </Panel>

          <Panel title="Cycle integrity">
            <div style={{ display: 'flex', flexDirection: 'column', gap: s(3), fontSize: 12.5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: s(3), alignItems: 'center' }}>
                <span style={label}>Demand lock</span>
                {sm.demand_lock.locked ? <Badge t="ok">SEALED</Badge> : <Badge t="idle">NOT LOCKED</Badge>}
              </div>
              {sm.demand_lock.sha256_hash && (
                <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 10.5, color: c.muted, overflowWrap: 'anywhere' }}>
                  {sm.demand_lock.sha256_hash}
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: s(3) }}>
                <span style={label}>Manifests</span>
                <span style={{ color: c.ink }}>
                  {sm.manifests.count ? `${sm.manifests.count} · ${kg(sm.manifests.total_kg)}` : 'None planned'}
                </span>
              </div>
              {Object.entries(sm.manifests.by_status).map(([st, n]) => (
                <div key={st} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: s(3) }}>
                  <Badge>{st}</Badge><span style={{ color: c.body }}>{n}</span>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: s(3) }}>
                <span style={label}>Deliveries recorded</span>
                <span style={{ color: c.ink }}>{sm.delivery.records || '—'}</span>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
