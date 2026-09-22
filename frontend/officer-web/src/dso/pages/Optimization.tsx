/**
 * Route & fleet optimization — stage 04.
 *
 * Runs OR-Tools CVRP over the approved allocations and shows the resulting vehicle routes. Distance is
 * geodesic throughout and labelled as such. When the fleet cannot cover a stop, the backend records a
 * HIGH exception rather than dropping it, and that is surfaced here as an explicit shortfall — never
 * as a bare "optimization failed".
 */
import { useState } from 'react';
import { useCycle } from '../DsoLayout';
import { Exception, Fleet, Manifest, dso } from '../api';
import { c, font, kg, label, num, s } from '../theme';
import { Badge, Bar, DataUnavailable, ErrorNote, Loading, Metric, MetricStrip, Panel, Region, Table, td, tdMono, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { ActionCard, DecisionGate } from '../components/Gate';
import { GeodesicNote } from '../components/Manifest';
import { ruleInfo } from '../components/Exceptions';

export default function OptimizationPage() {
  const { cycle, summary, refresh } = useCycle();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const fleetQ = useData<Fleet>(() => (cycle ? dso.fleet(cycle) : Promise.reject('no cycle')), [cycle, summary?.state]);
  const manQ = useData<Manifest[]>(() => (cycle ? dso.manifests(cycle).then(m => m.filter(x => x.manifest_id.startsWith('MFO-'))) : Promise.resolve([])), [cycle, summary?.state]);
  const routingExcQ = useData<Exception[]>(() => (cycle ? dso.exceptions(cycle, { status: 'OPEN', entity_type: 'ROUTING' }) : Promise.resolve([])), [cycle, summary?.state]);

  if (!cycle) return <Loading />;
  const canOptimize = summary?.state === 'ALLOCATED';
  const optimized = summary && ['OPTIMIZED', 'AUTHORIZED', 'TRACKING', 'DELIVERING', 'RECONCILING', 'AUDITING', 'CLOSED'].includes(summary.state);

  const optimize = async () => {
    setBusy(true); setErr(null);
    try { await dso.optimize(cycle); manQ.reload(); fleetQ.reload(); routingExcQ.reload(); refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); } finally { setBusy(false); }
  };

  const f = fleetQ.data;

  return (
    <>
      <Panel title="Route & fleet optimization" subtitle="Stage 04 · OR-Tools capacitated vehicle routing">
        <StageRail state={summary?.state} />
      </Panel>

      {err && <ErrorNote error={err} />}

      <MetricStrip>
        <Metric name="Fleet size" value={num(f?.totals.fleet_size)} hint={f ? `${f.totals.available} available` : undefined} />
        <Metric name="Vehicles assigned" value={num(f?.totals.assigned_this_cycle)}
          hint={optimized ? 'Assigned by the optimiser this cycle' : 'Not yet optimised'} />
        <Metric name="Fleet capacity" value={kg(f?.totals.fleet_capacity_kg)} hint="Total across all vehicles" />
        <Metric name="Planned load" value={kg(f?.totals.assigned_load_kg)}
          hint={f && f.totals.fleet_capacity_kg
            ? `${((f.totals.assigned_load_kg / f.totals.fleet_capacity_kg) * 100).toFixed(1)}% of fleet capacity`
            : 'Utilisation unavailable'} />
        <Metric name="Route distance" value={`${num(summary?.manifests.route_km)} km`} hint="Geodesic, not road distance" />
        <Metric name="Unroutable stops" value={num(routingExcQ.data?.length)}
          t={routingExcQ.data?.length ? 'bad' : 'ok'} hint={routingExcQ.data?.length ? 'Fleet could not cover these' : 'All stops covered'} />
      </MetricStrip>

      {!optimized && (
        canOptimize ? (
          <DecisionGate
            title="Optimize routes"
            intro="OR-Tools solves one capacitated vehicle routing problem per warehouse over its approved allocations."
            checks={[
              { label: 'Demand locked and allocation run', status: summary?.state === 'ALLOCATED' ? 'PASS' : 'FAIL' },
              { label: `${summary?.allocation.approved ?? 0} approved allocation lines to route`, status: (summary?.allocation.approved ?? 0) > 0 ? 'PASS' : 'FAIL' },
              { label: `${f?.totals.available ?? 0} vehicle(s) available`, status: (f?.totals.available ?? 0) > 0 ? 'PASS' : 'FAIL' },
            ]}
            action="Run optimization"
            busy={busy}
            onAction={optimize}
          >
            {(summary?.allocation.blocked ?? 0) > 0 && (
              <div style={{ background: c.warnBg, border: `1px solid ${c.warnLine}`, borderRadius: 5, padding: s(3), fontSize: 12.5, color: c.warn }}>
                {summary?.allocation.blocked} blocked allocation line(s) will be <strong>skipped</strong>, not routed. Resolve them
                first if those shops must be served this cycle.
              </div>
            )}
          </DecisionGate>
        ) : (
          <ActionCard title="Optimization not available yet"
            body={<>Routes can only be planned once an allocation exists. The cycle is currently {summary?.state}.</>}
            action="Run optimization" disabled onAction={() => {}} />
        )
      )}

      {(routingExcQ.data?.length ?? 0) > 0 && (
        <Panel title={`Coverage shortfalls (${routingExcQ.data!.length})`}
          subtitle="Recorded by the optimiser — these stops were left unmanifested, not silently dropped" pad={false}>
          <Table head={['FPS', 'Reason', 'Detail']} maxHeight={240}>
            {routingExcQ.data!.map(e => (
              <tr key={e.exception_id}>
                <td style={tdMono}>{e.entity_id}</td>
                <td style={td}><Badge t="bad">{ruleInfo(e.rule_code).title}</Badge></td>
                <td style={{ ...td, fontSize: 12 }}>{e.reason}</td>
              </tr>
            ))}
          </Table>
        </Panel>
      )}

      <Panel title={`Planned routes (${manQ.data?.length ?? 0})`} subtitle={<GeodesicNote inline />}>
        <Region q={manQ} empty={<DataUnavailable what="No routes planned" why="Run optimization to produce vehicle routes for this cycle." />}>
          {list => list.length === 0
            ? <DataUnavailable what="No routes planned" why="Run optimization to produce vehicle routes for this cycle." />
            : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: s(4) }}>
                {list.map(m => {
                  const v = f?.vehicles.find(x => x.vehicle_id === m.vehicle_id);
                  const cap = v ? Number(v.capacity_kg) : null;
                  const util = cap ? (Number(m.total_kg) / cap) * 100 : null;
                  return (
                    <article key={m.manifest_id} style={{ border: `1px solid ${c.line}`, borderRadius: 6, background: c.surface, padding: s(4) }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
                        <span style={{ font: `700 13px ${font.mono}`, color: c.ink }}>{m.vehicle_id}</span>
                        <Badge>{m.manifest_status}</Badge>
                        <span style={{ marginLeft: 'auto', fontSize: 11, color: c.muted, fontFamily: font.mono }}>{m.warehouse_id}</span>
                      </div>
                      <div style={{ marginTop: s(3), display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                          <span style={label}>Load</span>
                          <span style={{ color: c.ink, fontWeight: 600 }}>
                            {kg(m.total_kg)}{cap ? <span style={{ color: c.faint, fontWeight: 400 }}> / {kg(cap)}</span> : null}
                          </span>
                        </div>
                        {util !== null && <Bar value={util} max={100} t={util > 95 ? 'warn' : 'ok'} />}
                        {util !== null && <div style={{ fontSize: 11, color: c.muted }}>{util.toFixed(1)}% vehicle utilisation</div>}
                      </div>
                      <div style={{ marginTop: s(3), display: 'flex', gap: s(4), fontSize: 12, borderTop: `1px solid ${c.line}`, paddingTop: s(3) }}>
                        <div><div style={label}>Distance</div><div style={{ color: c.ink }}>{num(m.route_distance_km)} km</div></div>
                        <div><div style={label}>Duration</div><div style={{ color: c.ink }}>{num(m.route_duration_min)} min</div></div>
                        <div><div style={label}>Gates</div><div><Badge>{m.constraint_status}</Badge></div></div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
        </Region>
      </Panel>

      <Panel title="Fleet" pad={false}>
        <Region q={fleetQ}>
          {fl => (
            <Table head={['Vehicle', 'Type', 'Warehouse', 'Capacity', 'Status', 'Assignment', 'Utilisation']} maxHeight={380}>
              {fl.vehicles.map(v => (
                <tr key={v.vehicle_id}>
                  <td style={tdMono}>{v.vehicle_number}</td>
                  <td style={td}>{v.vehicle_type}</td>
                  <td style={tdMono}>{v.warehouse_id}</td>
                  <td style={td}>{kg(v.capacity_kg)}</td>
                  <td style={td}><Badge>{v.current_status}</Badge></td>
                  <td style={tdMono}>{v.manifest_id ?? <span style={{ color: c.faint, fontFamily: font.ui }}>unassigned</span>}</td>
                  <td style={td}>{v.utilisation_pct === null ? <span style={{ color: c.faint }}>—</span> : `${v.utilisation_pct}%`}</td>
                </tr>
              ))}
            </Table>
          )}
        </Region>
      </Panel>
    </>
  );
}
