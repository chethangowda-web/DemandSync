import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { get, post, ApiError } from '../api/client';
import { stagesFor } from '../types/workflow';
import CycleHeader from '../components/CycleHeader';
import WorkflowStepper from '../components/WorkflowStepper';
import ManifestCard from '../components/ManifestCard';
import DecisionGate, { Check } from '../components/DecisionGate';
import EvidencePanel from '../components/EvidencePanel';
import HashBadge from '../components/HashBadge';

const card: React.CSSProperties = { border: '1px solid #cbd5e1', borderRadius: 8, padding: 16, background: '#fff' };
const btn: React.CSSProperties = { padding: '8px 14px', background: '#0f2a44', color: '#fff', border: 'none', borderRadius: 6, fontWeight: 600, cursor: 'pointer' };
const btnGhost: React.CSSProperties = { ...btn, background: '#fff', color: '#0f2a44', border: '1px solid #0f2a44' };

function Banner({ text, kind }: { text: string; kind: 'error' | 'ok' }) {
  return <div style={{ padding: 10, borderRadius: 6, fontSize: 13, background: kind === 'error' ? '#fef2f2' : '#f0fdf4', color: kind === 'error' ? '#991b1b' : '#166534', border: `1px solid ${kind === 'error' ? '#fecaca' : '#bbf7d0'}` }}>{text}</div>;
}

async function safe<T>(fn: () => Promise<T>, setError: (m: string | null) => void, setBusy?: (b: boolean) => void) {
  setBusy?.(true);
  setError(null);
  try {
    return await fn();
  } catch (e) {
    setError(e instanceof ApiError ? e.message : String(e));
    return undefined;
  } finally {
    setBusy?.(false);
  }
}

export default function DSOControlCentre() {
  const { user } = useAuth();
  const [cycles, setCycles] = useState<any[] | null>(null);
  const [cycle, setCycle] = useState<string | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const refresh = () => setReload(r => r + 1);

  useEffect(() => { get('/api/v1/cycles').then(d => { setCycles(d.cycles); if (!cycle && d.cycles.length) setCycle(d.cycles[0].cycle); }).catch(e => setError(String(e))); }, [reload]);
  useEffect(() => { if (cycle) get(`/api/v1/cycles/${cycle}`).then(setDetail).catch(e => setError(String(e))); }, [cycle, reload]);

  if (!user) return null;
  if (!cycles) return <div style={{ padding: 24 }}>Loading…</div>;
  if (!cycle || !detail) return <div style={{ padding: 24 }}>Select a cycle.</div>;

  const stages = stagesFor(detail.state);

  return (
    <div style={{ maxWidth: 1100, margin: '24px auto', padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 16, fontFamily: 'Inter, system-ui' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <label style={{ fontSize: 13 }}>Cycle</label>
        <select value={cycle} onChange={e => setCycle(e.target.value)} style={{ padding: 6, borderRadius: 6 }}>
          {cycles.map(c => <option key={c.cycle} value={c.cycle}>{c.cycle} — {c.state}</option>)}
        </select>
        <button style={btnGhost} onClick={refresh}>Refresh</button>
      </div>

      <CycleHeader cycle={cycle} state={detail.state} stages={stages} />
      {error && <Banner kind="error" text={error} />}

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16 }}>
        <WorkflowStepper stages={stages} current={stages.find(s => s.status === 'ACTIVE')?.key ?? ''} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {(detail.state === 'OPEN' || detail.state === 'MONITOR') && <MonitorPanel cycle={cycle} onDone={refresh} setError={setError} />}
          {detail.state === 'LOCKED' && <AllocatePanel cycle={cycle} onDone={refresh} setError={setError} />}
          {detail.state === 'ALLOCATED' && <OptimizePanel cycle={cycle} onDone={refresh} setError={setError} />}
          {detail.state === 'OPTIMIZED' && <AuthorizePanel cycle={cycle} onDone={refresh} setError={setError} />}
          {detail.state === 'AUTHORIZED' && <DispatchPanel cycle={cycle} onDone={refresh} setError={setError} />}
          {(detail.state === 'TRACKING' || detail.state === 'DELIVERING') && <DeliveryPanel cycle={cycle} onDone={refresh} setError={setError} />}
          {(detail.state === 'RECONCILING' || detail.state === 'AUDITING') && <ReconcilePanel cycle={cycle} state={detail.state} onDone={refresh} setError={setError} />}
          {detail.state === 'CLOSED' && <ClosedPanel cycle={cycle} />}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ MONITOR: demand, forecast, lock

function MonitorPanel({ cycle, onDone, setError }: { cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [demand, setDemand] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { get(`/api/v1/cycles/${cycle}/demand`).then(setDemand).catch(e => setError(String(e))); }, [cycle]);
  if (!demand) return <div style={card}>Loading demand…</div>;
  return (
    <div style={card}>
      <strong>Demand — intent, baseline, forecast</strong>
      <p style={{ fontSize: 12, color: '#64748b' }}>Participation: {demand.participation.submitted}/{demand.participation.eligible} ({demand.participation.participation_pct}%) · Forecast generated: {String(demand.forecast_generated)}</p>
      <div style={{ maxHeight: 260, overflow: 'auto', fontSize: 12 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['FPS', 'Commodity', 'Intent kg', 'Baseline kg', 'Forecast kg'].map(h => <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0', padding: 4 }}>{h}</th>)}</tr></thead>
          <tbody>{demand.rows.slice(0, 50).map((r: any, i: number) => (
            <tr key={i}><td style={{ padding: 4 }}>{r.fps_id}</td><td>{r.commodity}</td><td>{r.intent_demand_kg}</td><td>{r.baseline_demand_kg ?? '—'}</td><td>{r.forecast_demand_kg ?? '—'}</td></tr>
          ))}</tbody>
        </table>
        {demand.rows.length > 50 && <p style={{ color: '#94a3b8' }}>Showing 50 of {demand.rows.length} rows.</p>}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button style={btnGhost} disabled={busy} onClick={() => safe(() => post(`/api/v1/cycles/${cycle}/forecast`), setError, setBusy).then(r => { if (r) onDone(); })}>Generate Forecast (XGBoost)</button>
        <button style={btn} disabled={busy} onClick={() => { if (confirm('Close the choice window? This immutably locks demand and cannot be undone.')) safe(() => post(`/api/v1/cycles/${cycle}/choice-window/close`), setError, setBusy).then(r => { if (r) onDone(); }); }}>Close Choice Window (Lock Demand)</button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ LOCKED: allocate

function AllocatePanel({ cycle, onDone, setError }: { cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [lock, setLock] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { get(`/api/v1/cycles/${cycle}/demand-lock`).then(setLock).catch(e => setError(String(e))); }, [cycle]);
  return (
    <div style={card}>
      <strong>Demand locked</strong>
      {lock && <div style={{ fontSize: 12, marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}><HashBadge label="SHA256" hash={lock.sha256_hash} /><span>verified: {String(lock.hash_verified)}</span></div>}
      <p style={{ fontSize: 12, color: '#64748b' }}>Runs the 6-gate constraint engine (entitlement floor, FPS/warehouse/truck capacity, route feasibility) and proposes an allocation per FPS.</p>
      <button style={btn} disabled={busy} onClick={() => safe(() => post(`/api/v1/cycles/${cycle}/allocate`), setError, setBusy).then(r => { if (r) onDone(); })}>Run Allocation</button>
    </div>
  );
}

// ------------------------------------------------------------------ ALLOCATED: exceptions, overrides, optimize

function AllocatedRow({ a, cycle, onDone, setError }: { a: any; cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [open, setOpen] = useState(false);
  const [kg, setKg] = useState(a.allocated_kg);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <>
      <tr style={{ background: a.status === 'BLOCKED' ? '#fef2f2' : undefined }}>
        <td style={{ padding: 4 }}>{a.fps_id}</td><td>{a.commodity}</td><td>{a.requested_kg}</td><td>{a.allocated_kg}</td>
        <td><span style={{ color: a.status === 'BLOCKED' ? '#dc2626' : '#16a34a', fontWeight: 700 }}>{a.status}</span></td>
        <td>{a.status === 'BLOCKED' && <button style={{ ...btnGhost, padding: '2px 8px', fontSize: 11 }} onClick={() => setOpen(o => !o)}>Override</button>}</td>
      </tr>
      {open && (
        <tr><td colSpan={6} style={{ padding: 8, background: '#f8fafc' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="number" value={kg} onChange={e => setKg(Number(e.target.value))} style={{ width: 90 }} />
            <input placeholder="Reason (required)" value={reason} onChange={e => setReason(e.target.value)} style={{ flex: 1, padding: 4 }} />
            <button style={btn} disabled={busy || !reason.trim()} onClick={() => safe(() => post(`/api/v1/cycles/${cycle}/allocations/${a.fps_id}/${a.commodity}/override`, { allocated_kg: kg, reason }), setError, setBusy).then(r => { if (r) { setOpen(false); onDone(); } })}>Submit override</button>
          </div>
        </td></tr>
      )}
    </>
  );
}

function OptimizePanel({ cycle, onDone, setError }: { cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [allocs, setAllocs] = useState<any[] | null>(null);
  const [exceptions, setExceptions] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { get(`/api/v1/cycles/${cycle}/allocations`).then(d => setAllocs(d.allocations)).catch(e => setError(String(e))); }, [cycle]);
  useEffect(() => { get(`/api/v1/cycles/${cycle}/exceptions?status=OPEN`).then(d => setExceptions(d.exceptions)).catch(e => setError(String(e))); }, [cycle]);
  if (!allocs) return <div style={card}>Loading allocations…</div>;
  const blocked = allocs.filter(a => a.status === 'BLOCKED').length;
  const checks: Check[] = [{ label: `${blocked} BLOCKED allocation(s) resolved or overridden`, status: blocked === 0 ? 'PASS' : 'WARN', detail: blocked === 0 ? undefined : `${blocked} still blocked — they will be skipped, not routed` }];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={card}>
        <strong>Allocations ({allocs.length})</strong>
        <div style={{ maxHeight: 300, overflow: 'auto', fontSize: 12, marginTop: 8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['FPS', 'Commodity', 'Requested', 'Allocated', 'Status', ''].map(h => <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0', padding: 4 }}>{h}</th>)}</tr></thead>
            <tbody>{allocs.map((a, i) => <AllocatedRow key={i} a={a} cycle={cycle} onDone={onDone} setError={setError} />)}</tbody>
          </table>
        </div>
      </div>
      {exceptions && exceptions.length > 0 && <EvidencePanel title={`Open exceptions (${exceptions.length})`} data={exceptions} />}
      <DecisionGate title="Optimize routes (OR-Tools CVRP, haversine distance — not road distance)" checks={checks} action="Optimize Routes" disabled={busy}
        onAction={() => safe(() => post(`/api/v1/cycles/${cycle}/optimize`), setError, setBusy).then(r => { if (r) onDone(); })} />
    </div>
  );
}

// ------------------------------------------------------------------ OPTIMIZED: validate/lock manifests, authorize

function ManifestActionRow({ m, cycle, onDone, setError }: { m: any; cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <ManifestCard m={m} />
      <div style={{ display: 'flex', gap: 8 }}>
        {m.manifest_status === 'DRAFT' && <button style={btnGhost} disabled={busy} onClick={() => safe(() => post(`/api/v1/manifests/${m.manifest_id}/validate`), setError, setBusy).then(r => { if (r) onDone(); })}>Validate</button>}
        {m.manifest_status === 'VALIDATED' && <button style={btn} disabled={busy} onClick={() => safe(() => post(`/api/v1/manifests/${m.manifest_id}/lock`), setError, setBusy).then(r => { if (r) onDone(); })}>Seal (SHA256 + QR) & Lock</button>}
        {m.manifest_status === 'LOCKED' && <a href={`/api/v1/manifests/${m.manifest_id}/qr`} target="_blank" rel="noreferrer" style={{ ...btnGhost, textDecoration: 'none', display: 'inline-block' }}>View QR</a>}
      </div>
    </div>
  );
}

function AuthorizePanel({ cycle, onDone, setError }: { cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [manifests, setManifests] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { get(`/api/v1/cycles/${cycle}/manifests`).then(d => setManifests(d.manifests.filter((m: any) => m.manifest_id.startsWith('MFO-')))).catch(e => setError(String(e))); }, [cycle]);
  if (!manifests) return <div style={card}>Loading manifests…</div>;
  const notLocked = manifests.filter(m => m.manifest_status !== 'LOCKED').length;
  const checks: Check[] = [{ label: `All ${manifests.length} manifests LOCKED`, status: notLocked === 0 ? 'PASS' : 'FAIL', detail: notLocked === 0 ? undefined : `${notLocked} not yet sealed` }];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {manifests.map(m => <ManifestActionRow key={m.manifest_id} m={m} cycle={cycle} onDone={onDone} setError={setError} />)}
      </div>
      {manifests.length === 0 && <div style={card}>No routable manifests this cycle (every FPS was blocked or unroutable). The cycle can still be authorized.</div>}
      <DecisionGate title="Authorize cycle" checks={checks} action="Authorize (final human sign-off)" disabled={busy}
        onAction={() => safe(() => post(`/api/v1/cycles/${cycle}/authorize`), setError, setBusy).then(r => { if (r) onDone(); })} />
    </div>
  );
}

// ------------------------------------------------------------------ AUTHORIZED: dispatch

function DispatchPanel({ cycle, onDone, setError }: { cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <div style={card}>
      <strong>Ready to dispatch</strong>
      <p style={{ fontSize: 12, color: '#64748b' }}>Marks every LOCKED manifest DISPATCHED and moves its vehicle to IN_TRANSIT.</p>
      <button style={btn} disabled={busy} onClick={() => safe(() => post(`/api/v1/cycles/${cycle}/dispatch`), setError, setBusy).then(r => { if (r) onDone(); })}>Dispatch</button>
    </div>
  );
}

// ------------------------------------------------------------------ TRACKING/DELIVERING: record delivery

function DeliverForm({ m, onDone, setError }: { m: any; onDone: () => void; setError: (m: string | null) => void }) {
  const [detail, setDetail] = useState<any | null>(null);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { get(`/api/v1/manifests/${m.manifest_id}`).then(d => { setDetail(d); const q: Record<string, number> = {}; d.items.forEach((i: any) => { q[`${i.fps_id}|${i.commodity}`] = i.planned_kg; }); setQty(q); }).catch(e => setError(String(e))); }, [m.manifest_id]);
  if (!detail) return null;
  return (
    <div style={card}>
      <ManifestCard m={m} />
      <div style={{ fontSize: 12, marginTop: 8 }}>
        {detail.items.map((i: any) => (
          <div key={`${i.fps_id}|${i.commodity}`} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0' }}>
            <span style={{ width: 90 }}>{i.fps_id}</span><span style={{ width: 60 }}>{i.commodity}</span>
            <span>planned {i.planned_kg}kg → delivered</span>
            <input type="number" value={qty[`${i.fps_id}|${i.commodity}`] ?? 0} onChange={e => setQty(q => ({ ...q, [`${i.fps_id}|${i.commodity}`]: Number(e.target.value) }))} style={{ width: 80 }} />
          </div>
        ))}
      </div>
      <button style={btn} disabled={busy} onClick={() => {
        const items = detail.items.map((i: any) => ({ fps_id: i.fps_id, commodity: i.commodity, delivered_kg: qty[`${i.fps_id}|${i.commodity}`] ?? 0 }));
        safe(() => post(`/api/v1/manifests/${m.manifest_id}/deliver`, { items }), setError, setBusy).then(r => { if (r) onDone(); });
      }}>Record delivery</button>
    </div>
  );
}

function DeliveryPanel({ cycle, onDone, setError }: { cycle: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [manifests, setManifests] = useState<any[] | null>(null);
  useEffect(() => { get(`/api/v1/cycles/${cycle}/manifests`).then(d => setManifests(d.manifests.filter((m: any) => m.manifest_id.startsWith('MFO-')))).catch(e => setError(String(e))); }, [cycle]);
  if (!manifests) return <div style={card}>Loading manifests…</div>;
  const dispatched = manifests.filter(m => m.manifest_status === 'DISPATCHED');
  const delivered = manifests.filter(m => m.manifest_status === 'DELIVERED');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {dispatched.map(m => <DeliverForm key={m.manifest_id} m={m} onDone={onDone} setError={setError} />)}
      {delivered.length > 0 && <div style={card}><strong>Delivered ({delivered.length})</strong>{delivered.map(m => <ManifestCard key={m.manifest_id} m={m} />)}</div>}
      {dispatched.length === 0 && delivered.length === 0 && <div style={card}>No dispatched manifests to deliver.</div>}
    </div>
  );
}

// ------------------------------------------------------------------ RECONCILING/AUDITING: 7 closure checks, close

function ReconcilePanel({ cycle, state, onDone, setError }: { cycle: string; state: string; onDone: () => void; setError: (m: string | null) => void }) {
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<any | null>(null);
  const checks: Check[] = last ? Object.entries(last.checks).map(([k, v]) => ({ label: k.replace(/_/g, ' '), status: v ? 'PASS' : 'FAIL' })) : [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <DecisionGate title="Reconcile (the 7 closure checks)" checks={checks.length ? checks : [{ label: 'Not yet run', status: 'WARN', detail: 'click Reconcile' }]}
        action="Reconcile" disabled={busy}
        onAction={() => safe(() => post(`/api/v1/cycles/${cycle}/reconcile`), setError, setBusy).then(r => { if (r) { setLast(r); onDone(); } })} />
      {state === 'AUDITING' && (
        <div style={card}>
          <strong>All checks passed — ready to close</strong>
          <div><button style={btn} disabled={busy} onClick={() => safe(() => post(`/api/v1/cycles/${cycle}/close`), setError, setBusy).then(r => { if (r) onDone(); })}>Close Cycle</button></div>
        </div>
      )}
    </div>
  );
}

function ClosedPanel({ cycle }: { cycle: string }) {
  return <div style={card}><strong>Cycle {cycle} is CLOSED</strong><p style={{ fontSize: 12, color: '#64748b' }}>Complete audit trail available via /api/v1/auth/audit.</p></div>;
}
