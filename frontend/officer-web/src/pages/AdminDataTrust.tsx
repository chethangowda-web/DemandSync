/**
 * System Admin Portal — workflow-driven platform administration & security centre.
 * TOP = persistent 8-stage workflow bar, BELOW = workspace for the stage.
 * NO sidebar. Every value comes from backend/api/admin.py; absent data renders
 * DATA UNAVAILABLE. Account mutations are backend-authorized (MANAGE_USERS),
 * reason-gated, confirmed, and audited with before/after.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ApiError } from '../api/client';
import { c, font, label, s, btn, btnGhost, btnDisabled, num } from '../dso/theme';
import { adminApi } from '../admin/api';
import { IntelSection, fetchIntel } from '../components/Intelligence';

// ---------------------------------------------------------------- constants
const STAGES = [
  { n: 1, key: 'OVERVIEW', name: 'System Overview', hint: 'What is the system state?' },
  { n: 2, key: 'USERS', name: 'Users & RBAC', hint: 'Who has access?' },
  { n: 3, key: 'DATASETS', name: 'Dataset & Imports', hint: 'Is the data trustworthy?' },
  { n: 4, key: 'HEALTH', name: 'System Health', hint: 'What is healthy?' },
  { n: 5, key: 'INTEGRATIONS', name: 'Integrations', hint: 'What is connected?' },
  { n: 6, key: 'SECURITY', name: 'Security & Audit', hint: 'What changed?' },
  { n: 7, key: 'CONFIG', name: 'Configuration', hint: 'How is it configured?' },
  { n: 8, key: 'FINAL', name: 'Final System Status', hint: 'Ready or not?' },
] as const;

function stageTone(st: string): 'ok' | 'warn' | 'bad' | 'idle' | 'accent' {
  switch (st) {
    case 'COMPLETED': return 'ok';
    case 'IN REVIEW': return 'accent';
    case 'ACTION REQUIRED': case 'BLOCKED': case 'DEGRADED': return 'bad';
    default: return 'idle';
  }
}
function svcTone(st: string): 'ok' | 'warn' | 'bad' | 'idle' {
  return st === 'ONLINE' || st === 'PASS' ? 'ok' : st === 'DEGRADED' || st === 'WARNING' ? 'warn'
    : st === 'OFFLINE' || st === 'FAIL' ? 'bad' : 'idle';
}
function fmtDT(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true });
}
function errMsg(e: unknown): string { return e instanceof ApiError ? e.message : String(e); }
const NA = <span style={{ color: c.faint }}>DATA UNAVAILABLE</span>;
const NONE = <span style={{ color: c.muted }}>NO RECORDS AVAILABLE</span>;
const STEP_KEY = 'dsp-admin-step';
function loadStep(): number { try { const v = Number(localStorage.getItem(STEP_KEY)); return Number.isFinite(v) && v >= 0 && v <= 7 ? v : 0; } catch { return 0; } }

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
function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return <div style={{ display: 'flex', padding: '6px 0', borderBottom: `1px solid ${c.line}`, fontSize: 12.5 }}><span style={{ color: c.muted, flex: '0 0 170px' }}>{k}</span><span>{v}</span></div>;
}

// ---------------------------------------------------------------- AI assistant (compact, grounded)
const AI_SUGGESTIONS = [
  { intent: 'SECURITY_ANOMALIES', label: 'Show recent security anomalies.' },
  { intent: 'DATASETS_FAILED', label: 'Which datasets failed validation?' },
  { intent: 'INTEGRATIONS_DOWN', label: 'Which integrations are unavailable?' },
  { intent: 'CYCLE_BLOCKED', label: 'Why is this cycle blocked?' },
  { intent: 'FORECAST_WHY', label: 'Why is the forecast service degraded?' },
];
function AIAssistant() {
  const [q, setQ] = useState('');
  const [ans, setAns] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const ask = async (intent?: string, question?: string) => {
    setBusy(true); setErr('');
    try { setAns(await adminApi.ask(intent ? { intent } : { question: question ?? q })); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Card title="AI Admin Assistant" sub="Grounded in backend evidence · advisory only — never mutates">
      <div style={{ display: 'flex', gap: s(2), flexWrap: 'wrap', marginBottom: s(2) }}>
        {AI_SUGGESTIONS.map(sg => (
          <button key={sg.intent} onClick={() => ask(sg.intent)} disabled={busy}
            style={{ ...btnGhost, padding: '4px 10px', fontSize: 11.5 }}>{sg.label}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: s(2) }}>
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && q.trim() && ask(undefined, q)}
          placeholder="Ask about system state…" style={{ flex: 1, border: `1px solid ${c.lineStrong}`, borderRadius: 6, padding: '8px 10px', fontSize: 13 }} />
        <button onClick={() => q.trim() && ask(undefined, q)} disabled={busy || !q.trim()} style={busy || !q.trim() ? btnDisabled : btn}>ASK</button>
      </div>
      {err && <div style={{ color: c.bad, fontSize: 12, marginTop: s(2) }}>{err}</div>}
      {ans && (
        <div style={{ background: c.accentBg, border: '1px solid #BFDBFE', borderRadius: 6, padding: s(3), marginTop: s(2) }}>
          <div style={{ ...label, color: c.accent }}>Insight</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>{ans.insight}</div>
          <div style={{ ...label, marginTop: s(2) }}>Evidence</div>
          {(ans.evidence || []).map((e: string, i: number) => <div key={i} style={{ fontSize: 12.5, marginTop: 2 }}>• {e}</div>)}
          <div style={{ fontSize: 11, color: c.muted, marginTop: s(2) }}>Source: {(ans.source_records || []).join(', ')} · Confidence: {ans.confidence}</div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- header + workflow
function TopHeader({ user, logout, cycle, cycleState, backend, lastSync, notif, step }: any) {
  return (
    <header style={{ background: '#071A31', color: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(3), padding: `${s(2)} ${s(4)}`, flexWrap: 'wrap' }}>
        <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>◈</div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 800 }}>DemandSYNC <span style={{ fontWeight: 400, fontSize: 10.5, opacity: 0.7 }}>PDS PREDICT</span></div>
          <div style={{ fontSize: 10.5, opacity: 0.7 }}>System Administration · Platform control centre</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(3), marginLeft: s(3), background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 12px', fontSize: 12 }}>
          <span><span style={{ opacity: 0.7 }}>Current cycle </span><strong>{cycle ?? '—'}</strong></span>
          <span><span style={{ opacity: 0.7 }}>Jurisdiction </span><strong>All districts</strong></span>
          <span><span style={{ opacity: 0.7 }}>System </span><strong style={{ color: backend === 'ONLINE' ? '#4ADE80' : '#FBBF24' }}>{backend ?? '—'}</strong></span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: s(3), flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 700 }}><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: backend === 'ONLINE' ? '#16A34A' : '#F59E0B', marginRight: 6 }} />{backend === 'ONLINE' ? 'Backend Operational' : 'Backend Degraded'}</span>
          <span style={{ fontSize: 11, opacity: 0.7 }}>Last sync: {lastSync ? fmtDT(lastSync) : '—'}</span>
          <span style={{ position: 'relative', fontSize: 12, border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 10px' }}>🔔{notif > 0 && (
            <span style={{ position: 'absolute', top: -8, right: -8, background: '#DC2626', color: '#fff', fontSize: 10, fontWeight: 800, borderRadius: 999, minWidth: 18, height: 18, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{notif}</span>)}
          </span>
          <span style={{ fontSize: 12, textAlign: 'right' }}><strong>{user.name}</strong><span style={{ display: 'block', fontSize: 11, opacity: 0.7 }}>System Admin</span></span>
          <span style={{ fontSize: 11, textAlign: 'right', opacity: 0.85 }}>Step {step + 1} of 8<span style={{ display: 'block', fontWeight: 800, color: '#FF9933', opacity: 1 }}>{STAGES[step].name}</span></span>
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
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, minWidth: 1180 }}>
        {STAGES.map((st, i) => {
          const info = byKey[st.key] || { status: 'NOT STARTED', detail: '' };
          const cur = i === active;
          const tone = stageTone(info.status);
          const dot = { ok: c.ok, warn: c.warn, bad: c.bad, idle: c.faint, accent: '#1D4ED8' }[tone];
          return (
            <span key={st.key} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              {i > 0 && <span style={{ margin: '0 5px', color: c.faint, fontSize: 14 }}>→</span>}
              <button onClick={() => onGo(i)} title={`${st.name} — ${st.hint}${info.detail ? ` · ${info.detail}` : ''}`}
                style={{
                  display: 'flex', gap: s(2), alignItems: 'flex-start', textAlign: 'left',
                  background: cur ? '#EFF6FF' : '#fff', border: `1px solid ${cur ? '#1D4ED8' : c.line}`,
                  borderRadius: 7, padding: '9px 11px', cursor: 'pointer', minWidth: 138,
                  boxShadow: cur ? '0 0 0 3px #DBEAFE' : 'none',
                }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: dot, color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800, flexShrink: 0 }}>
                  {info.status === 'COMPLETED' ? '✓' : (info.status === 'ACTION REQUIRED' || info.status === 'BLOCKED') ? '!' : st.n}
                </span>
                <span>
                  <span style={{ display: 'block', fontSize: 11.5, fontWeight: 800, color: c.ink }}>{st.n}. {st.name}</span>
                  <span style={{ display: 'block', fontSize: 10, fontWeight: 800, color: dot, marginTop: 2 }}>{info.status.replace('_', ' ')}</span>
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
  const svcs: [string, string][] = [
    ['api', 'API'], ['postgresql', 'Database'], ['authentication', 'Authentication'], ['forecast', 'ML / Forecast'],
    ['optimization', 'Optimization'], ['storage', 'Storage'], ['notifications', 'Notifications'],
  ];
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="System status" sub="Live probes taken while loading this workspace.">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: s(2) }}>
          {svcs.map(([k, name]) => {
            const v = data.services[k] || {};
            return (
              <div key={k} style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
                <div style={{ display: 'flex', gap: s(2), alignItems: 'center' }}>
                  <span style={{ fontSize: 12, fontWeight: 800 }}>{name}</span>
                  <span style={{ marginLeft: 'auto' }}><Badge tone={svcTone(v.status || 'UNKNOWN')}>{v.status || 'UNKNOWN'}</Badge></span>
                </div>
                <div style={{ fontSize: 11, color: c.muted, marginTop: 4 }}>Checked {v.last_check ? fmtDT(v.last_check) : '—'}{v.latency_ms != null ? ` · ${v.latency_ms} ms` : ''}</div>
                <div style={{ fontSize: 11.5, marginTop: 2 }}>{v.detail || v.error || ''}</div>
              </div>
            );
          })}
        </div>
      </Card>
      <Card title="Platform counts" sub="Straight from the database.">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: s(2) }}>
          <Stat k="Active users" v={num(data.counts.active_users)} sub={`${num(data.counts.total_users)} total`} />
          <Stat k="Active cycle" v={data.counts.active_cycle ?? '—'} sub={data.counts.active_cycle_state ?? ''} />
          <Stat k="Beneficiary records" v={num(data.counts.beneficiary_records)} />
          <Stat k="FPS records" v={num(data.counts.fps_records)} />
          <Stat k="Warehouses" v={num(data.counts.warehouses)} />
          <Stat k="Vehicles" v={num(data.counts.vehicles)} />
          <Stat k="Latest dataset" v={data.counts.latest_dataset_version ?? '—'} />
          <Stat k="Latest audit event" v={data.counts.latest_audit_event ? data.counts.latest_audit_event.action.replace(/_/g, ' ') : '—'} sub={data.counts.latest_audit_event ? fmtDT(data.counts.latest_audit_event.timestamp) : ''} />
        </div>
      </Card>
    </div>
  );
}

function UsersPanel({ onChanged }: { onChanged: () => void }) {
  const [q, setQ] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [data, setData] = useState<any>(null);
  const [sel, setSel] = useState<any>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<null | { kind: string; label: string }>(null);
  const [reason, setReason] = useState('');
  const [newRole, setNewRole] = useState('');

  const load = useCallback(async () => {
    setErr('');
    try { setData(await adminApi.users({ q: q || undefined, role: role || undefined, status: status || undefined, limit: 100, offset: 0 })); }
    catch (e) { setErr(errMsg(e)); }
  }, [q, role, status]);
  useEffect(() => { load(); }, [load]);

  const open = async (id: string) => {
    setErr(''); setConfirm(null); setReason('');
    try { setSel(await adminApi.user(id)); } catch (e) { setErr(errMsg(e)); }
  };

  const mutate = async () => {
    if (!sel || !confirm) return;
    setBusy(true); setErr('');
    try {
      if (confirm.kind === 'status') await adminApi.updateUser(sel.user.officer_id, { status: sel.user.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE', reason });
      else if (confirm.kind === 'role') await adminApi.updateUser(sel.user.officer_id, { role: newRole, reason });
      else await adminApi.unlockUser(sel.user.officer_id, reason);
      setConfirm(null); setReason('');
      await open(sel.user.officer_id);
      load(); onChanged();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const counts = { total: data?.total ?? 0 };
  const byRole = data?.by_role || [];
  const active = byRole.filter((r: any) => r.status === 'ACTIVE').reduce((a: number, r: any) => a + r.n, 0);
  const inactive = byRole.filter((r: any) => r.status !== 'ACTIVE').reduce((a: number, r: any) => a + r.n, 0);

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: s(2) }}>
        <Stat k="Total users" v={num(counts.total)} />
        <Stat k="Active users" v={num(active)} />
        <Stat k="Inactive users" v={num(inactive)} alert={inactive > 0} />
        {byRole.filter((r: any) => r.status === 'ACTIVE').map((r: any) => <Stat key={r.role} k={r.role} v={num(r.n)} />)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: sel ? '1fr 430px' : '1fr', gap: s(3), alignItems: 'start' }}>
        <Card title={`Officers (${data?.total ?? '…'})`}
          action={<span style={{ display: 'flex', gap: s(2) }}>
            <select value={role} onChange={e => setRole(e.target.value)} style={{ padding: 6, border: `1px solid ${c.lineStrong}`, borderRadius: 5, fontSize: 12 }}>
              <option value="">All roles</option>{(data?.known_roles || []).map((r: string) => <option key={r} value={r}>{r}</option>)}
            </select>
            <select value={status} onChange={e => setStatus(e.target.value)} style={{ padding: 6, border: `1px solid ${c.lineStrong}`, borderRadius: 5, fontSize: 12 }}>
              <option value="">Any status</option><option>ACTIVE</option><option>INACTIVE</option>
            </select>
          </span>}>
          <div style={{ display: 'flex', gap: s(2), marginBottom: s(2) }}>
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search ID / name / employee code"
              style={{ flex: 1, border: `1px solid ${c.lineStrong}`, borderRadius: 6, padding: '8px 10px', fontSize: 13 }} />
          </div>
          {(data?.users || []).map((u: any) => (
            <button key={u.officer_id} onClick={() => open(u.officer_id)}
              style={{ width: '100%', textAlign: 'left', display: 'flex', gap: s(2), alignItems: 'center', background: sel?.user?.officer_id === u.officer_id ? '#EFF6FF' : '#fff', border: 'none', borderBottom: `1px solid ${c.line}`, padding: '9px 4px', cursor: 'pointer', fontSize: 12.5 }}>
              <span style={{ fontFamily: font.mono, fontWeight: 700, fontSize: 11.5 }}>{u.officer_id}</span>
              <span>{u.name} · {u.role}</span>
              {u.auth?.locked && <Badge tone="bad">LOCKED</Badge>}
              {!u.auth?.has_credentials && <Badge tone="warn">NO CREDENTIALS</Badge>}
              <span style={{ marginLeft: 'auto' }}><Badge tone={u.status === 'ACTIVE' ? 'ok' : 'idle'}>{u.status}</Badge></span>
            </button>
          ))}
          {data && data.users.length === 0 && <div style={{ fontSize: 12.5, color: c.muted, padding: s(2) }}>NO RECORDS AVAILABLE.</div>}
        </Card>
        {sel && (
          <Card title={`${sel.user.officer_id}`} action={<button onClick={() => setSel(null)} style={{ ...btnGhost, padding: '4px 10px', fontSize: 12 }}>Close</button>}>
            <KV k="Name" v={<strong>{sel.user.name}</strong>} />
            <KV k="Role" v={`${sel.user.role}${sel.canonical_role ? '' : ' (UNKNOWN — no permissions)'}`} />
            <KV k="Status" v={<Badge tone={sel.user.status === 'ACTIVE' ? 'ok' : 'idle'}>{sel.user.status}</Badge>} />
            <KV k="District" v={sel.user.district ?? '—'} />
            <KV k="Credentials" v={sel.auth.has_credentials ? `set${sel.auth.locked ? ' · LOCKED' : ''}${sel.auth.must_change_password ? ' · must change password' : ''}` : 'NONE — cannot sign in'} />
            <KV k="Failed attempts" v={sel.auth.failed_attempts ?? '—'} />
            <div style={{ ...label, marginTop: s(3), marginBottom: s(1) }}>Permissions ({sel.permissions.length}) — role → allowed actions</div>
            <div style={{ maxHeight: 180, overflowY: 'auto', border: `1px solid ${c.line}`, borderRadius: 6, padding: s(2) }}>
              {sel.permissions.length === 0 && <span style={{ fontSize: 12, color: c.muted }}>No permissions for this role.</span>}
              {sel.permissions.map((p: any) => (
                <div key={p.permission} style={{ display: 'flex', fontSize: 11.5, padding: '2px 0' }}>
                  <span style={{ fontFamily: font.mono }}>{p.permission}</span>
                  <span style={{ marginLeft: 'auto' }}><Badge tone={p.access === 'MANAGE' ? 'warn' : 'idle'}>{p.access}</Badge></span>
                </div>
              ))}
            </div>
            <div style={{ ...label, marginTop: s(3), marginBottom: s(1) }}>Recent audit activity</div>
            {sel.recent_activity.length === 0 && <div style={{ fontSize: 12, color: c.muted }}>NO RECORDS AVAILABLE.</div>}
            {sel.recent_activity.slice(0, 6).map((a: any, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '4px 0', borderBottom: `1px solid ${c.line}` }}>{a.action.replace(/_/g, ' ')} · {a.result} · {fmtDT(a.timestamp)}</div>
            ))}
            <div style={{ ...label, marginTop: s(3), marginBottom: s(1) }}>Actions (audited, reason required)</div>
            <div style={{ display: 'flex', gap: s(2), flexWrap: 'wrap' }}>
              <button onClick={() => setConfirm({ kind: 'status', label: sel.user.status === 'ACTIVE' ? 'DEACTIVATE USER' : 'ACTIVATE USER' })} style={btnGhost}>{sel.user.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}</button>
              {sel.auth.locked && <button onClick={() => setConfirm({ kind: 'unlock', label: 'RESET ACCESS (UNLOCK)' })} style={btnGhost}>Unlock</button>}
              <select value={newRole} onChange={e => setNewRole(e.target.value)} style={{ padding: 6, border: `1px solid ${c.lineStrong}`, borderRadius: 5, fontSize: 12 }}>
                <option value="">Change role…</option>{(data?.known_roles || []).map((r: string) => <option key={r} value={r}>{r}</option>)}
              </select>
              {newRole && <button onClick={() => setConfirm({ kind: 'role', label: `CHANGE ROLE → ${newRole}` })} style={btnGhost}>Apply</button>}
            </div>
            {confirm && (
              <div style={{ background: c.warnBg, border: `1px solid ${c.warnLine}`, borderRadius: 6, padding: s(3), marginTop: s(2) }}>
                <div style={{ fontWeight: 800, fontSize: 13 }}>{confirm.label}</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>Before: <strong>{confirm.kind === 'role' ? sel.user.role : confirm.kind === 'status' ? sel.user.status : 'LOCKED'}</strong> → After: <strong>{confirm.kind === 'role' ? newRole : confirm.kind === 'status' ? (sel.user.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE') : 'UNLOCKED'}</strong></div>
                <div style={{ fontSize: 12, marginTop: 2 }}>Administrator: current admin · Timestamp: backend on confirm</div>
                <input value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason (required)"
                  style={{ width: '100%', padding: 8, marginTop: s(2), border: `1px solid ${c.line}`, borderRadius: 5, fontSize: 13 }} />
                <div style={{ display: 'flex', gap: s(2), marginTop: s(2) }}>
                  <button onClick={() => setConfirm(null)} style={btnGhost}>Cancel</button>
                  <button onClick={mutate} disabled={busy || reason.trim().length < 5} style={busy || reason.trim().length < 5 ? btnDisabled : btn}>{busy ? 'Applying…' : 'Confirm Change'}</button>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}

function DatasetsPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');
  const [openImp, setOpenImp] = useState<string | null>(null);
  useEffect(() => { adminApi.datasets().then(setData).catch(e => setErr(errMsg(e))); }, []);
  if (err) return <div style={{ padding: s(4) }}><Err msg={err} /></div>;
  if (!data) return <Loading what="dataset provenance" />;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="Import history (append-only)" sub={data.note}>
        {data.imports.length === 0 && <div style={{ fontSize: 13, color: c.muted }}>NO RECORDS AVAILABLE.</div>}
        {data.imports.map((imp: any) => (
          <div key={imp.import_id} style={{ border: `1px solid ${c.line}`, borderRadius: 8, padding: s(3), marginBottom: s(2) }}>
            <div style={{ display: 'flex', gap: s(2), alignItems: 'center', flexWrap: 'wrap', fontSize: 12.5 }}>
              <strong style={{ fontFamily: font.mono }}>{imp.import_id}</strong>
              <span>{imp.dataset_name} v{imp.version}</span>
              <span style={{ marginLeft: 'auto' }}><Badge tone={imp.status === 'ACTIVE' ? 'ok' : imp.status === 'REJECTED' || imp.status === 'FAILED' ? 'bad' : 'warn'}>{imp.status}</Badge></span>
            </div>
            <div style={{ fontSize: 12, color: c.body, marginTop: 4 }}>
              {num(imp.total_rows)} rows · by {imp.imported_by} · {fmtDT(imp.created_at)} · sha256 <span style={{ fontFamily: font.mono }}>{String(imp.checksum || '').slice(0, 16)}…</span>
            </div>
            <div style={{ display: 'flex', gap: s(2), marginTop: s(2), flexWrap: 'wrap' }}>
              {(imp.pipeline || []).map((p: any) => <Badge key={p.stage} tone={p.status === 'PASS' ? 'ok' : 'bad'}>{p.stage}: {p.status} ({p.total - p.failed}/{p.total})</Badge>)}
            </div>
            <button onClick={() => setOpenImp(openImp === imp.import_id ? null : imp.import_id)} style={{ ...btnGhost, padding: '4px 10px', fontSize: 12, marginTop: s(2) }}>
              {openImp === imp.import_id ? 'Hide validation checks' : `Inspect ${(imp.checks || []).length} validation checks`}
            </button>
            {openImp === imp.import_id && (
              <div style={{ marginTop: s(2), maxHeight: 260, overflowY: 'auto', border: `1px solid ${c.line}`, borderRadius: 6, padding: s(2) }}>
                {(imp.checks || []).filter((x: any) => x.failed).map((x: any, i: number) => (
                  <div key={i} style={{ fontSize: 12, padding: '4px 0', borderBottom: `1px solid ${c.line}`, color: c.bad }}>
                    ✕ [{x.stage}] {x.table}: {x.check} — {x.detail || x.message || ''}
                  </div>
                ))}
                {(imp.checks || []).filter((x: any) => !x.failed).length > 0 && (
                  <div style={{ fontSize: 12, color: c.ok, marginTop: s(1) }}>✓ {(imp.checks || []).filter((x: any) => !x.failed).length} further checks passed.</div>
                )}
              </div>
            )}
          </div>
        ))}
      </Card>
      <Card title="Live vs imported row counts" sub="Drift indicates post-import writes through the application (expected for operational tables).">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ color: c.muted }}>{['Dataset', 'Imported', 'Live', 'Status'].map(h =>
              <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, textAlign: 'left' }}>{h.toUpperCase()}</th>)}</tr></thead>
            <tbody>
              {Object.entries(data.live_counts).map(([t, n]: any) => {
                const drifted = data.drift && data.drift[t];
                return (
                  <tr key={t} style={{ borderBottom: `1px solid ${c.line}` }}>
                    <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 12 }}>{t}</td>
                    <td style={{ padding: '8px 10px' }}>{drifted ? num(drifted.imported) : (n == null ? '—' : num(n))}</td>
                    <td style={{ padding: '8px 10px', fontWeight: 700 }}>{n == null ? NA : num(n)}</td>
                    <td style={{ padding: '8px 10px' }}>
                      {n == null ? <Badge tone="idle">NOT AVAILABLE</Badge> : drifted ? <Badge tone="warn">WARNING — drift</Badge> : <Badge tone="ok">READY</Badge>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function HealthPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => { adminApi.health().then(setData).catch(e => setErr(errMsg(e))); }, []);
  if (err) return <div style={{ padding: s(4) }}><Err msg={err} /></div>;
  if (!data) return <Loading what="system health" />;
  const names: Record<string, string> = { api: 'API', postgresql: 'PostgreSQL', authentication: 'Authentication', forecast: 'Forecast Service', optimization: 'Optimization Service', storage: 'Storage', notifications: 'Notification Service' };
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title={`Health — ${data.overall}`} sub="Each card is a live probe, not a cached verdict.">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: s(2) }}>
          {Object.entries(data.services).map(([k, v]: any) => (
            <button key={k} onClick={() => setSel(k)} style={{ textAlign: 'left', background: sel === k ? '#EFF6FF' : c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), cursor: 'pointer' }}>
              <div style={{ display: 'flex', gap: s(2), alignItems: 'center' }}>
                <span style={{ fontSize: 12.5, fontWeight: 800 }}>{names[k] || k}</span>
                <span style={{ marginLeft: 'auto' }}><Badge tone={svcTone(v.status)}>{v.status}</Badge></span>
              </div>
              <div style={{ fontSize: 11, color: c.muted, marginTop: 4 }}>Last check {fmtDT(v.last_check)}{v.latency_ms != null ? ` · ${v.latency_ms} ms` : ''}</div>
            </button>
          ))}
        </div>
      </Card>
      {sel && data.services[sel] && (
        <Card title={names[sel] || sel} action={<button onClick={() => setSel(null)} style={{ ...btnGhost, padding: '4px 10px', fontSize: 12 }}>Close</button>}>
          <KV k="Current state" v={<Badge tone={svcTone(data.services[sel].status)}>{data.services[sel].status}</Badge>} />
          <KV k="Last successful check" v={data.services[sel].status === 'ONLINE' ? fmtDT(data.services[sel].last_check) : 'None this probe'} />
          <KV k="Last failure" v={data.services[sel].error ? `${fmtDT(data.services[sel].last_check)} — ${data.services[sel].error}` : 'None recorded (no health history table exists)'} />
          <KV k="Detail" v={data.services[sel].detail || data.services[sel].error || '—'} />
          <KV k="Latency" v={data.services[sel].latency_ms != null ? `${data.services[sel].latency_ms} ms` : NA} />
        </Card>
      )}
      <IntelSection title="Data-quality and system intelligence" subtitle="Missing values, broken references, stale data, model health — advisory only"
        fetch={() => fetchIntel('admin').then(r => r.insights)}
        emptyWhy="No data-quality or system signals." />
    </div>
  );
}

function IntegrationsPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');
  useEffect(() => { adminApi.integrations().then(setData).catch(e => setErr(errMsg(e))); }, []);
  if (err) return <div style={{ padding: s(4) }}><Err msg={err} /></div>;
  if (!data) return <Loading what="integrations" />;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="Integrations" sub="Connected only where the backend confirms it.">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ color: c.muted }}>{['Integration', 'Purpose', 'Connection', 'Last check', 'Configuration'].map(h =>
              <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, textAlign: 'left' }}>{h.toUpperCase()}</th>)}</tr></thead>
            <tbody>
              {(data.integrations || []).map((r: any) => (
                <tr key={r.integration} style={{ borderBottom: `1px solid ${c.line}` }}>
                  <td style={{ padding: '9px 10px', fontWeight: 700 }}>{r.integration}</td>
                  <td style={{ padding: '9px 10px' }}>{r.purpose}</td>
                  <td style={{ padding: '9px 10px' }}><Badge tone={svcTone(r.status)}>{r.status}</Badge></td>
                  <td style={{ padding: '9px 10px' }}>{fmtDT(r.last_check)}</td>
                  <td style={{ padding: '9px 10px', fontSize: 12 }}>{r.detail || r.error || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function SecurityPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');
  useEffect(() => { adminApi.security().then(setData).catch(e => setErr(errMsg(e))); }, []);
  if (err) return <div style={{ padding: s(4) }}><Err msg={err} /></div>;
  if (!data) return <Loading what="security events" />;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: s(2) }}>
        <Stat k="Successful logins (24h)" v={num(data.logins_24h.success)} />
        <Stat k="Failed logins (24h)" v={num(data.logins_24h.failed)} alert={data.logins_24h.failed > 10} />
        <Stat k="Audit chain" v={data.chain.intact ? 'INTACT' : 'BROKEN'} sub={`${data.chain.checked} events checked`} alert={!data.chain.intact} />
      </div>
      <Card title="Audit-chain integrity" sub="Recomputed over every chained event on load.">
        {data.chain.intact
          ? <div style={{ fontSize: 13, color: c.ok, fontWeight: 700 }}>✓ Chain valid · hashes verified · no tampering detected ({data.chain.checked} events).</div>
          : <div style={{ background: c.badBg, border: `1px solid ${c.badLine}`, borderRadius: 6, padding: s(3) }}>
            <div style={{ fontWeight: 800, color: c.bad }}>✕ INTEGRITY FAILURE</div>
            {data.chain.broken.slice(0, 5).map((id: string) => <div key={id} style={{ fontSize: 12, fontFamily: font.mono, marginTop: 4 }}>Affected event: {id}</div>)}
          </div>}
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: s(3) }}>
        <Card title={`Failed authentication (${data.recent_failures.length} recent)`}>
          {data.recent_failures.length === 0 && <div style={{ fontSize: 12.5, color: c.muted }}>NO RECORDS AVAILABLE.</div>}
          {data.recent_failures.map((e: any, i: number) => (
            <div key={i} style={{ fontSize: 12.5, padding: '7px 0', borderBottom: `1px solid ${c.line}` }}>
              <strong>{e.actor_user_id}</strong> ({e.actor_role}) · {e.action.replace(/_/g, ' ')} · {fmtDT(e.timestamp)}
              <div style={{ color: c.muted, fontSize: 11.5 }}>{e.reason || ''} · IP/device: DATA UNAVAILABLE (not recorded)</div>
            </div>
          ))}
        </Card>
        <Card title={`Role & access changes (${data.role_changes.length})`}>
          {data.role_changes.length === 0 && <div style={{ fontSize: 12.5, color: c.muted }}>NO RECORDS AVAILABLE — no account changes recorded.</div>}
          {data.role_changes.map((e: any) => (
            <div key={e.audit_event_id} style={{ border: `1px solid ${c.line}`, borderLeft: `4px solid ${c.warn}`, borderRadius: 6, padding: s(2), marginBottom: s(2), fontSize: 12.5 }}>
              <div><strong>{e.actor_user_id}</strong> · {e.audit_event_id && ''}{fmtDT(e.timestamp)}</div>
              <div>User: <span style={{ fontFamily: font.mono }}>{e.entity_id}</span></div>
              <div>Before: <strong>{e.before_state ?? '—'}</strong> → After: <strong>{e.after_state ?? '—'}</strong></div>
              <div style={{ color: c.muted }}>Reason: {e.reason || '—'} · Result: SUCCESS</div>
            </div>
          ))}
        </Card>
      </div>
      <Card title="System mutations (24h)" sub="Successful non-login actions.">
        {data.mutations_24h.length === 0 && <div style={{ fontSize: 12.5, color: c.muted }}>NO RECORDS AVAILABLE.</div>}
        <div style={{ display: 'flex', gap: s(2), flexWrap: 'wrap' }}>
          {data.mutations_24h.map((m: any) => <span key={m.action} style={{ fontSize: 12, background: c.raised, border: `1px solid ${c.line}`, borderRadius: 999, padding: '4px 10px' }}>{m.action.replace(/_/g, ' ')} × {m.n}</span>)}
        </div>
      </Card>
    </div>
  );
}

function ConfigPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');
  useEffect(() => { adminApi.configuration().then(setData).catch(e => setErr(errMsg(e))); }, []);
  if (err) return <div style={{ padding: s(4) }}><Err msg={err} /></div>;
  if (!data) return <Loading what="configuration" />;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Card title="Effective configuration" sub={data.note}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ color: c.muted }}>{['Category', 'Setting', 'Value', 'Detail'].map(h =>
              <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, textAlign: 'left' }}>{h.toUpperCase()}</th>)}</tr></thead>
            <tbody>
              {(data.entries || []).map((r: any, i: number) => (
                <tr key={i} style={{ borderBottom: `1px solid ${c.line}` }}>
                  <td style={{ padding: '8px 10px', color: c.muted }}>{r.category}</td>
                  <td style={{ padding: '8px 10px', fontWeight: 700 }}>{r.setting}</td>
                  <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 12 }}>{r.value}</td>
                  <td style={{ padding: '8px 10px', fontSize: 12 }}>{r.detail} <Badge tone="idle">READ-ONLY</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function FinalPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');
  useEffect(() => { adminApi.final().then(setData).catch(e => setErr(errMsg(e))); }, []);
  if (err) return <div style={{ padding: s(4) }}><Err msg={err} /></div>;
  if (!data) return <Loading what="final status" />;
  const vTone = data.verdict === 'SYSTEM READY' ? 'ok' as const : data.verdict === 'SYSTEM BLOCKED' ? 'bad' as const : 'warn' as const;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ background: '#0F2542', color: '#fff', borderRadius: 8, padding: s(4), display: 'flex', gap: s(3), alignItems: 'center', flexWrap: 'wrap' }}>
        <div><div style={label}>System verdict — computed from evidence below</div>
          <div style={{ marginTop: 6 }}><Badge tone={vTone}>{data.verdict}</Badge></div></div>
      </div>
      <Card title="Readiness categories">
        {data.readiness.map((r: any) => (
          <div key={r.category} style={{ display: 'grid', gridTemplateColumns: '200px 130px 1fr', gap: s(2), alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${c.line}`, fontSize: 12.5 }}>
            <span style={{ fontWeight: 600 }}>{r.category}</span>
            <span><Badge tone={svcTone(r.status)}>{r.status}</Badge></span>
            <span style={{ color: c.muted }}>{r.evidence}</span>
          </div>
        ))}
      </Card>
      <AIAssistant />
    </div>
  );
}

// ---------------------------------------------------------------- main shell
export default function AdminDataTrust() {
  const { user, logout } = useAuth();
  const [step, setStep] = useState(loadStep());
  const [stages, setStages] = useState<any[]>([]);
  const [err, setErr] = useState('');
  const [ov, setOv] = useState<any>(null);
  const [usersTick, setUsersTick] = useState(0);

  const loadStages = useCallback(async () => {
    try { setStages((await adminApi.stages()).stages); } catch (e) { setErr(errMsg(e)); }
  }, []);
  useEffect(() => {
    adminApi.overview().then(setOv).catch(e => setErr(errMsg(e)));
    loadStages();
  }, [loadStages, usersTick]);

  const go = (i: number) => {
    setStep(i);
    try { localStorage.setItem(STEP_KEY, String(i)); } catch {}
  };

  if (!user) return null;
  const attention = stages.filter(x => x.status === 'ACTION REQUIRED' || x.status === 'BLOCKED').length;
  const counts = ov?.counts;

  return (
    <div style={{ minHeight: '100vh', background: '#F1F5F9', fontFamily: font.ui }}>
      <TopHeader user={user} logout={logout} cycle={counts?.active_cycle} cycleState={counts?.active_cycle_state}
        backend={ov ? (Object.values(ov.services).every((v: any) => v.status === 'ONLINE') ? 'ONLINE' : 'DEGRADED') : undefined}
        lastSync={ov?.last_sync} notif={attention} step={step} />
      <WorkflowBar active={step} stages={stages} onGo={go} />
      {err && <div style={{ margin: `${s(2)} ${s(4)}`, background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(2), borderRadius: 6, fontSize: 12.5 }}>{err}</div>}
      <main>
        {step === 0 && (ov ? <OverviewPanel data={ov} /> : <Loading what="system overview" />)}
        {step === 1 && <UsersPanel onChanged={() => { setUsersTick(t => t + 1); }} />}
        {step === 2 && <DatasetsPanel />}
        {step === 3 && <HealthPanel />}
        {step === 4 && <IntegrationsPanel />}
        {step === 5 && <SecurityPanel />}
        {step === 6 && <ConfigPanel />}
        {step === 7 && <FinalPanel />}
      </main>
      <footer style={{ padding: s(4), textAlign: 'center', fontSize: 11, color: c.faint }}>
        DemandSYNC · System administration is backend-authorized and audited · Secrets are never exposed.
      </footer>
    </div>
  );
}
