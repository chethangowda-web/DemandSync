/**
 * Tracking — stage 06.
 *
 * Planned route and live position are shown as two separate things and never conflated. Where no
 * telemetry exists (which is the normal case in this dataset), the screen says LIVE LOCATION
 * UNAVAILABLE rather than drawing a vehicle at its planned stop. ETA is only ever the planned ETA from
 * the optimiser, labelled as planned.
 */
import { useMemo, useState } from 'react';
import { useCycle } from '../DsoLayout';
import { Manifest, RouteStop, TelemetryPoint, dso } from '../api';
import { c, dateTime, font, kg, label, num, s } from '../theme';
import { Badge, DataUnavailable, Loading, Metric, MetricStrip, Panel, Region, Table, td, tdMono, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { GeodesicNote } from '../components/Manifest';

export default function TrackingPage() {
  const { cycle, summary } = useCycle();
  const [selected, setSelected] = useState<string | null>(null);

  const trackQ = useData<{ planned_routes: RouteStop[]; telemetry: TelemetryPoint[] }>(
    () => (cycle ? dso.tracking(cycle) : Promise.reject('no cycle')), [cycle, summary?.state]);
  const manQ = useData<Manifest[]>(
    () => (cycle ? dso.manifests(cycle).then(m => m.filter(x => x.manifest_id.startsWith('MFO-'))) : Promise.resolve([])), [cycle, summary?.state]);

  const byManifest = useMemo(() => {
    const m = new Map<string, RouteStop[]>();
    (trackQ.data?.planned_routes ?? []).forEach(r => m.set(r.manifest_id, [...(m.get(r.manifest_id) ?? []), r]));
    m.forEach(v => v.sort((a, b) => a.stop_sequence - b.stop_sequence));
    return m;
  }, [trackQ.data]);

  const latestTelemetry = useMemo(() => {
    const m = new Map<string, TelemetryPoint>();
    (trackQ.data?.telemetry ?? []).forEach(t => { if (!m.has(t.manifest_id)) m.set(t.manifest_id, t); });
    return m;
  }, [trackQ.data]);

  if (!cycle) return <Loading />;
  const manifests = manQ.data ?? [];
  const inTransit = manifests.filter(m => m.manifest_status === 'DISPATCHED');
  const withPosition = (trackQ.data?.telemetry ?? []).filter(t => t.latitude !== null && t.longitude !== null);
  const active = selected ?? inTransit[0]?.manifest_id ?? manifests[0]?.manifest_id ?? null;

  return (
    <>
      <Panel title="Tracking" subtitle="Stage 06 · planned route versus what has actually been reported">
        <StageRail state={summary?.state} />
      </Panel>

      <MetricStrip>
        <Metric name="Manifests dispatched" value={num(inTransit.length)} hint={`${manifests.length} total this cycle`} />
        <Metric name="Delivered" value={num(manifests.filter(m => m.manifest_status === 'DELIVERED').length)} hint="Confirmed at the shop" />
        <Metric name="Telemetry points" value={num(trackQ.data?.telemetry.length)}
          hint={withPosition.length ? `${withPosition.length} carry coordinates` : 'No coordinates reported'} />
        <Metric name="Planned stops" value={num(trackQ.data?.planned_routes.length)} hint="Across all routes" />
      </MetricStrip>

      {manifests.length === 0 ? (
        <DataUnavailable what="Nothing to track" why="No manifests have been produced for this cycle yet." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 0.8fr) minmax(0, 2fr)', gap: s(5), alignItems: 'start' }}>
          <Panel title={`Vehicles (${manifests.length})`} pad={false}>
            <div style={{ maxHeight: 520, overflow: 'auto' }}>
              {manifests.map(m => {
                const tel = latestTelemetry.get(m.manifest_id);
                const on = m.manifest_id === active;
                return (
                  <button key={m.manifest_id} onClick={() => setSelected(m.manifest_id)}
                    style={{ display: 'block', width: '100%', textAlign: 'left', padding: s(3), border: 'none',
                      borderBottom: `1px solid ${c.line}`, borderLeft: `3px solid ${on ? c.navy : 'transparent'}`,
                      background: on ? c.accentBg : 'transparent', cursor: 'pointer', font: `400 12.5px ${font.ui}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
                      <span style={{ fontFamily: font.mono, fontWeight: 700, color: c.ink }}>{m.vehicle_id}</span>
                      <span style={{ marginLeft: 'auto' }}><Badge>{m.manifest_status}</Badge></span>
                    </div>
                    <div style={{ color: c.muted, marginTop: 3 }}>
                      {m.warehouse_id} · {kg(m.total_kg)} · {byManifest.get(m.manifest_id)?.length ?? 0} stops
                    </div>
                    <div style={{ fontSize: 11, color: tel ? c.body : c.faint, marginTop: 3 }}>
                      {tel ? `Last report ${dateTime(tel.timestamp)} · ${tel.status}` : 'No telemetry reported'}
                    </div>
                  </button>
                );
              })}
            </div>
          </Panel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: s(5), minWidth: 0 }}>
            <Panel title="Live position">
              {(() => {
                const tel = active ? latestTelemetry.get(active) : undefined;
                if (!tel) {
                  return <DataUnavailable what="Live location unavailable"
                    why="No telemetry has been reported for this vehicle. The planned route below is a plan, not a position — it is never shown as a live location." />;
                }
                const hasCoords = tel.latitude !== null && tel.longitude !== null;
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
                    <div style={{ display: 'flex', gap: s(5), flexWrap: 'wrap' }}>
                      <div><div style={label}>Reported status</div><div style={{ marginTop: 3 }}><Badge>{tel.status}</Badge></div></div>
                      <div><div style={label}>Last report</div><div style={{ color: c.ink, fontWeight: 600 }}>{dateTime(tel.timestamp)}</div></div>
                      <div><div style={label}>Speed</div><div style={{ color: c.ink, fontWeight: 600 }}>{tel.speed_kmph === null ? 'unavailable' : `${num(tel.speed_kmph)} km/h`}</div></div>
                    </div>
                    {hasCoords ? (
                      <div style={{ fontFamily: font.mono, fontSize: 12, color: c.body }}>
                        {Number(tel.latitude).toFixed(5)}, {Number(tel.longitude).toFixed(5)}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12.5, color: c.warn }}>
                        This report carries no coordinates — position unavailable.
                      </div>
                    )}
                    <div style={{ fontSize: 11.5, color: c.muted }}>ETA is not computed from live movement; only the planned ETA below is available.</div>
                  </div>
                );
              })()}
            </Panel>

            <Panel title="Planned route" subtitle={<GeodesicNote inline />} pad={false}>
              <Region q={trackQ}>
                {() => {
                  const stops = active ? byManifest.get(active) ?? [] : [];
                  if (!stops.length) return <div style={{ padding: s(5) }}><DataUnavailable what="No planned stops" /></div>;
                  return (
                    <Table head={['#', 'FPS', 'Leg (km)', 'Planned ETA', 'Coordinates', 'Status']} maxHeight={360}>
                      {stops.map(r => (
                        <tr key={`${r.manifest_id}-${r.stop_sequence}`}>
                          <td style={tdMono}>{r.stop_sequence}</td>
                          <td style={tdMono}>{r.fps_id}</td>
                          <td style={td}>{num(r.distance_from_previous_km)}</td>
                          <td style={td}>{r.eta_minutes === null ? <span style={{ color: c.faint }}>unavailable</span> : `+${num(r.eta_minutes)} min`}</td>
                          <td style={tdMono}>{Number(r.latitude).toFixed(4)}, {Number(r.longitude).toFixed(4)}</td>
                          <td style={td}><Badge>{r.route_status}</Badge></td>
                        </tr>
                      ))}
                    </Table>
                  );
                }}
              </Region>
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
