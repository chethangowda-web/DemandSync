/**
 * Delivery & Reconciliation — stage 07.
 *
 * Deliveries are recorded from what was actually observed at the shop, never pre-filled as "equal to
 * planned" without the officer confirming it. The closure gate reads the backend's own seven checks
 * (GET /closure-checks) so the officer sees the gate before committing to reconcile.
 */
import { useState } from 'react';
import { ClosureChecks, Delivery, Manifest, ManifestDetail, dso } from '../api';
import { useCycle } from '../DsoLayout';
import { c, dateTime, font, kg, label, num, s } from '../theme';
import { Badge, DataUnavailable, Drawer, ErrorNote, Facts, Loading, Metric, MetricStrip, Panel, Region, Table, td, tdMono, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { ActionCard, DecisionGate, checksFromMap } from '../components/Gate';

function DeliveryForm({ manifest, onDone, onError }:
  { manifest: ManifestDetail; onDone: () => void; onError: (m: string) => void }) {
  const [qty, setQty] = useState<Record<string, string>>(() =>
    Object.fromEntries(manifest.items.map(i => [`${i.fps_id}|${i.commodity}`, ''])));
  const [busy, setBusy] = useState(false);
  const complete = Object.values(qty).every(v => v !== '');

  const submit = async () => {
    setBusy(true);
    try {
      await dso.deliver(manifest.manifest_id, manifest.items.map(i => ({
        fps_id: i.fps_id, commodity: i.commodity, delivered_kg: Number(qty[`${i.fps_id}|${i.commodity}`]),
      })));
      onDone();
    } catch (e: any) { onError(e?.message || String(e)); } finally { setBusy(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: s(4) }}>
      <div style={{ fontSize: 12.5, color: c.body, lineHeight: 1.6 }}>
        Enter the quantity <strong>actually received</strong> at each shop. Nothing is pre-filled from the plan —
        a figure that matches the plan must be entered deliberately.
      </div>
      <Table head={['FPS', 'Commodity', 'Planned', 'Received (kg)']}>
        {manifest.items.map(i => {
          const k = `${i.fps_id}|${i.commodity}`;
          const v = qty[k];
          const delta = v === '' ? null : Number(v) - Number(i.planned_kg);
          return (
            <tr key={i.manifest_item_id}>
              <td style={tdMono}>{i.fps_id}</td>
              <td style={td}>{i.commodity}</td>
              <td style={td}>{kg(i.planned_kg)}</td>
              <td style={td}>
                <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
                  <input type="number" value={v} onChange={e => setQty(q => ({ ...q, [k]: e.target.value }))}
                    style={{ width: 96, padding: '5px 8px', border: `1px solid ${c.lineStrong}`, borderRadius: 4,
                      font: `600 12.5px ${font.mono}` }} />
                  {delta !== null && delta !== 0 && (
                    <span style={{ fontSize: 11.5, color: delta < 0 ? c.bad : c.warn, fontWeight: 600 }}>
                      {delta > 0 ? '+' : ''}{num(delta)}
                    </span>
                  )}
                </div>
              </td>
            </tr>
          );
        })}
      </Table>
      <button disabled={!complete || busy} onClick={submit}
        style={{ alignSelf: 'flex-start', font: `600 13px ${font.ui}`, padding: '10px 18px', borderRadius: 5,
          border: 'none', background: complete && !busy ? c.navy : c.idleBg, color: complete && !busy ? '#fff' : c.faint,
          cursor: complete && !busy ? 'pointer' : 'not-allowed' }}>
        {busy ? 'Recording…' : 'Record delivery'}
      </button>
      {!complete && <div style={{ fontSize: 11.5, color: c.muted }}>Every line needs a received quantity before this can be recorded.</div>}
    </div>
  );
}

export default function ReconciliationPage() {
  const { cycle, summary, refresh } = useCycle();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState<ManifestDetail | null>(null);
  const [lastRun, setLastRun] = useState<{ passed: boolean; state: string } | null>(null);

  const manQ = useData<Manifest[]>(() => (cycle ? dso.manifests(cycle).then(m => m.filter(x => x.manifest_id.startsWith('MFO-'))) : Promise.resolve([])), [cycle, summary?.state]);
  const delQ = useData<Delivery[]>(() => (cycle ? dso.deliveries(cycle) : Promise.resolve([])), [cycle, summary?.state]);
  const checkQ = useData<{ checks: ClosureChecks; passed: boolean }>(() => (cycle ? dso.closureChecks(cycle) : Promise.reject('no cycle')), [cycle, summary?.state]);

  if (!cycle) return <Loading />;
  const manifests = manQ.data ?? [];
  const pending = manifests.filter(m => m.manifest_status === 'DISPATCHED');
  const deliveries = delQ.data ?? [];

  const run = async (what: string, fn: () => Promise<unknown>) => {
    setBusy(what); setErr(null);
    try { await fn(); manQ.reload(); delQ.reload(); checkQ.reload(); refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); } finally { setBusy(null); }
  };

  const canClose = summary?.state === 'AUDITING';
  const closed = summary?.state === 'CLOSED';

  return (
    <>
      <Panel title="Delivery & reconciliation" subtitle="Stage 07 · confirm what arrived, then close the cycle">
        <StageRail state={summary?.state} />
      </Panel>

      {err && <ErrorNote error={err} />}

      <MetricStrip>
        <Metric name="Awaiting delivery" value={num(pending.length)} t={pending.length ? 'warn' : 'ok'} hint="Dispatched, not yet confirmed" />
        <Metric name="Delivery lines" value={num(deliveries.length)} hint="Recorded at the shop" />
        <Metric name="Variance" value={num(summary?.delivery.variance)} t={summary?.delivery.variance ? 'warn' : 'ok'} hint="Outside tolerance" />
        <Metric name="Rejected" value={num(summary?.delivery.rejected)} t={summary?.delivery.rejected ? 'bad' : 'ok'} hint="Nothing received" />
        <Metric name="Delivered volume" value={kg(summary?.delivery.delivered_kg)} hint={`of ${kg(summary?.manifests.total_kg)} planned`} />
      </MetricStrip>

      {pending.length > 0 && (
        <Panel title={`Record deliveries (${pending.length} outstanding)`}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: s(4) }}>
            {pending.map(m => (
              <article key={m.manifest_id} style={{ border: `1px solid ${c.line}`, borderRadius: 6, padding: s(4), background: c.surface }}>
                <div style={{ font: `700 12.5px ${font.mono}`, color: c.ink }}>{m.manifest_id}</div>
                <div style={{ fontSize: 12, color: c.muted, marginTop: 3 }}>{m.vehicle_id} · {kg(m.total_kg)}</div>
                <button onClick={async () => {
                  setErr(null);
                  try { setForm(await dso.manifest(m.manifest_id)); } catch (e: any) { setErr(e?.message || String(e)); }
                }}
                  style={{ marginTop: s(3), font: `600 12.5px ${font.ui}`, padding: '7px 14px', borderRadius: 5,
                    border: 'none', background: c.navy, color: '#fff', cursor: 'pointer' }}>
                  Record delivery
                </button>
              </article>
            ))}
          </div>
        </Panel>
      )}

      <Panel title={`Delivery verification (${deliveries.length})`} pad={false}>
        <Region q={delQ} empty={<div style={{ padding: s(5) }}><DataUnavailable what="No deliveries recorded" why="Deliveries appear here once confirmed against a dispatched manifest." /></div>}>
          {list => list.length === 0
            ? <div style={{ padding: s(5) }}><DataUnavailable what="No deliveries recorded" why="Deliveries appear here once confirmed against a dispatched manifest." /></div>
            : (
              <Table head={['Manifest', 'FPS', 'Commodity', 'Planned', 'Received', 'Variance', 'Classification', 'Recorded']} maxHeight={420}>
                {list.map(d => (
                  <tr key={d.delivery_id} style={{ background: d.status === 'REJECTED' ? c.badBg : d.status === 'VARIANCE' ? c.warnBg : undefined }}>
                    <td style={tdMono}>{d.manifest_id}</td>
                    <td style={tdMono}>{d.fps_id}</td>
                    <td style={td}>{d.commodity}</td>
                    <td style={td}>{kg(d.planned_kg)}</td>
                    <td style={{ ...td, fontWeight: 600, color: c.ink }}>{kg(d.delivered_kg)}</td>
                    <td style={{ ...td, color: Number(d.variance_kg) === 0 ? c.muted : Number(d.variance_kg) < 0 ? c.bad : c.warn, fontWeight: 600 }}>
                      {Number(d.variance_kg) > 0 ? '+' : ''}{num(d.variance_kg)} kg
                    </td>
                    <td style={td}><Badge>{d.status}</Badge></td>
                    <td style={{ ...td, fontSize: 11.5, color: c.muted }}>{dateTime(d.delivery_date)}</td>
                  </tr>
                ))}
              </Table>
            )}
        </Region>
      </Panel>

      <Region q={checkQ}>
        {res => closed ? (
          <Panel title="Cycle closed">
            <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
              <Badge t="ok">CLOSED</Badge>
              <div style={{ fontSize: 13, color: c.body, lineHeight: 1.6 }}>
                This cycle completed every closure check and was closed. Its decision trail — who did what, when,
                why, and with what result — is permanently auditable.
              </div>
              <Facts items={[['Closed at', summary?.closed_at ? new Date(summary.closed_at).toLocaleString('en-IN') : '—']]} />
            </div>
          </Panel>
        ) : canClose ? (
          <ActionCard title="Cycle closure gate"
            body={<>All seven closure checks passed at reconciliation. Closing is final and stamps the cycle as complete.</>}
            action="Close cycle" busy={busy === 'close'}
            onAction={() => { if (confirm('Close this cycle? This is final.')) run('close', () => dso.close(cycle)); }} />
        ) : (
          <DecisionGate
            title="Cycle closure gate"
            intro="The seven checks below are read live from the backend. Reconciling advances the cycle only if all of them pass."
            checks={checksFromMap(res.checks)}
            action={lastRun && !lastRun.passed ? 'Re-run reconciliation' : 'Run reconciliation'}
            busy={busy === 'reconcile'}
            blockedNote="Reconciliation can only run once deliveries have begun."
            onAction={() => run('reconcile', async () => {
              const r = await dso.reconcile(cycle);
              setLastRun({ passed: r.passed, state: r.state });
            })}
          >
            {lastRun && !lastRun.passed && (
              <div style={{ background: c.warnBg, border: `1px solid ${c.warnLine}`, borderRadius: 5, padding: s(3), fontSize: 12.5, color: c.warn }}>
                Last reconciliation did not pass; the cycle stayed in {lastRun.state} and a high-severity exception was
                recorded for each failed check.
              </div>
            )}
          </DecisionGate>
        )}
      </Region>

      <Drawer open={!!form} onClose={() => setForm(null)} title={`Record delivery · ${form?.manifest_id ?? ''}`}
        subtitle={form ? `${form.vehicle_id} · ${form.items.length} lines` : undefined} width={620}>
        {form && <DeliveryForm manifest={form}
          onDone={() => { setForm(null); manQ.reload(); delQ.reload(); checkQ.reload(); refresh(); }}
          onError={m => { setErr(m); setForm(null); }} />}
      </Drawer>
    </>
  );
}
