/**
 * Auditor Portal — workflow-driven PDS Audit & Decision Trace workspace.
 * TOP = persistent 7-stage workflow bar, BELOW = evidence workspace for the stage.
 * NO sidebar. Read-only: the auditor verifies, never modifies. Every value comes
 * from backend/api/auditor.py; absent data renders DATA UNAVAILABLE, never invented.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ApiError } from '../api/client';
import { c, font, label, s, btn, btnGhost, btnDisabled, kg, num } from '../dso/theme';
import { auditorApi } from '../auditor/api';
import { IntelSection, fetchIntel } from '../components/Intelligence';

// ---------------------------------------------------------------- constants
const STAGES = [
  { n: 1, key: 'OVERVIEW', name: 'Cycle Overview', hint: 'Where is this cycle?' },
  { n: 2, key: 'DEMAND', name: 'Demand & Allocation', hint: 'Is the chain traceable?' },
  { n: 3, key: 'DISPATCH', name: 'Dispatch & Manifest', hint: 'Are seals intact?' },
  { n: 4, key: 'DELIVERY', name: 'Delivery & Reconciliation', hint: 'What varies?' },
  { n: 5, key: 'EXCEPTIONS', name: 'Exceptions', hint: 'What needs attention?' },
  { n: 6, key: 'TRACE', name: 'Decision Trace', hint: 'Who decided what?' },
  { n: 7, key: 'CLOSURE', name: 'Final Audit & Closure', hint: 'Ready to close?' },
] as const;

function stageTone(st: string): 'ok' | 'warn' | 'bad' | 'idle' | 'accent' {
  switch (st) {
    case 'COMPLETED': return 'ok';
    case 'IN REVIEW': return 'accent';
    case 'ACTION REQUIRED': case 'BLOCKED': return 'bad';
    default: return 'idle';
  }
}
function fmtDT(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true });
}
function fmtD(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
function errMsg(e: unknown): string { return e instanceof ApiError ? e.message : String(e); }
function unavailable(v: unknown): boolean { return v === null || v === undefined; }
const NA = <span style={{ color: c.faint }}>DATA UNAVAILABLE</span>;

// persistence
const ck = 'dsp-audit-cycle', dk = 'dsp-audit-district', sk = (cy: string) => `dsp-audit-step-${cy}`;
function load(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } }
function store(k: string, v: string) { try { localStorage.setItem(k, v); } catch {} }

// ---------------------------------------------------------------- small ui
function Badge({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'idle' | 'accent'; children: React.ReactNode }) {
  const map = {
    ok: [c.ok, c.okBg, c.okLine], warn: [c.warn, c.warnBg, c.warnLine], bad: [c.bad, c.badBg, c.badLine],
    idle: [c.muted, c.canvas, c.line], accent: [c.accent, c.accentBg, '#BFDBFE'],
  } as const;
  const [fg, bg, ln] = map[tone];
  return <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.04em', color: fg, background: bg, border: `1px solid ${ln}`, padding: '3px 9px', borderRadius: 999, whiteSpace: 'nowrap' }}>{children}</span>;
}
function Card({ title, sub, action, children }: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(2), marginBottom: sub ? 2 : s(3) }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, color: c.ink }}>{title}</div>
        {action && <span style={{ marginLeft: 'auto' }}>{action}</span>}
      </div>
      {sub && <div style={{ fontSize: 11.5, color: c.muted, marginBottom: s(3) }}>{sub}</div>}
      {children}
    </div>
  );
}
function Stat({ k, v, sub, alert }: { k: string; v: string; sub?: string; alert?: boolean }) {
  return (
    <div style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), minWidth: 0 }}>
      <div style={label}>{k}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: alert ? c.bad : c.ink, marginTop: 2 }}>{v}</div>
      {sub && <div style={{ fontSize: 11, color: c.muted, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
function Err({ msg }: { msg: string }) {
  if (!msg) return null;
  return <div style={{ background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(2), borderRadius: 6, fontSize: 12.5, marginBottom: s(3) }}>{msg}</div>;
}
function Loading({ what }: { what: string }) {
  return <div style={{ padding: s(5), color: c.muted, fontSize: 13 }}>Loading {what}…</div>;
}
function Empty({ what }: { what: string }) {
  return <div style={{ padding: s(3), color: c.muted, fontSize: 12.5, background: c.raised, border: `1px dashed ${c.lineStrong}`, borderRadius: 6 }}>NO RECORDS AVAILABLE — {what}.</div>;
}

// ---------------------------------------------------------------- AI assistant (small, grounded)
const AI_SUGGESTIONS = [
  { intent: 'CLOSURE_WHY', label: 'Why is this cycle not ready for closure?' },
  { intent: 'EXCEPTIONS_WHICH', label: 'Which exceptions affected this cycle?' },
  { intent: 'VARIANCE_WHY', label: 'What caused this variance?' },
  { intent: 'MANIFEST_INTEGRITY', label: 'Which manifests have integrity issues?' },
  { intent: 'ALLOCATION_WHY', label: 'Why was this allocation created?' },
];
function AIAssistant({ cycle }: { cycle: string }) {
  const [q, setQ] = useState('');
  const [ans, setAns] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const ask = async (intent?: string, question?: string) => {
    setBusy(true); setErr('');
    try { setAns(await auditorApi.ask(cycle, intent ? { intent } : { question: question ?? q })); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Card title="AI Audit Assistant" sub="Grounded in real data · advisory only — never modifies records">
      <div style={{ display: 'flex', gap: s(2), flexWrap: 'wrap', marginBottom: s(2) }}>
        {AI_SUGGESTIONS.map(sg => (
          <button key={sg.intent} onClick={() => ask(sg.intent)} disabled={busy}
            style={{ ...btnGhost, padding: '4px 10px', fontSize: 11.5 }}>{sg.label}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: s(2) }}>
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && q.trim() && ask(undefined, q)}
          placeholder="Ask a question…" style={{ flex: 1, border: `1px solid ${c.lineStrong}`, borderRadius: 6, padding: '8px 10px', fontSize: 13 }} />
        <button onClick={() => q.trim() && ask(undefined, q)} disabled={busy || !q.trim()} style={busy || !q.trim() ? btnDisabled : btn}>ASK</button>
      </div>
      {err && <div style={{ color: c.bad, fontSize: 12, marginTop: s(2) }}>{err}</div>}
      {busy && <div style={{ fontSize: 12, color: c.muted, marginTop: s(2) }}>Reading evidence…</div>}
      {ans && (
        <div style={{ background: c.accentBg, border: '1px solid #BFDBFE', borderRadius: 6, padding: s(3), marginTop: s(2) }}>
          <div style={{ ...label, color: c.accent }}>AI insight</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>{ans.insight}</div>
          <div style={{ ...label, marginTop: s(2) }}>Evidence</div>
          {(ans.evidence || []).map((e: string, i: number) => <div key={i} style={{ fontSize: 12.5, marginTop: 2 }}>• {e}</div>)}
          <div style={{ fontSize: 11, color: c.muted, marginTop: s(2) }}>Source records: {(ans.source_records || []).join(', ')} · Confidence: {ans.confidence}</div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- header + workflow bar
function TopHeader({ user, logout, cycles, cycle, setCycle, districts, district, setDistrict, cycleState, lastSync, notif, step }: any) {
  const sel: React.CSSProperties = { padding: '6px 8px', border: `1px solid ${c.lineStrong}`, borderRadius: 5, fontSize: 12.5, background: '#fff', maxWidth: 190 };
  return (
    <header style={{ background: '#071A31', color: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(3), padding: `${s(2)} ${s(4)}`, flexWrap: 'wrap' }}>
        <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>◈</div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 800 }}>DemandSYNC <span style={{ fontWeight: 400, fontSize: 10.5, opacity: 0.7 }}>PDS PREDICT</span></div>
          <div style={{ fontSize: 10.5, opacity: 0.7 }}>Auditor Portal · Transparency — Accountability — Food Security</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(2), marginLeft: s(3), background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '5px 10px' }}>
          <label style={{ fontSize: 10, opacity: 0.7, fontWeight: 700 }}>CYCLE<br />
            <select value={cycle ?? ''} onChange={e => setCycle(e.target.value)} style={{ ...sel, background: '#0F2542', color: '#fff', border: '1px solid rgba(255,255,255,0.25)', marginTop: 2 }}>
              {(cycles || []).map((x: any) => <option key={x.cycle} value={x.cycle}>{x.cycle} ({x.state})</option>)}
            </select></label>
          <label style={{ fontSize: 10, opacity: 0.7, fontWeight: 700 }}>DISTRICT<br />
            <select value={district ?? ''} onChange={e => setDistrict(e.target.value || null)} style={{ ...sel, background: '#0F2542', color: '#fff', border: '1px solid rgba(255,255,255,0.25)', marginTop: 2 }}>
              <option value="">All districts</option>
              {(districts || []).map((d: string) => <option key={d} value={d}>{d}</option>)}
            </select></label>
          <span style={{ fontSize: 11 }}><span style={{ opacity: 0.7 }}>Status </span><strong>{cycleState ?? '—'}</strong></span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: s(3), flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 700 }}><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#16A34A', marginRight: 6 }} />System Online</span>
          <span style={{ fontSize: 11, opacity: 0.7 }}>Last sync: {lastSync ? fmtDT(lastSync) : '—'}</span>
          <span style={{ position: 'relative', fontSize: 12, border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 10px' }}>🔔{notif > 0 && (
            <span style={{ position: 'absolute', top: -8, right: -8, background: '#DC2626', color: '#fff', fontSize: 10, fontWeight: 800, borderRadius: 999, minWidth: 18, height: 18, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{notif}</span>)}
          </span>
          <span style={{ fontSize: 12, textAlign: 'right' }}><strong>{user.name}</strong><span style={{ display: 'block', fontSize: 11, opacity: 0.7 }}>Auditor · {user.district ?? '—'}</span></span>
          <span style={{ fontSize: 11, textAlign: 'right', opacity: 0.85 }}>Step {step + 1} of 7<span style={{ display: 'block', fontWeight: 800, color: '#FF9933', opacity: 1 }}>{STAGES[step].name}</span></span>
          <Link to="/change-password" style={{ color: '#fff', fontSize: 12 }}>Change password</Link>
          <button onClick={logout} style={{ background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 12px', font: `600 12px ${font.ui}`, cursor: 'pointer' }}>Sign out</button>
        </div>
      </div>
      <div style={{ display: 'flex', height: 3 }}><div style={{ flex: 1, background: '#FF9933' }} /><div style={{ flex: 1, background: '#fff' }} /><div style={{ flex: 1, background: '#138808' }} /></div>
    </header>
  );
}

function WorkflowBar({ active, stages, onGo }: { active: number; stages: any[]; onGo: (i: number) => void }) {
  const byKey = Object.fromEntries((stages || []).map((x: any) => [x.key, x]));
  return (
    <div style={{ background: '#fff', borderBottom: `1px solid ${c.line}`, padding: `${s(2)} ${s(4)}`, overflowX: 'auto', position: 'sticky', top: 0, zIndex: 5 }}>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, minWidth: 1080 }}>
        {STAGES.map((st, i) => {
          const info = byKey[st.key] || { status: 'NOT STARTED', timestamp: null };
          const cur = i === active;
          const tone = stageTone(info.status);
          const dot = { ok: c.ok, warn: c.warn, bad: c.bad, idle: c.faint, accent: '#1D4ED8' }[tone];
          return (
            <span key={st.key} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              {i > 0 && <span style={{ margin: '0 6px', color: c.faint, fontSize: 14 }}>→</span>}
              <button onClick={() => onGo(i)} title={`${st.name} — ${st.hint}`}
                style={{
                  display: 'flex', gap: s(2), alignItems: 'flex-start', textAlign: 'left',
                  background: cur ? '#EFF6FF' : '#fff', border: `1px solid ${cur ? '#1D4ED8' : c.line}`,
                  borderRadius: 7, padding: '9px 12px', cursor: 'pointer', minWidth: 148,
                  boxShadow: cur ? '0 0 0 3px #DBEAFE' : 'none',
                }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: dot, color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800, flexShrink: 0 }}>
                  {info.status === 'COMPLETED' ? '✓' : info.status === 'ACTION_REQUIRED' || info.status === 'BLOCKED' ? '!' : st.n}
                </span>
                <span>
                  <span style={{ display: 'block', fontSize: 12, fontWeight: 800, color: c.ink }}>{st.n}. {st.name}</span>
                  <span style={{ display: 'block', fontSize: 10, fontWeight: 800, color: dot, marginTop: 2 }}>{info.status.replace('_', ' ')}</span>
                  <span style={{ display: 'block', fontSize: 10, color: c.muted, marginTop: 1 }}>{info.timestamp ? fmtDT(info.timestamp) : '—'}</span>
                </span>
              </button>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- stage panels
function OverviewPanel({ data }: { data: any }) {
  const cyc = data.cycle, sm = data.summary;
  const rows: [string, string][] = [
    ['Cycle identity', cyc.cycle], ['District scope', 'All districts (state audit)'], ['Cycle period', `${fmtD(cyc.choice_window_start)} → ${fmtD(cyc.choice_window_end)}`],
    ['Current backend state', cyc.state], ['Opened at', fmtDT(cyc.choice_window_start)], ['Locked at', fmtDT(cyc.locked_at)],
    ['Authorized at', unavailable(cyc.authorized_at) ? 'DATA UNAVAILABLE' : fmtDT(cyc.authorized_at)],
    ['Dispatch started', unavailable(cyc.dispatch_started_at) ? 'DATA UNAVAILABLE' : fmtDT(cyc.dispatch_started_at)],
    ['Delivery completed', unavailable(cyc.delivery_completed_at) ? 'DATA UNAVAILABLE' : fmtDT(cyc.delivery_completed_at)],
    ['Audit status', cyc.state === 'CLOSED' ? 'CLOSED' : 'OPEN FOR REVIEW'],
  ];
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: s(3) }}>
        <Card title="Cycle identity">
          {rows.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', padding: '7px 0', borderBottom: `1px solid ${c.line}`, fontSize: 12.5 }}>
              <span style={{ color: c.muted, flex: '0 0 170px' }}>{k}</span><strong>{v}</strong>
            </div>
          ))}
        </Card>
        <Card title="Audit summary">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(2) }}>
            <Stat k="Total beneficiaries" v={num(sm.total_beneficiaries)} />
            <Stat k="Total demand" v={kg(sm.total_demand_kg)} />
            <Stat k="Total allocated" v={kg(sm.total_allocated_kg)} />
            <Stat k="Total dispatched" v={kg(sm.total_dispatched_kg)} />
            <Stat k="Total received" v={kg(sm.total_received_kg)} />
            <Stat k="Total distributed" v={kg(sm.total_distributed_kg)} />
            <Stat k="Total variance" v={`${sm.total_variance_kg > 0 ? '+' : ''}${num(sm.total_variance_kg)} kg`} alert={sm.total_variance_kg !== 0} />
            <Stat k="Exceptions" v={`${sm.open_exceptions} open`} sub={`${sm.resolved_exceptions} resolved`} alert={sm.open_exceptions > 0} />
            <Stat k="Manifests" v={String(sm.manifest_count)} />
            <Stat k="Deliveries" v={String(sm.delivery_count)} />
          </div>
        </Card>
        <Card title="Audit readiness">
          {data.readiness.map((r: any) => (
            <div key={r.key} style={{ display: 'flex', gap: s(2), alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${c.line}`, fontSize: 13 }}>
              <span style={{ width: 20, height: 20, borderRadius: '50%', background: r.met ? c.ok : c.canvas, color: r.met ? '#fff' : c.faint, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 800 }}>{r.met ? '✓' : '–'}</span>
              <span>{r.label}</span>
            </div>
          ))}
        </Card>
      </div>
      <IntelSection title="Audit intelligence" subtitle="Override patterns, reconciliation anomalies, closure blockers with evidence — advisory only"
        fetch={() => fetchIntel('auditor', cyc.cycle).then(r => r.insights)}
        emptyWhy="No audit patterns require review in this cycle." />
    </div>
  );
}

function DemandPanel({ data, cycle }: { data: any; cycle: string }) {
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="Demand → forecast → allocation chain" sub="Intent − Forecast and Forecast − Baseline differences use the backend's own arithmetic.">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ color: c.muted }}>{['Commodity', 'Intent', 'Forecast', 'Baseline', 'Validated (locked)', 'Allocated', 'Intent − Fcst', 'Fcst − Base'].map(h =>
              <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, textAlign: 'left' }}>{h.toUpperCase()}</th>)}</tr></thead>
            <tbody>
              {data.chain.map((r: any) => (
                <tr key={r.commodity} style={{ borderBottom: `1px solid ${c.line}` }}>
                  <td style={{ padding: '9px 10px', fontWeight: 800 }}>{r.commodity}</td>
                  <td style={{ padding: '9px 10px' }}>{kg(r.intent_kg)}</td>
                  <td style={{ padding: '9px 10px' }}>{unavailable(r.forecast_kg) ? NA : kg(r.forecast_kg)}</td>
                  <td style={{ padding: '9px 10px' }}>{unavailable(r.baseline_kg) ? NA : kg(r.baseline_kg)}</td>
                  <td style={{ padding: '9px 10px' }}>{unavailable(r.validated_kg) ? NA : kg(r.validated_kg)}</td>
                  <td style={{ padding: '9px 10px', fontWeight: 700 }}>{kg(r.allocated_kg)}</td>
                  <td style={{ padding: '9px 10px' }}>{unavailable(r.intent_minus_forecast_kg) ? NA : `${Number(r.intent_minus_forecast_kg) > 0 ? '+' : ''}${num(r.intent_minus_forecast_kg)} kg`}</td>
                  <td style={{ padding: '9px 10px' }}>{unavailable(r.forecast_minus_baseline_kg) ? NA : `${Number(r.forecast_minus_baseline_kg) > 0 ? '+' : ''}${num(r.forecast_minus_baseline_kg)} kg`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: s(3) }}>
        <Card title="Evidence: demand lock & forecast">
          <div style={{ fontSize: 12.5, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div>Demand lock: {data.demand_lock.locked
              ? <span><Badge tone="ok">SEALED ✓</Badge> <span className="mono" style={{ fontFamily: font.mono }}>{String(data.demand_lock.sha256_hash).slice(0, 20)}…</span><div style={{ color: c.muted, fontSize: 11.5, marginTop: 4 }}>Locked {fmtDT(data.demand_lock.locked_at)} by {data.demand_lock.locked_by}</div></span>
              : <span><Badge tone="idle">NOT SEALED</Badge> <span style={{ color: c.muted }}>No demand lock for {cycle}.</span></span>}</div>
            <div>Forecast model: {data.forecast ? <span><strong>{data.forecast.model_version}</strong> · {data.forecast.rows} rows · {fmtDT(data.forecast.generated_at)}</span> : NA}</div>
          </div>
        </Card>
        <Card title={`Manual overrides (${data.overrides.length})`} sub="WHO · WHAT · WHEN · WHY · BEFORE → AFTER">
          {data.overrides.length === 0 && data.override_events.length === 0 && <Empty what="no manual overrides recorded for this cycle" />}
          {data.override_events.map((e: any) => (
            <div key={e.audit_event_id} style={{ border: `1px solid ${c.line}`, borderLeft: `4px solid ${c.warn}`, borderRadius: 6, padding: s(2), marginBottom: s(2), fontSize: 12.5 }}>
              <div><strong>{e.actor_user_id}</strong> ({e.actor_role}) · {fmtDT(e.timestamp)}</div>
              <div style={{ marginTop: 2 }}>Before: <span style={{ fontFamily: font.mono }}>{e.before_state ?? '—'}</span> → After: <span style={{ fontFamily: font.mono }}>{e.after_state ?? '—'}</span></div>
              <div style={{ color: c.muted, marginTop: 2 }}>Reason: {e.reason || '—'}</div>
            </div>
          ))}
        </Card>
      </div>
      <AIAssistant cycle={cycle} />
    </div>
  );
}

function ManifestPanel({ data, onOpen }: { data: any; onOpen: (id: string) => void }) {
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title={`Manifest evidence — ${data.cycle}${data.district ? ` · ${data.district}` : ''}`} sub={`${data.manifests.length} manifests. Hash status is recomputed from stored rows.`}>
        {data.manifests.length === 0 ? <Empty what="no manifests for this scope" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <thead><tr style={{ color: c.muted }}>{['Manifest', 'Vehicle', 'Warehouse', 'FPS dest.', 'Planned', 'Status', 'Created', 'Authorized', 'Hash'].map(h =>
                <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, textAlign: 'left' }}>{h.toUpperCase()}</th>)}</tr></thead>
              <tbody>
                {data.manifests.map((m: any) => (
                  <tr key={m.manifest_id} style={{ borderBottom: `1px solid ${c.line}` }}>
                    <td style={{ padding: '8px 10px' }}><button onClick={() => onOpen(m.manifest_id)} style={{ background: 'none', border: 'none', color: c.accent, cursor: 'pointer', fontFamily: font.mono, fontSize: 12, fontWeight: 700, padding: 0 }}>{m.manifest_id}</button></td>
                    <td style={{ padding: '8px 10px' }}>{m.vehicle_id ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{m.warehouse_id ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{m.fps_count ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{kg(m.planned_kg)}</td>
                    <td style={{ padding: '8px 10px' }}><Badge tone={m.manifest_status === 'LOCKED' || m.manifest_status === 'DELIVERED' ? 'ok' : m.manifest_status === 'DRAFT' ? 'idle' : 'accent'}>{m.manifest_status}</Badge></td>
                    <td style={{ padding: '8px 10px' }}>{fmtDT(m.created_at)}</td>
                    <td style={{ padding: '8px 10px' }}>{m.locked_at ? fmtDT(m.locked_at) : '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{m.hash_verified === true ? <Badge tone="ok">VERIFIED ✓</Badge> : m.hash_verified === false ? <Badge tone="bad">FAILED</Badge> : <Badge tone="idle">NOT SEALED</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function ManifestDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    auditorApi.manifest(id).then(setD).catch(e => setErr(errMsg(e)));
  }, [id]);
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(7,26,49,0.45)', zIndex: 50, display: 'flex', justifyContent: 'flex-end' }} onClick={onClose}>
      <div style={{ width: 'min(560px, 94vw)', background: '#fff', height: '100%', overflowY: 'auto', padding: s(4) }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
          <div style={{ fontSize: 15, fontWeight: 800, fontFamily: font.mono }}>{id}</div>
          <button onClick={onClose} style={{ ...btnGhost, marginLeft: 'auto', padding: '5px 10px' }}>Close</button>
        </div>
        {err && <div style={{ color: c.bad, fontSize: 12.5, marginTop: s(2) }}>{err}</div>}
        {!d && !err && <Loading what="manifest evidence" />}
        {d && (
          <div style={{ marginTop: s(3), display: 'flex', flexDirection: 'column', gap: s(3), fontSize: 12.5 }}>
            <Card title="Manifest identity">
              {[['Cycle', d.cycle], ['Vehicle', d.vehicle_id ?? 'DATA UNAVAILABLE'], ['Warehouse', d.warehouse_id ?? 'DATA UNAVAILABLE'],
                ['Status', d.manifest_status], ['Total', kg(d.total_kg)], ['Route distance', d.route_distance_km != null ? `${num(d.route_distance_km)} km (haversine)` : 'DATA UNAVAILABLE'],
                ['Created by', d.created_by ?? '—'], ['Created', fmtDT(d.created_at)],
                ['Locked by', d.locked_by ?? '—'], ['Locked', fmtDT(d.locked_at)],
              ].map(([k, v]) => <div key={k as string} style={{ display: 'flex', padding: '5px 0', borderBottom: `1px solid ${c.line}` }}><span style={{ color: c.muted, flex: '0 0 130px' }}>{k}</span><strong>{v}</strong></div>)}
              <div style={{ marginTop: s(2) }}>Authorization: {d.authorization ? <span>cycle authorized by <strong>{d.authorization.actor_user_id}</strong> · {fmtDT(d.authorization.timestamp)}</span> : 'DATA UNAVAILABLE'}</div>
            </Card>
            <Card title="SHA-256 integrity">
              <div className="mono" style={{ fontFamily: font.mono, fontSize: 11, wordBreak: 'break-all', background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(2) }}>
                {d.sha256_hash ?? 'No seal recorded.'}
              </div>
              <div style={{ marginTop: s(2) }}>
                {d.lock_verification?.hash_verified === true && <Badge tone="ok">✓ HASH VERIFIED — MANIFEST IMMUTABLE</Badge>}
                {d.lock_verification?.hash_verified === false && (
                  <div style={{ background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, fontWeight: 800, padding: s(2), borderRadius: 6 }}>MANIFEST INTEGRITY CHECK FAILED</div>
                )}
                {d.lock_verification?.hash_verified == null && <Badge tone="idle">NOT SEALED — {d.lock_verification?.note ?? ''}</Badge>}
              </div>
              {d.qr_png_base64
                ? <div style={{ marginTop: s(2) }}><div style={label}>QR code (sealed payload)</div><img src={`data:image/png;base64,${d.qr_png_base64}`} alt="Manifest QR" style={{ width: 140, height: 140, marginTop: 6, border: `1px solid ${c.line}` }} /></div>
                : <div style={{ fontSize: 12, color: c.muted, marginTop: s(2) }}>No QR payload — manifest not yet sealed.</div>}
            </Card>
            <Card title={`FPS destinations (${(d.items || []).length})`}>
              {(d.items || []).map((it: any) => (
                <div key={it.manifest_item_id} style={{ display: 'flex', gap: s(2), fontSize: 12.5, padding: '6px 0', borderBottom: `1px solid ${c.line}` }}>
                  <span style={{ fontFamily: font.mono, fontWeight: 700 }}>{it.fps_id}</span>
                  <span>{it.commodity}</span><span style={{ marginLeft: 'auto', fontWeight: 700 }}>{kg(it.planned_kg)}</span>
                </div>
              ))}
              {(d.items || []).length === 0 && <Empty what="no manifest items" />}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

function DeliveryPanel({ data, cycle }: { data: any; cycle: string }) {
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="Reconciliation flow" sub="Allocated → Dispatched → Received → Distributed, variance at the received/distributed transition.">
        <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, overflowX: 'auto' }}>
          {data.flow.map((f: any, i: number) => (
            <span key={f.commodity} style={{ display: 'flex', alignItems: 'stretch', flexShrink: 0 }}>
              {i > 0 && <span style={{ alignSelf: 'center', margin: '0 8px', color: c.faint }}>→</span>}
              <span style={{ border: `1px solid ${f.status === 'VERIFIED' ? c.okLine : f.status === 'VARIANCE' ? c.warnLine : c.line}`, borderRadius: 7, padding: s(3), minWidth: 210, background: '#fff' }}>
                <span style={{ fontWeight: 800 }}>{f.commodity}</span> <Badge tone={f.status === 'VERIFIED' ? 'ok' : f.status === 'VARIANCE' ? 'warn' : 'idle'}>{f.status}</Badge>
                <span style={{ display: 'block', fontSize: 12, marginTop: 6 }}>Allocated {kg(f.allocated_kg)}</span>
                <span style={{ display: 'block', fontSize: 12 }}>↓ Dispatched {kg(f.dispatched_kg)}</span>
                <span style={{ display: 'block', fontSize: 12 }}>↓ Received {kg(f.received_kg)}</span>
                <span style={{ display: 'block', fontSize: 12 }}>↓ Distributed {kg(f.distributed_kg)}</span>
                <span style={{ display: 'block', fontSize: 12, fontWeight: 800, color: f.variance_kg ? c.warn : c.ok }}>Variance {f.variance_kg > 0 ? '+' : ''}{num(f.variance_kg)} kg</span>
              </span>
            </span>
          ))}
        </div>
        <div style={{ fontSize: 12, color: c.body, marginTop: s(2) }}>
          Closure checks: {data.checks_passed == null ? 'DATA UNAVAILABLE' : data.checks_passed ? 'all pass' : `failing: ${Object.entries(data.closure_checks || {}).filter(([, v]) => !v).map(([k]) => k).join(', ')}`}
        </div>
      </Card>
      <Card title={`Delivery evidence (${data.total})`} sub={data.district ? `Filtered to ${data.district}.` : 'All districts.'}>
        {data.deliveries.length === 0 ? <Empty what="no delivery records for this scope" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <thead><tr style={{ color: c.muted }}>{['FPS', 'Manifest', 'Vehicle', 'Planned', 'Delivered', 'Variance', 'Recorded by', 'Timestamp', 'Verification'].map(h =>
                <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, textAlign: 'left' }}>{h.toUpperCase()}</th>)}</tr></thead>
              <tbody>
                {data.deliveries.map((r: any) => (
                  <tr key={r.delivery_id} style={{ borderBottom: `1px solid ${c.line}` }}>
                    <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 11.5 }}>{r.fps_id}</td>
                    <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 11.5 }}>{r.manifest_id}</td>
                    <td style={{ padding: '8px 10px' }}>{r.vehicle_id ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{kg(r.planned_kg)}</td>
                    <td style={{ padding: '8px 10px', fontWeight: 700 }}>{kg(r.delivered_kg)}</td>
                    <td style={{ padding: '8px 10px', fontWeight: 700, color: r.variance_kg ? c.warn : c.ok }}>{r.variance_kg != null ? `${Number(r.variance_kg) > 0 ? '+' : ''}${num(r.variance_kg)} kg` : '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{r.verified_by ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{fmtDT(r.delivery_date)}</td>
                    <td style={{ padding: '8px 10px' }}><Badge tone={r.status === 'VERIFIED' ? 'ok' : r.status === 'VARIANCE' ? 'warn' : 'bad'}>{r.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <AIAssistant cycle={cycle} />
    </div>
  );
}

function ExceptionsPanel({ data, cycle, onFilter }: { data: any; cycle: string; onFilter: (sev: string | null) => void }) {
  const [sel, setSel] = useState<any>(null);
  const o = data.open_by_severity;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: s(2) }}>
        {[['Critical', 'HIGH', o.HIGH, true], ['High', 'MEDIUM', o.MEDIUM, false], ['Medium', 'LOW', o.LOW, false]].map(([k, sev, v, alert]: any) => (
          <button key={k as string} onClick={() => onFilter(sev)} style={{ ...({} as any), background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), cursor: 'pointer', textAlign: 'left' }}>
            <div style={label}>{k}</div><div style={{ fontSize: 20, fontWeight: 800, color: alert && v > 0 ? c.bad : c.ink }}>{v}</div>
          </button>
        ))}
        <button onClick={() => onFilter(null)} style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), cursor: 'pointer', textAlign: 'left' }}>
          <div style={label}>Filter</div><div style={{ fontSize: 14, fontWeight: 800, color: c.accent }}>Show all</div>
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: sel ? '1fr 380px' : '1fr', gap: s(3), alignItems: 'start' }}>
        <Card title={`Exceptions (${data.exceptions.length} shown)`}>
          {data.exceptions.length === 0 ? <Empty what="no exceptions match this filter" /> :
            data.exceptions.map((e: any) => (
              <button key={e.exception_id} onClick={() => setSel(e)}
                style={{ width: '100%', textAlign: 'left', display: 'flex', gap: s(2), alignItems: 'center', background: sel?.exception_id === e.exception_id ? '#EFF6FF' : '#fff', border: 'none', borderBottom: `1px solid ${c.line}`, padding: '10px 4px', cursor: 'pointer', fontSize: 12.5 }}>
                <Badge tone={e.severity === 'HIGH' ? 'bad' : e.severity === 'MEDIUM' ? 'warn' : 'idle'}>{e.severity}</Badge>
                <span style={{ fontFamily: font.mono, fontWeight: 700, fontSize: 11.5 }}>{e.exception_id}</span>
                <span>{e.rule_code} · {e.entity_type} {e.entity_id}</span>
                <span style={{ marginLeft: 'auto' }}><Badge tone={e.status === 'OPEN' || e.status === 'ACTION_REQUIRED' ? 'bad' : e.status === 'RESOLVED' || e.status === 'CLOSED' ? 'ok' : 'accent'}>{e.status.replace('_', ' ')}</Badge></span>
              </button>
            ))}
        </Card>
        {sel && (
          <Card title={`Evidence ${sel.exception_id}`} action={<button onClick={() => setSel(null)} style={{ ...btnGhost, padding: '4px 10px', fontSize: 12 }}>Close</button>}>
            {[
              ['What happened?', sel.reason ?? 'DATA UNAVAILABLE'], ['Affected entity', `${sel.entity_type} ${sel.entity_id}`],
              ['Expected value', 'DATA UNAVAILABLE'], ['Actual value', 'DATA UNAVAILABLE'], ['Difference', 'DATA UNAVAILABLE'],
              ['Rule triggered', sel.rule_code ?? 'DATA UNAVAILABLE'], ['Evidence', sel.reason ?? 'DATA UNAVAILABLE'],
              ['Created by', sel.assigned_to ? `Assigned: ${sel.assigned_to}` : 'System rule engine'], ['Created at', fmtDT(sel.detected_at)],
              ['Resolution', sel.resolution ?? (sel.status === 'RESOLVED' || sel.status === 'CLOSED' ? '—' : 'UNRESOLVED')],
              ['Resolved at', sel.resolved_at ? fmtDT(sel.resolved_at) : sel.status === 'RESOLVED' || sel.status === 'CLOSED' ? '—' : 'UNRESOLVED'],
            ].map(([k, v]) => <div key={k as string} style={{ display: 'flex', padding: '6px 0', borderBottom: `1px solid ${c.line}`, fontSize: 12.5 }}><span style={{ color: c.muted, flex: '0 0 120px' }}>{k}</span><span>{v}</span></div>)}
          </Card>
        )}
      </div>
      <AIAssistant cycle={cycle} />
    </div>
  );
}

function TracePanel({ data, cycle, action, onAction }: { data: any; cycle: string; action: string | null; onAction: (a: string | null) => void }) {
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title={`Audit decision trace (${data.total} events)`} sub={`Chronological · hash chain ${data.chain_intact ? 'INTACT ✓' : 'BROKEN — investigate'}`}
        action={<select value={action ?? ''} onChange={e => onAction(e.target.value || null)} style={{ padding: 6, border: `1px solid ${c.lineStrong}`, borderRadius: 5, fontSize: 12 }}>
          <option value="">All actions</option>
          {(data.actions || []).map((a: string) => <option key={a} value={a}>{a}</option>)}
        </select>}>
        {data.events.length === 0 ? <Empty what="no audit events for this filter" /> : (
          <div style={{ position: 'relative', paddingLeft: 22 }}>
            <div style={{ position: 'absolute', left: 7, top: 6, bottom: 6, width: 2, background: c.line }} />
            {data.events.map((e: any) => (
              <div key={e.audit_event_id} style={{ position: 'relative', paddingBottom: s(3) }}>
                <span style={{ position: 'absolute', left: -21, top: 3, width: 12, height: 12, borderRadius: '50%', background: e.result === 'SUCCESS' ? c.ok : e.result === 'FAIL' ? c.bad : c.warn, border: '2px solid #fff', boxShadow: `0 0 0 1px ${c.lineStrong}` }} />
                <div style={{ fontSize: 13, fontWeight: 800 }}>{e.action.replace(/_/g, ' ')} <Badge tone={e.result === 'SUCCESS' ? 'ok' : e.result === 'FAIL' ? 'bad' : 'warn'}>{e.result}</Badge></div>
                <div style={{ fontSize: 12, color: c.body, marginTop: 2 }}>
                  WHO <strong>{e.actor_user_id}</strong> · ROLE {e.actor_role} · ENTITY {e.entity_type} {e.entity_id} · WHEN {fmtDT(e.timestamp)}
                </div>
                {e.reason && <div style={{ fontSize: 12, marginTop: 2 }}>WHY “{e.reason}”</div>}
                {(e.before_state || e.after_state) && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(2), marginTop: 6 }}>
                    <div style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 5, padding: s(2) }}><div style={label}>Before</div><div className="mono" style={{ fontFamily: font.mono, fontSize: 11, marginTop: 2, wordBreak: 'break-word' }}>{e.before_state ?? '—'}</div></div>
                    <div style={{ background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 5, padding: s(2) }}><div style={label}>After</div><div className="mono" style={{ fontFamily: font.mono, fontSize: 11, marginTop: 2, wordBreak: 'break-word' }}>{e.after_state ?? '—'}</div></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function ClosurePanel({ data, cycle }: { data: any; cycle: string }) {
  const toneFor = (st: string) => st === 'PASS' ? 'ok' as const : st === 'FAIL' ? 'bad' as const : st === 'WARNING' ? 'warn' as const : 'idle' as const;
  const decTone = data.decision === 'AUDIT READY' ? 'ok' as const : data.decision === 'AUDIT BLOCKED' ? 'bad' as const : 'warn' as const;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="Final audit checklist" sub="Each verdict is computed from backend evidence at load time.">
        {data.checklist.map((ch: any) => (
          <div key={ch.check} style={{ display: 'grid', gridTemplateColumns: '250px 130px 1fr', gap: s(2), alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${c.line}`, fontSize: 12.5 }}>
            <span style={{ fontWeight: 600 }}>{ch.check}</span>
            <span><Badge tone={toneFor(ch.status)}>{ch.status.replace('_', ' ')}</Badge></span>
            <span style={{ color: c.muted }}>{ch.evidence}</span>
          </div>
        ))}
      </Card>
      <div style={{ background: '#0F2542', color: '#fff', borderRadius: 8, padding: s(4) }}>
        <div style={label}>Audit decision</div>
        <div style={{ marginTop: 6 }}><Badge tone={decTone}>{data.decision}</Badge></div>
        <div style={{ fontSize: 12.5, marginTop: s(2), opacity: 0.85 }}>
          Auditor: signed-in auditor · Evidence: {data.checklist.length} checks above · Timestamp: load time (recomputed per visit).
        </div>
        <div style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 6, padding: s(3), marginTop: s(3), fontSize: 12.5, fontWeight: 700 }}>
          {data.final_action}
        </div>
      </div>
      <AIAssistant cycle={cycle} />
    </div>
  );
}

// ---------------------------------------------------------------- main shell
export default function AuditorPortal() {
  const { user, logout } = useAuth();
  const [cycles, setCycles] = useState<any[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [cycle, setCycle] = useState<string | null>(null);
  const [district, setDistrict] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [stages, setStages] = useState<any[]>([]);
  const [err, setErr] = useState('');
  const [ov, setOv] = useState<any>(null);
  const [demand, setDemand] = useState<any>(null);
  const [mans, setMans] = useState<any>(null);
  const [recon, setRecon] = useState<any>(null);
  const [exc, setExc] = useState<any>(null);
  const [excSev, setExcSev] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);
  const [traceAction, setTraceAction] = useState<string | null>(null);
  const [closure, setClosure] = useState<any>(null);
  const [manifestId, setManifestId] = useState<string | null>(null);

  // boot: cycles, persisted scope, default to most-evidenced cycle
  useEffect(() => {
    let dead = false;
    (async () => {
      try {
        const r = await auditorApi.cycles();
        if (dead) return;
        setCycles(r.cycles);
        setDistricts(r.districts || []);
        const savedCy = load(ck), savedD = load(dk);
        const valid = savedCy && r.cycles.some((x: any) => x.cycle === savedCy) ? savedCy : null;
        const best = valid || [...r.cycles].sort((a: any, b: any) =>
          ((b.evidence?.manifests || 0) + (b.evidence?.allocations || 0)) - ((a.evidence?.manifests || 0) + (a.evidence?.allocations || 0)))[0]?.cycle
          || r.cycles[0]?.cycle || null;
        setCycle(best);
        if (savedD && (r.districts || []).includes(savedD)) setDistrict(savedD);
        const restored = Number(load(sk(best)) || 0);
        if (restored) setStep(prev => (prev === 0 ? restored : prev));
      } catch (e) { if (!dead) setErr(errMsg(e)); }
    })();
    return () => { dead = true; };
  }, []);

  const loadStages = useCallback(async (cy: string) => {
    try { setStages((await auditorApi.stages(cy)).stages); } catch (e) { setErr(errMsg(e)); }
  }, []);

  // per-stage lazy loads
  useEffect(() => {
    if (!cycle) return;
    store(ck, cycle);
    loadStages(cycle);
    setOv(null); setDemand(null); setMans(null); setRecon(null); setExc(null); setTrace(null); setClosure(null);
    setExcSev(null); setTraceAction(null);
  }, [cycle, loadStages]);
  useEffect(() => { if (district !== undefined) store(dk, district ?? ''); }, [district]);

  const refreshStep = useCallback(async (st: number, cy: string, dist: string | null, sev: string | null, act: string | null) => {
    try {
      if (st === 0 && !ov) setOv(await auditorApi.overview(cy));
      if (st === 1 && !demand) setDemand(await auditorApi.demand(cy));
      if (st === 2) setMans(await auditorApi.manifests(cy, dist));
      if (st === 3) setRecon(await auditorApi.reconciliation(cy, dist));
      if (st === 4) setExc(await auditorApi.exceptions(cy, { severity: sev || undefined, district: dist }));
      if (st === 5) setTrace(await auditorApi.trace(cy, act || undefined));
      if (st === 6 && !closure) setClosure(await auditorApi.closure(cy));
      setErr('');
    } catch (e) { setErr(errMsg(e)); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ov, demand, closure]);

  useEffect(() => {
    if (cycle) refreshStep(step, cycle, district, excSev, traceAction);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, cycle, district, excSev, traceAction]);

  const go = (i: number) => {
    setStep(i);
    if (cycle) store(sk(cycle), String(i));
  };
  const changeCycle = (cy: string) => { setCycle(cy); setStep(Number(load(sk(cy)) || 0)); };

  if (!user) return null;
  const attention = stages.filter(x => x.status === 'ACTION_REQUIRED' || x.status === 'BLOCKED').length;

  return (
    <div style={{ minHeight: '100vh', background: '#F1F5F9', fontFamily: font.ui }}>
      <TopHeader user={user} logout={logout} cycles={cycles} cycle={cycle} setCycle={changeCycle}
        districts={districts} district={district} setDistrict={setDistrict}
        cycleState={cycles.find(x => x.cycle === cycle)?.state} lastSync={ov?.last_sync} notif={attention} step={step} />
      <WorkflowBar active={step} stages={stages} onGo={go} />
      {err && <div style={{ margin: `${s(2)} ${s(4)}`, background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(2), borderRadius: 6, fontSize: 12.5 }}>{err}</div>}
      {!cycle && !err && <Loading what="audit scope" />}
      <main>
        {cycle && step === 0 && (ov ? <OverviewPanel data={ov} /> : <Loading what="cycle overview" />)}
        {cycle && step === 1 && (demand ? <DemandPanel data={demand} cycle={cycle} /> : <Loading what="demand evidence" />)}
        {cycle && step === 2 && (mans ? <ManifestPanel data={mans} onOpen={setManifestId} /> : <Loading what="manifests" />)}
        {cycle && step === 3 && (recon ? <DeliveryPanel data={recon} cycle={cycle} /> : <Loading what="delivery evidence" />)}
        {cycle && step === 4 && (exc ? <ExceptionsPanel data={exc} cycle={cycle} onFilter={(sev) => { setExc(null); setExcSev(sev); }} /> : <Loading what="exceptions" />)}
        {cycle && step === 5 && (trace ? <TracePanel data={trace} cycle={cycle} action={traceAction} onAction={(a) => { setTrace(null); setTraceAction(a); }} /> : <Loading what="decision trace" />)}
        {cycle && step === 6 && (closure ? <ClosurePanel data={closure} cycle={cycle} /> : <Loading what="closure checklist" />)}
      </main>
      {manifestId && <ManifestDrawer id={manifestId} onClose={() => setManifestId(null)} />}
      <footer style={{ padding: s(4), textAlign: 'center', fontSize: 11, color: c.faint }}>
        DemandSYNC · Auditor workspace is read-only — verification never alters official records{district ? ` · District filter: ${district}` : ''}.
      </footer>
    </div>
  );
}
