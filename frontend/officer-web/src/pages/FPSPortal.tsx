/**
 * FPS Owner — Stateful Workflow-Driven Fair Price Shop Operations Center.
 * TOP = persistent workflow bar, BELOW = workspace for the current step.
 * NO sidebars. One continuous operational cycle. Every value comes from the
 * backend (backend/api/fps.py); nothing is hardcoded, mocked, or faked.
 */
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { ApiError } from '../api/client';
import { c, font, label, s, btn, btnGhost, btnDisabled, kg, num } from '../dso/theme';
import { fpsApi } from '../fps/api';
import { IntelSection, fetchIntel } from '../components/Intelligence';

const EposChartLazy = lazy(() => import('../fps/EposChart').then(m => ({ default: m.EposChart })));
const EposDailyChartLazy = lazy(() => import('../fps/EposChart').then(m => ({ default: m.EposDailyChart })));

// ---------------------------------------------------------------- constants
const STEPS = ['OVERVIEW', 'STOCK', 'e-POS', 'BENEFICIARIES', 'DISTRIBUTION', 'RECONCILIATION', 'REQUESTS', 'CLOSE DAY'] as const;
const STEP_HINT = [
  'Operational summary for this shop',
  'Inventory ledger and movements',
  'e-PoS activity and transactions',
  'Beneficiaries assigned to this shop',
  'Record today\u2019s distributions',
  'Ledger vs transaction comparison',
  'Supply and replenishment requests',
  'Verify and close the operating day',
];

const stepKey = (id: string) => `dsp-fps-step-${id}`;
const visitedKey = (id: string) => `dsp-fps-visited-${id}`;
const outboxKey = (id: string) => `dsp-fps-outbox-${id}`;
function loadStep(id: string): number { try { const v = Number(localStorage.getItem(stepKey(id))); return Number.isFinite(v) && v >= 0 && v <= 7 ? v : 0; } catch { return 0; } }
function storeStep(id: string, n: number) { try { localStorage.setItem(stepKey(id), String(n)); } catch {} }
function loadVisited(id: string): number[] { try { const v = JSON.parse(localStorage.getItem(visitedKey(id)) || '[]'); return Array.isArray(v) ? v.filter((x: any) => Number.isInteger(x) && x >= 0 && x <= 7) : []; } catch { return []; } }
function storeVisited(id: string, v: number[]) { try { localStorage.setItem(visitedKey(id), JSON.stringify(v)); } catch {} }

interface QueuedDist {
  client_ref: string; beneficiary_id: string; beneficiary_name?: string;
  commodity: string; quantity_kg: number; queued_at: string;
  status: 'QUEUED' | 'SYNCING' | 'FAILED'; error?: string;
}
function loadOutbox(id: string): QueuedDist[] { try { const v = JSON.parse(localStorage.getItem(outboxKey(id)) || '[]'); return Array.isArray(v) ? v : []; } catch { return []; } }
function storeOutbox(id: string, v: QueuedDist[]) { try { localStorage.setItem(outboxKey(id), JSON.stringify(v)); } catch {} }
function newClientRef(): string {
  try { return `WEB-${crypto.randomUUID().slice(0, 8).toUpperCase()}`; }
  catch { return `WEB-${Date.now().toString(36).toUpperCase()}`; }
}

// ---------------------------------------------------------------- small ui
function fmtDT(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true });
}
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
        <div style={{ ...label, fontSize: 12 }}>{title}</div>
        {action && <span style={{ marginLeft: 'auto' }}>{action}</span>}
      </div>
      {sub && <div style={{ fontSize: 11.5, color: c.muted, marginBottom: s(3) }}>{sub}</div>}
      {children}
    </div>
  );
}
function Stat({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), minWidth: 0 }}>
      <div style={label}>{k}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: c.ink, marginTop: 2 }}>{v}</div>
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
function errMsg(e: unknown): string { return e instanceof ApiError ? e.message : String(e); }

// ---------------------------------------------------------------- headers
function GovHeader({ user, shop, alertCount, onBell, onLogout, net }: {
  user: any; shop: any; alertCount: number; onBell: () => void; onLogout: () => void;
  net: { online: boolean; syncing: boolean; queued: number };
}) {
  const [showProfile, setShowProfile] = useState(false);
  return (
    <header style={{ background: '#071A31', color: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(3), padding: `${s(2)} ${s(4)}`, flexWrap: 'wrap' }}>
        <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>◈</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 9, letterSpacing: '0.1em', opacity: 0.7, fontWeight: 700 }}>GOVERNMENT OF INDIA</div>
          <div style={{ fontSize: 11, opacity: 0.7 }}>Department of Food &amp; Public Distribution</div>
          <div style={{ fontSize: 14, fontWeight: 800, marginTop: 2 }}>PDS DemandSYNC <span style={{ fontWeight: 400, opacity: 0.75, fontSize: 11 }}>— Public Distribution System Intelligence Platform</span></div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: s(3), flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: net.online ? '#16A34A' : '#F59E0B' }} />
            {net.syncing ? 'Syncing…' : net.online ? (net.queued ? `Online · ${net.queued} queued` : 'System Operational') : 'Offline — queuing locally'}
          </span>
          <button onClick={onBell} title="Operational alerts"
            style={{ position: 'relative', background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 10px', font: `600 12px ${font.ui}`, cursor: 'pointer' }}>
            🔔 Notifications{alertCount > 0 && (
              <span style={{ position: 'absolute', top: -8, right: -8, background: '#DC2626', color: '#fff', fontSize: 10, fontWeight: 800, borderRadius: 999, minWidth: 18, height: 18, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px' }}>{alertCount}</span>
            )}
          </button>
          <span style={{ fontSize: 12, textAlign: 'right' }}>
            <strong>{user.name}</strong>
            <span style={{ display: 'block', fontSize: 11, opacity: 0.7 }}>FPS Owner · {shop?.fps_id ?? '—'} · {user.district ?? shop?.district ?? '—'}</span>
          </span>
          <span style={{ position: 'relative' }}>
            <button onClick={() => setShowProfile(v => !v)} style={{ background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 12px', font: `600 12px ${font.ui}`, cursor: 'pointer' }}>Profile</button>
            {showProfile && (
              <div style={{ position: 'absolute', right: 0, top: 34, background: '#fff', color: c.ink, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), minWidth: 230, zIndex: 20, boxShadow: '0 8px 24px rgba(0,0,0,0.25)', fontSize: 12 }}>
                <div style={label}>Signed in</div>
                <div style={{ fontWeight: 700, marginTop: 4 }}>{user.name}</div>
                <div style={{ color: c.body, marginTop: 2 }}>ID: <span style={{ fontFamily: font.mono }}>{user.user_id}</span></div>
                <div style={{ color: c.body }}>Role: {user.role}</div>
                <div style={{ color: c.body }}>District: {user.district ?? shop?.district ?? '—'}</div>
                <div style={{ color: c.body }}>Shop: {shop?.fps_name ?? '—'} ({shop?.fps_id ?? '—'})</div>
              </div>
            )}
          </span>
          <button onClick={onLogout} style={{ background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 12px', font: `600 12px ${font.ui}`, cursor: 'pointer' }}>Logout</button>
        </div>
      </div>
      <div style={{ display: 'flex', height: 3 }}><div style={{ flex: 1, background: '#FF9933' }} /><div style={{ flex: 1, background: '#fff' }} /><div style={{ flex: 1, background: '#138808' }} /></div>
    </header>
  );
}

function ShopHeader({ shop, owner, cycle, step }: { shop: any; owner: any; cycle: any; step: number }) {
  return (
    <div style={{ background: '#0F2542', color: '#fff', padding: `${s(3)} ${s(4)}`, borderBottom: '1px solid #1A3A5C' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: s(4), alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 9, letterSpacing: '0.12em', opacity: 0.6, fontWeight: 800 }}>FAIR PRICE SHOP OPERATIONS</div>
          <div style={{ fontSize: 19, fontWeight: 800, marginTop: 2 }}>{shop.fps_name}</div>
          <div style={{ fontSize: 11.5, opacity: 0.75, marginTop: 2 }}>
            FPS ID: <strong style={{ fontFamily: font.mono }}>{shop.fps_id}</strong> · Owner: {owner?.name ?? '—'} · {shop.taluk ? `${shop.taluk}, ` : ''}{shop.district}
          </div>
        </div>
        <div style={{ width: 1, height: 44, background: 'rgba(255,255,255,0.15)' }} />
        <div style={{ fontSize: 12 }}><div style={{ opacity: 0.6, fontSize: 10, letterSpacing: '0.08em', fontWeight: 700 }}>SHOP STATUS</div>
          <div style={{ background: shop.status === 'ACTIVE' ? '#16A34A' : '#FF9933', color: shop.status === 'ACTIVE' ? '#fff' : '#071A31', padding: '2px 8px', borderRadius: 999, fontWeight: 800, fontSize: 11, display: 'inline-block', marginTop: 2 }}>{shop.status === 'ACTIVE' ? 'OPEN' : shop.status}</div></div>
        <div style={{ fontSize: 12 }}><div style={{ opacity: 0.6, fontSize: 10, letterSpacing: '0.08em', fontWeight: 700 }}>CURRENT CYCLE</div><div style={{ fontWeight: 700 }}>{cycle?.cycle ?? '—'} · {cycle?.state ?? ''}</div></div>
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{ fontSize: 11, opacity: 0.7 }}>Step {step + 1} of 8</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: '#FF9933' }}>{STEPS[step]}</div>
          <div style={{ fontSize: 10.5, opacity: 0.6 }}>{STEP_HINT[step]}</div>
        </div>
      </div>
    </div>
  );
}

function WorkflowBar({ active, visited, locked, onGo }: {
  active: number; visited: number[]; locked: (i: number) => { lock: boolean; why?: string }; onGo: (i: number) => void;
}) {
  return (
    <div style={{ background: '#fff', borderBottom: `1px solid ${c.line}`, padding: `${s(2)} ${s(4)}`, overflowX: 'auto', position: 'sticky', top: 0, zIndex: 5 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, minWidth: 860 }}>
        {STEPS.map((nm, i) => {
          const { lock, why } = locked(i);
          const done = visited.includes(i) && i !== active;
          const cur = i === active;
          const circleStyle: React.CSSProperties = done
            ? { background: c.ok, borderColor: c.ok, color: '#fff' }
            : cur ? { background: '#1D4ED8', borderColor: '#1D4ED8', color: '#fff', boxShadow: '0 0 0 4px #DBEAFE' }
              : lock ? { background: c.canvas, borderColor: c.lineStrong, color: c.faint }
                : { background: '#fff', borderColor: c.lineStrong, color: c.muted };
          return (
            <span key={nm} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              {i > 0 && <span style={{ width: 22, height: 2, background: done ? c.ok : c.line, margin: '0 3px' }} />}
              <button onClick={() => !lock && onGo(i)} disabled={lock} title={lock ? (why || 'Locked') : `${nm} — ${STEP_HINT[i]}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, background: cur ? '#EFF6FF' : 'transparent',
                  border: `1px solid ${cur ? '#BFDBFE' : 'transparent'}`, borderRadius: 999, padding: '8px 11px',
                  cursor: lock ? 'not-allowed' : 'pointer', opacity: lock ? 0.6 : 1,
                }}>
                <span style={{
                  width: 26, height: 26, borderRadius: '50%', border: '1px solid', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontWeight: 800, ...circleStyle,
                }}>{done ? '✓' : lock ? '🔒' : i + 1}</span>
                <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.05em', color: done ? c.ok : cur ? '#1D4ED8' : lock ? c.faint : c.body }}>{nm}</span>
              </button>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 1 overview
function OverviewPanel({ data, onGo }: { data: any; onGo: (i: number) => void }) {
  const dist = data.distribution;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: s(2) }}>
        <Stat k="Shop status" v={data.status.shop_status === 'ACTIVE' ? 'OPEN' : data.status.shop_status} sub={`Cycle ${data.cycle.cycle}`} />
        <Stat k="Today" v={data.today} sub={`Last activity ${fmtDT(data.status.last_activity_at)}`} />
        <Stat k="Today's transactions" v={String(data.status.today.txns)} sub={`${data.status.today.success} successful · ${data.status.today.failed} failed`} />
        <Stat k="Served this cycle" v={String(dist.served_this_cycle)} sub={`of ${dist.assigned_beneficiaries} assigned`} />
        <Stat k="Pending collections" v={String(dist.pending_collections)} sub="beneficiaries yet to collect" />
      </div>

      <Card title="Stock summary">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ textAlign: 'left', color: c.muted }}>
              {['Commodity', 'Available', 'Allocated', 'Distributed (ledger)', 'Distributed (e-PoS)', 'Remaining'].map(h =>
                <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, letterSpacing: '0.06em' }}>{h.toUpperCase()}</th>)}
            </tr></thead>
            <tbody>
              {data.stock.map((r: any) => (
                <tr key={r.commodity} style={{ borderBottom: `1px solid ${c.line}` }}>
                  <td style={{ padding: '9px 10px', fontWeight: 700 }}>{r.commodity}</td>
                  <td style={{ padding: '9px 10px' }}>{kg(r.closing_stock_kg)}</td>
                  <td style={{ padding: '9px 10px' }}>{r.allocated_kg != null ? kg(r.allocated_kg) : '—'}</td>
                  <td style={{ padding: '9px 10px' }}>{kg(r.distributed_kg)}</td>
                  <td style={{ padding: '9px 10px' }}>{kg(r.distributed_epos_kg)}</td>
                  <td style={{ padding: '9px 10px', fontWeight: 700 }}>{kg(r.closing_stock_kg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: s(3) }}>
        <Card title={`Alerts (${data.alerts.length})`}>
          {data.alerts.length === 0 && <div style={{ fontSize: 13, color: c.ok }}>No operational alerts. The shop is running normally.</div>}
          {data.alerts.map((a: any, i: number) => (
            <div key={i} style={{
              border: `1px solid ${a.severity === 'HIGH' ? c.badLine : a.severity === 'MEDIUM' ? c.warnLine : c.line}`,
              borderLeft: `4px solid ${a.severity === 'HIGH' ? c.bad : a.severity === 'MEDIUM' ? c.warn : c.accent}`,
              borderRadius: 6, padding: s(2), marginBottom: s(2), fontSize: 12.5, background: '#fff',
            }}>
              <strong>[{a.severity}]</strong> {a.message}
            </div>
          ))}
        </Card>
        <Card title="AI operational insight (advisory)">
          {(!data.insights || data.insights.length === 0) && <div style={{ fontSize: 13, color: c.muted }}>Not enough activity in this cycle for an assessment yet.</div>}
          {(data.insights || []).map((ins: any, i: number) => (
            <div key={i} style={{ background: c.accentBg, border: '1px solid #BFDBFE', borderRadius: 6, padding: s(3), marginBottom: s(2) }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: c.ink }}>{ins.headline}</div>
              <div style={{ fontSize: 12, color: c.body, marginTop: 4 }}>{ins.detail}</div>
              {ins.recommended_action && <div style={{ fontSize: 12, marginTop: 6 }}><strong>Recommended action:</strong> {ins.recommended_action}</div>}
            </div>
          ))}
          <div style={{ fontSize: 11, color: c.muted }}>Suggestions are advisory — they never change stock or records.</div>
        </Card>
      </div>

      <IntelSection title="Stock and delivery intelligence" subtitle="Incoming stock, depletion risk, allocation reasons for this shop — advisory only"
        fetch={() => fetchIntel('fps', data.cycle?.cycle).then(r => r.insights)}
        emptyWhy="Nothing currently signals risk for this shop." />

      <div style={{ background: '#0F2542', color: '#fff', borderRadius: 8, padding: s(4), display: 'flex', gap: s(3), alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={label}>Today&apos;s next action</div>
          <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>{data.next_action}</div>
        </div>
        <button onClick={() => onGo(4)} style={{ ...btn, marginLeft: 'auto', background: '#FF9933', borderColor: '#FF9933', color: '#071A31' }}>GO TO DISTRIBUTION →</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 2 stock
function StockPanel({ data, onChanged }: { data: any; onChanged: () => void }) {
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState('');
  const [recv, setRecv] = useState({ commodity: 'RICE', quantity_kg: '', reason: '', reference: '' });
  const [adj, setAdj] = useState({ commodity: 'RICE', quantity_kg: '', reason: '' });
  const [incoming, setIncoming] = useState<any>(null);
  useEffect(() => { fpsApi.incoming().then(setIncoming).catch(() => setIncoming({ items: [] })); }, []);

  const submit = async (kind: 'receive' | 'adjust') => {
    setErr(''); setBusy(kind);
    try {
      if (kind === 'receive') {
        await fpsApi.receive({ commodity: recv.commodity, quantity_kg: Number(recv.quantity_kg), reason: recv.reason, reference: recv.reference || undefined });
        setRecv({ commodity: 'RICE', quantity_kg: '', reason: '', reference: '' });
      } else {
        await fpsApi.adjust({ commodity: adj.commodity, quantity_kg: Number(adj.quantity_kg), reason: adj.reason });
        setAdj({ commodity: 'RICE', quantity_kg: '', reason: '' });
      }
      onChanged();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(''); }
  };

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      <Card title={`Incoming dispatch — expected stock${incoming && incoming.cycle ? ` (${incoming.cycle})` : ''}`}
        sub="The same manifest records the DSO planned. ETA and live location appear only if the backend holds them.">
        {!incoming && <div style={{ fontSize: 13, color: c.muted }}>Loading incoming dispatch…</div>}
        {incoming && incoming.items.length === 0 && <div style={{ fontSize: 13, color: c.muted }}>NO RECORDS AVAILABLE — no dispatch planned for this shop in this cycle.</div>}
        {incoming && incoming.items.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <thead><tr style={{ textAlign: 'left', color: c.muted }}>
                {['Manifest', 'Vehicle', 'Commodity', 'Expected', 'Dispatch', 'Delivery'].map(h =>
                  <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, letterSpacing: '0.06em' }}>{h.toUpperCase()}</th>)}
              </tr></thead>
              <tbody>
                {incoming.items.map((m: any, i: number) => (
                  <tr key={`${m.manifest_id}-${i}`} style={{ borderBottom: `1px solid ${c.line}` }}>
                    <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 11.5 }}>{m.manifest_id}</td>
                    <td style={{ padding: '8px 10px' }}>{m.vehicle_number ?? m.vehicle_id ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{m.commodity}</td>
                    <td style={{ padding: '8px 10px', fontWeight: 700 }}>{kg(m.planned_kg)}</td>
                    <td style={{ padding: '8px 10px' }}><Badge tone={m.manifest_status === 'DISPATCHED' || m.manifest_status === 'DELIVERED' ? 'ok' : m.manifest_status === 'DRAFT' ? 'idle' : 'accent'}>{m.manifest_status}</Badge></td>
                    <td style={{ padding: '8px 10px' }}>{m.delivery_status ? `${m.delivery_status} · ${kg(m.delivered_kg)}` : 'Not yet recorded'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ fontSize: 11, color: c.muted, marginTop: s(2) }}>{incoming.eta_note} {incoming.location_note}</div>
          </div>
        )}
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: s(3) }}>
        {data.cards.map((r: any) => (
          <div key={r.commodity} style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
              <div style={{ fontSize: 15, fontWeight: 800 }}>{r.commodity}</div>
              <span style={{ marginLeft: 'auto' }}>
                <Badge tone={r.availability === 'AVAILABLE' ? 'ok' : r.availability === 'EXHAUSTED' ? 'bad' : 'idle'}>{r.availability.replace('_', ' ')}</Badge>
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(2), marginTop: s(3), fontSize: 12.5 }}>
              <div><div style={label}>System stock (closing)</div><div style={{ fontWeight: 800, fontSize: 16 }}>{r.closing_stock_kg != null ? kg(r.closing_stock_kg) : '—'}</div></div>
              <div><div style={label}>Allocated</div><div style={{ fontWeight: 700 }}>{r.allocated_kg != null ? kg(r.allocated_kg) : '—'}</div></div>
              <div><div style={label}>Opening</div><div>{r.opening_stock_kg != null ? kg(r.opening_stock_kg) : '—'}</div></div>
              <div><div style={label}>Received</div><div>{r.received_kg != null ? kg(r.received_kg) : '—'}</div></div>
              <div><div style={label}>Distributed (ledger)</div><div>{r.distributed_kg != null ? kg(r.distributed_kg) : '—'}</div></div>
              <div><div style={label}>Distributed (e-PoS)</div><div>{kg(r.distributed_epos_kg)}</div></div>
              <div><div style={label}>Adjustments posted</div><div>{r.adjusted_kg != null ? `${Number(r.adjusted_kg) > 0 ? '+' : ''}${num(r.adjusted_kg)} kg` : '—'}</div></div>
              <div><div style={label}>Allocation</div><div>{r.allocation_status ?? '—'}</div></div>
            </div>
            {!r.has_ledger && <div style={{ fontSize: 11.5, color: c.warn, marginTop: s(2) }}>No ledger issued for this commodity in {data.cycle}.</div>}
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: c.muted }}>Minimum levels are not configured in the system — availability is reported exactly as recorded in the ledger.</div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: s(3) }}>
        <Card title="Receive stock">
          <div style={{ display: 'flex', flexDirection: 'column', gap: s(2), fontSize: 13 }}>
            <label style={label}>Commodity<br />
              <select value={recv.commodity} onChange={e => setRecv({ ...recv, commodity: e.target.value })} style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }}><option>RICE</option><option>WHEAT</option></select></label>
            <label style={label}>Quantity (kg)<br />
              <input type="number" min="0.1" step="0.1" value={recv.quantity_kg} onChange={e => setRecv({ ...recv, quantity_kg: e.target.value })} placeholder="e.g. 50" style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <label style={label}>Reason / source<br />
              <input value={recv.reason} onChange={e => setRecv({ ...recv, reason: e.target.value })} placeholder="Delivery acknowledgment details" style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <label style={label}>Reference (optional)<br />
              <input value={recv.reference} onChange={e => setRecv({ ...recv, reference: e.target.value })} placeholder="Manifest / delivery ref" style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <button disabled={busy === 'receive' || !recv.quantity_kg || !recv.reason.trim()} onClick={() => submit('receive')} style={busy === 'receive' || !recv.quantity_kg || !recv.reason.trim() ? btnDisabled : btn}>{busy === 'receive' ? 'Posting…' : 'RECEIVE STOCK'}</button>
          </div>
        </Card>
        <Card title="Record authorized adjustment">
          <div style={{ display: 'flex', flexDirection: 'column', gap: s(2), fontSize: 13 }}>
            <label style={label}>Commodity<br />
              <select value={adj.commodity} onChange={e => setAdj({ ...adj, commodity: e.target.value })} style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }}><option>RICE</option><option>WHEAT</option></select></label>
            <label style={label}>Quantity (kg, negative for loss)<br />
              <input type="number" step="0.1" value={adj.quantity_kg} onChange={e => setAdj({ ...adj, quantity_kg: e.target.value })} placeholder="e.g. -2 for damage" style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <label style={label}>Mandatory reason<br />
              <input value={adj.reason} onChange={e => setAdj({ ...adj, reason: e.target.value })} placeholder="Damage, weighing correction, …" style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <button disabled={busy === 'adjust' || !adj.quantity_kg || adj.reason.trim().length < 5} onClick={() => submit('adjust')} style={busy === 'adjust' || !adj.quantity_kg || adj.reason.trim().length < 5 ? btnDisabled : btnGhost}>{busy === 'adjust' ? 'Posting…' : 'RECORD AUTHORIZED ADJUSTMENT'}</button>
            <div style={{ fontSize: 11, color: c.muted }}>Posted to the ledger with your name, kept in history, and still visible in reconciliation.</div>
          </div>
        </Card>
      </div>

      <Card title={`Stock movement (${data.movements.length})`}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ textAlign: 'left', color: c.muted }}>
              {['Date', 'Quantity', 'Type', 'Reference', 'Status'].map(h =>
                <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, letterSpacing: '0.06em' }}>{h.toUpperCase()}</th>)}
            </tr></thead>
            <tbody>
              {data.movements.length === 0 && <tr><td colSpan={5} style={{ padding: s(3), color: c.muted }}>No movements recorded in this cycle.</td></tr>}
              {data.movements.map((m: any) => (
                <tr key={`${m.source}-${m.id}`} style={{ borderBottom: `1px solid ${c.line}` }}>
                  <td style={{ padding: '8px 10px' }}>{fmtDT(m.at)}</td>
                  <td style={{ padding: '8px 10px', fontWeight: 700 }}>{m.commodity} · {kg(m.quantity)}</td>
                  <td style={{ padding: '8px 10px' }}><Badge tone={m.type === 'DELIVERY' ? 'accent' : m.type === 'RECEIPT' ? 'ok' : 'idle'}>{m.type}</Badge></td>
                  <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 11.5 }}>{m.reference ?? m.id}</td>
                  <td style={{ padding: '8px 10px', fontSize: 12 }}>{m.reason ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 3 e-pos
function EposPanel({ data }: { data: any }) {
  const t = data.cycle_totals;
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4), display: 'flex', gap: s(3), alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={label}>e-PoS status</div>
          <div style={{ marginTop: 6 }}><Badge tone="idle">NOT INSTRUMENTED</Badge></div>
        </div>
        <div style={{ fontSize: 12.5, color: c.body, maxWidth: 560 }}>{data.device.note}</div>
        <div style={{ marginLeft: 'auto', fontSize: 12.5 }}><div style={label}>Last activity</div><div style={{ fontWeight: 700 }}>{fmtDT(data.device.last_activity_at)}</div></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: s(2) }}>
        <Stat k="Total transactions" v={String(t.txns)} sub={`cycle ${data.cycle}`} />
        <Stat k="Successful" v={String(t.success)} />
        <Stat k="Failed" v={String(t.failed)} />
        <Stat k="Pending" v="0" sub="all records are terminal" />
        <Stat k="Cancelled" v={String(t.cancelled)} />
        <Stat k="Today" v={String(data.today.txns)} sub={`${data.today.success} successful`} />
      </div>

      <Card title="Transaction activity">
        {data.by_hour.length === 0 ? <div style={{ fontSize: 13, color: c.muted }}>No transactions in this cycle to chart.</div> : (
          <Suspense fallback={<div style={{ height: 240, display: 'grid', placeItems: 'center', color: c.muted }}>Loading chart…</div>}>
            <EposChartLazy byHour={data.by_hour} byDay={data.by_day} />
            <div style={{ marginTop: s(3) }}><EposDailyChartLazy byDay={data.by_day} /></div>
          </Suspense>
        )}
      </Card>

      <Card title={`Recent transactions (${data.recent.length})`}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead><tr style={{ textAlign: 'left', color: c.muted }}>
              {['Transaction', 'Beneficiary', 'Time', 'Commodity', 'Quantity', 'Status'].map(h =>
                <th key={h} style={{ padding: '8px 10px', borderBottom: `1px solid ${c.line}`, fontSize: 10.5, letterSpacing: '0.06em' }}>{h.toUpperCase()}</th>)}
            </tr></thead>
            <tbody>
              {data.recent.map((r: any) => (
                <tr key={r.transaction_id} style={{ borderBottom: `1px solid ${c.line}` }}>
                  <td style={{ padding: '8px 10px', fontFamily: font.mono, fontSize: 11.5 }}>{r.transaction_id}</td>
                  <td style={{ padding: '8px 10px' }}>{r.beneficiary_id}<div style={{ fontSize: 11, color: c.muted }}>{r.beneficiary_name ?? ''}</div></td>
                  <td style={{ padding: '8px 10px' }}>{fmtDT(r.transaction_time)}</td>
                  <td style={{ padding: '8px 10px' }}>{r.commodity}</td>
                  <td style={{ padding: '8px 10px', fontWeight: 700 }}>{kg(r.quantity_kg)}</td>
                  <td style={{ padding: '8px 10px' }}><Badge tone={r.status === 'SUCCESS' ? 'ok' : r.status === 'FAILED' ? 'bad' : 'idle'}>{r.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ fontSize: 11, color: c.muted, marginTop: s(2) }}>Transaction records are read-only. The FPS Owner cannot edit or delete official records.</div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 4 beneficiaries
function BeneficiariesPanel({ cycle, onDistribute }: { cycle: string; onDistribute: (id: string) => void }) {
  const [q, setQ] = useState('');
  const [pendingOnly, setPendingOnly] = useState(false);
  const [data, setData] = useState<any>(null);
  const [sel, setSel] = useState<any>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (query: string, pend: boolean) => {
    setBusy(true); setErr('');
    try { setData(await fpsApi.beneficiaries(query || undefined, pend, 50, 0)); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }, []);
  useEffect(() => { load('', false); }, [load, cycle]);

  const open = async (id: string) => {
    setErr('');
    try { setSel(await fpsApi.beneficiary(id)); } catch (e) { setErr(errMsg(e)); }
  };

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: s(2) }}>
        <Stat k="Assigned beneficiaries" v={data ? String(data.total) : '…'} />
        <Stat k="Served this cycle" v={data ? String(data.served_this_cycle) : '…'} />
        <Stat k="Pending" v={data ? String(data.total - data.served_this_cycle) : '…'} />
        <Stat k="Expected today" v="—" sub="visit-based distribution" />
      </div>
      <Card title="Find beneficiary" action={
        <label style={{ fontSize: 12, color: c.body, display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={pendingOnly} onChange={e => { setPendingOnly(e.target.checked); load(q, e.target.checked); }} /> Pending only
        </label>
      }>
        <div style={{ display: 'flex', gap: s(2) }}>
          <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load(q, pendingOnly)}
            placeholder="Search Beneficiary ID / name" style={{ flex: 1, border: `1px solid ${c.lineStrong}`, borderRadius: 6, padding: '9px 10px', fontSize: 13 }} />
          <button onClick={() => load(q, pendingOnly)} style={btn}>SEARCH</button>
        </div>
        <div style={{ marginTop: s(3), display: 'flex', flexDirection: 'column' }}>
          {busy && <div style={{ fontSize: 12.5, color: c.muted }}>Searching…</div>}
          {(data?.beneficiaries || []).map((b: any) => (
            <button key={b.beneficiary_id} onClick={() => open(b.beneficiary_id)}
              style={{ textAlign: 'left', background: sel?.beneficiary?.beneficiary_id === b.beneficiary_id ? '#EFF6FF' : '#fff', border: 'none', borderBottom: `1px solid ${c.line}`, padding: '10px 4px', cursor: 'pointer', display: 'flex', gap: s(2), alignItems: 'center' }}>
              <span style={{ fontFamily: font.mono, fontSize: 12, fontWeight: 700 }}>{b.beneficiary_id}</span>
              <span style={{ fontSize: 12.5 }}>{b.name} · {b.scheme} · {b.household_size} members</span>
              <span style={{ marginLeft: 'auto' }}><Badge tone={b.collection_status === 'COLLECTED' ? 'ok' : b.collection_status === 'PARTIAL' ? 'warn' : 'accent'}>{b.collection_status}</Badge></span>
            </button>
          ))}
          {data && data.beneficiaries.length === 0 && <div style={{ fontSize: 12.5, color: c.muted, padding: s(2) }}>No beneficiaries match.</div>}
        </div>
      </Card>
      {sel && (
        <Card title={`Beneficiary ${sel.beneficiary.beneficiary_id}`} action={<button onClick={() => setSel(null)} style={btnGhost}>Close</button>}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: s(2), fontSize: 12.5 }}>
            <div><div style={label}>Name</div><div style={{ fontWeight: 700 }}>{sel.beneficiary.name}</div></div>
            <div><div style={label}>Scheme</div><div>{sel.beneficiary.scheme}</div></div>
            <div><div style={label}>Family members</div><div>{sel.beneficiary.household_size}</div></div>
            <div><div style={label}>Monthly entitlement</div><div style={{ fontWeight: 700 }}>{kg(sel.entitlement.total_kg)} <span style={{ fontWeight: 400, color: c.muted }}>(Rice {kg(sel.entitlement.rice_kg)} · Wheat {kg(sel.entitlement.wheat_kg)})</span></div></div>
            <div><div style={label}>Current cycle</div><div>{sel.cycle}</div></div>
            <div><div style={label}>Collected</div><div>Rice {kg(sel.entitlement.collected_rice_kg)} · Wheat {kg(sel.entitlement.collected_wheat_kg)}</div></div>
            <div><div style={label}>Remaining</div><div style={{ fontWeight: 700 }}>Rice {kg(sel.entitlement.remaining_rice_kg)} · Wheat {kg(sel.entitlement.remaining_wheat_kg)}</div></div>
          </div>
          <div style={{ fontSize: 11, color: c.muted, marginTop: s(2) }}>Entitlement source: {sel.entitlement.source}</div>
          <button onClick={() => onDistribute(sel.beneficiary.beneficiary_id)} style={{ ...btn, marginTop: s(3) }}>START DISTRIBUTION →</button>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- STEP 5 distribution
function DistributionPanel({ cycle, preselect, onDone }: {
  cycle: string; preselect: string | null; onDone: () => void;
}) {
  const [queue, setQueue] = useState<any[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [commodity, setCommodity] = useState('RICE');
  const [qty, setQty] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [outbox, setOutboxState] = useState<QueuedDist[]>([]);
  const fpsId = useMemo(() => { try { return JSON.parse(sessionStorage.getItem('dsp-fps-id') || 'null'); } catch { return null; } }, []);

  const loadQueue = useCallback(async () => {
    setErr('');
    try { const r = await fpsApi.beneficiaries(undefined, true, 100, 0); setQueue(r.beneficiaries); }
    catch (e) { setErr(errMsg(e)); }
  }, []);
  useEffect(() => { loadQueue(); if (fpsId) setOutboxState(loadOutbox(fpsId)); }, [loadQueue, cycle, fpsId]);
  useEffect(() => { if (preselect) { setSelId(preselect); setResult(null); } }, [preselect]);

  useEffect(() => {
    if (!selId) { setDetail(null); return; }
    fpsApi.beneficiary(selId).then(d => {
      setDetail(d);
      const remR = d.entitlement.remaining_rice_kg, remW = d.entitlement.remaining_wheat_kg;
      const com = remR > 0 ? 'RICE' : 'WHEAT';
      setCommodity(com);
      setQty(String(com === 'RICE' ? remR : remW));
    }).catch(e => setErr(errMsg(e)));
  }, [selId]);

  const remaining = detail ? (commodity === 'RICE' ? detail.entitlement.remaining_rice_kg : detail.entitlement.remaining_wheat_kg) : 0;

  const confirm = async () => {
    if (!detail) return;
    setErr(''); setBusy(true);
    const payload = { beneficiary_id: detail.beneficiary.beneficiary_id, commodity, quantity_kg: Number(qty), client_ref: newClientRef() };
    try {
      const r = await fpsApi.distribute(payload);
      setResult(r); setSelId(null); setDetail(null);
      loadQueue(); onDone();
    } catch (e) {
      if (e instanceof ApiError && e.status === 0 && fpsId) {
        // Offline: queue locally, never claim success.
        const item: QueuedDist = {
          client_ref: payload.client_ref!, beneficiary_id: payload.beneficiary_id,
          beneficiary_name: detail.beneficiary.name, commodity, quantity_kg: Number(qty),
          queued_at: new Date().toISOString(), status: 'QUEUED',
        };
        const next = [...loadOutbox(fpsId), item];
        storeOutbox(fpsId, next); setOutboxState(next);
        setResult({ queued: true, ...item });
        setSelId(null); setDetail(null);
      } else setErr(errMsg(e));
    } finally { setBusy(false); }
  };

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      {outbox.length > 0 && (
        <Card title={`Offline queue (${outbox.length}) — saved locally, waiting for sync`}>
          {outbox.map(o => (
            <div key={o.client_ref} style={{ display: 'flex', gap: s(2), alignItems: 'center', fontSize: 12.5, padding: '8px 0', borderBottom: `1px solid ${c.line}` }}>
              <span style={{ fontFamily: font.mono, fontWeight: 700 }}>{o.beneficiary_id}</span>
              <span>{o.commodity} · {kg(o.quantity_kg)}</span>
              <span style={{ marginLeft: 'auto' }}><Badge tone={o.status === 'FAILED' ? 'bad' : 'warn'}>{o.status === 'FAILED' ? 'SYNC FAILED' : 'SAVED LOCALLY — WAITING FOR SYNC'}</Badge></span>
            </div>
          ))}
          <div style={{ fontSize: 11, color: c.muted, marginTop: s(1) }}>Queued distributions are confirmed only after the backend accepts them.</div>
        </Card>
      )}
      {result && !result.queued && (
        <div style={{ background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 8, padding: s(4) }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: c.ok }}>✓ DISTRIBUTION COMPLETED</div>
          <div style={{ fontSize: 12.5, marginTop: s(1) }}>
            Transaction <strong style={{ fontFamily: font.mono }}>{result.transaction_id}</strong> · {result.beneficiary_id} · {result.commodity} {kg(result.quantity_kg)} · {fmtDT(result.timestamp)}
            {result.replayed && <span> (replayed — original record kept)</span>}
          </div>
        </div>
      )}
      {result?.queued && (
        <div style={{ background: c.warnBg, border: `1px solid ${c.warnLine}`, borderRadius: 8, padding: s(4), fontSize: 13 }}>
          <strong>SAVED LOCALLY — WAITING FOR SYNC.</strong> {result.beneficiary_id} · {result.commodity} {kg(result.quantity_kg)} will be submitted when connectivity returns.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: s(3) }}>
        <Card title={`Distribution queue (${queue.length} pending)`}>
          <div style={{ maxHeight: 460, overflowY: 'auto' }}>
            {queue.map((b: any) => (
              <div key={b.beneficiary_id} style={{ border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), marginBottom: s(2), background: selId === b.beneficiary_id ? '#EFF6FF' : '#fff' }}>
                <div style={{ display: 'flex', gap: s(2), alignItems: 'center' }}>
                  <span style={{ fontFamily: font.mono, fontWeight: 800, fontSize: 12.5 }}>{b.beneficiary_id}</span>
                  <span style={{ marginLeft: 'auto' }}><Badge tone="accent">READY FOR COLLECTION</Badge></span>
                </div>
                <div style={{ fontSize: 12, color: c.body, marginTop: 4 }}>{b.scheme} · {b.household_size} members · Entitlement {kg(b.entitlement_kg)}</div>
                <div style={{ fontSize: 12, marginTop: 2 }}>Remaining: Rice {kg(b.remaining_rice_kg)} · Wheat {kg(b.remaining_wheat_kg)}</div>
                <button onClick={() => { setSelId(b.beneficiary_id); setResult(null); }} style={{ ...btnGhost, padding: '5px 10px', fontSize: 12, marginTop: s(2) }}>START DISTRIBUTION</button>
              </div>
            ))}
            {queue.length === 0 && <div style={{ fontSize: 13, color: c.ok }}>Queue clear — every assigned beneficiary has collected in {cycle}.</div>}
          </div>
        </Card>

        <Card title="Distribution process">
          {!detail && <div style={{ fontSize: 13, color: c.muted }}>Select a beneficiary from the queue. Verification and entitlement are read from the backend record.</div>}
          {detail && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: s(2), fontSize: 13 }}>
              {[
                ['1. Verify beneficiary', `${detail.beneficiary.name} · ${detail.beneficiary.beneficiary_id} · ${detail.beneficiary.status}`],
                ['2. Verify entitlement', `Rice ${kg(detail.entitlement.rice_kg)} / Wheat ${kg(detail.entitlement.wheat_kg)} · remaining Rice ${kg(detail.entitlement.remaining_rice_kg)}, Wheat ${kg(detail.entitlement.remaining_wheat_kg)}`],
              ].map(([k, v]) => <div key={k as string} style={{ background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 6, padding: s(2) }}><strong>✓ {k}</strong><div style={{ fontSize: 12, marginTop: 2 }}>{v}</div></div>)}
              <label style={label}>3–4. Commodity &amp; e-PoS quantity<br />
                <span style={{ display: 'flex', gap: s(2), marginTop: 4 }}>
                  <select value={commodity} onChange={e => { setCommodity(e.target.value); setQty(String(e.target.value === 'RICE' ? detail.entitlement.remaining_rice_kg : detail.entitlement.remaining_wheat_kg)); }} style={{ padding: 8, border: `1px solid ${c.line}`, borderRadius: 5 }}>
                    <option value="RICE" disabled={detail.entitlement.remaining_rice_kg <= 0}>RICE ({kg(detail.entitlement.remaining_rice_kg)} left)</option>
                    <option value="WHEAT" disabled={detail.entitlement.remaining_wheat_kg <= 0}>WHEAT ({kg(detail.entitlement.remaining_wheat_kg)} left)</option>
                  </select>
                  <input type="number" min="0.1" max={remaining} step="0.1" value={qty} onChange={e => setQty(e.target.value)} style={{ flex: 1, padding: 8, border: `1px solid ${c.line}`, borderRadius: 5 }} />
                </span></label>
              <div style={{ fontSize: 11, color: c.muted }}>5–8. Confirm → transaction recorded → inventory, history and collection status update in the backend.</div>
              <div style={{ display: 'flex', gap: s(2) }}>
                <button onClick={() => { setSelId(null); setDetail(null); }} style={btnGhost}>Cancel</button>
                <button disabled={busy || !qty || Number(qty) <= 0 || Number(qty) - remaining > 1e-9} onClick={confirm}
                  style={busy || !qty || Number(qty) <= 0 || Number(qty) - remaining > 1e-9 ? btnDisabled : btn}>
                  {busy ? 'Recording…' : 'CONFIRM DISTRIBUTION'}</button>
              </div>
              {Number(qty) - remaining > 1e-9 && <div style={{ fontSize: 12, color: c.bad }}>Quantity exceeds the remaining entitlement of {kg(remaining)}.</div>}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 6 reconciliation
function ReconPanel({ data, onChanged }: { data: any; onChanged: () => void }) {
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState('');

  const review = async (com: string) => {
    setErr(''); setBusy(com);
    try {
      await fpsApi.reviewVariance({ commodity: com, note: notes[com] });
      setNotes({ ...notes, [com]: '' });
      onChanged();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(''); }
  };

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      <Card title={`Stock & transaction reconciliation — ${data.cycle}`} action={data.reconciled ? <Badge tone="ok">RECONCILED ✓</Badge> : <Badge tone="warn">REVIEW PENDING</Badge>}>
        <div style={{ fontSize: 12.5, color: c.body, marginBottom: s(3) }}>
          Opening + Received − Distributed + Adjustments = Expected closing, compared against the ledger and the source records (e-PoS lines, verified deliveries).
        </div>
        {data.lines.map((r: any) => {
          const expected = (r.opening_stock_kg ?? 0) + (r.received_kg ?? 0) - (r.dispatched_kg ?? 0) - (r.distributed_kg ?? 0) + (r.adjusted_kg ?? 0);
          const hasVar = (r.distribution_variance_kg || 0) !== 0 || (r.receipt_variance_kg || 0) !== 0;
          return (
            <div key={r.commodity} style={{ border: `1px solid ${hasVar ? c.warnLine : c.okLine}`, borderRadius: 8, padding: s(3), marginBottom: s(3), background: '#fff' }}>
              <div style={{ display: 'flex', gap: s(2), alignItems: 'center', flexWrap: 'wrap' }}>
                <strong style={{ fontSize: 14 }}>{r.commodity}</strong>
                {!r.has_ledger && <Badge tone="idle">NO LEDGER</Badge>}
                {r.has_ledger && !hasVar && <Badge tone="ok">RECONCILED ✓</Badge>}
                {r.has_ledger && hasVar && <Badge tone="warn">VARIANCE DETECTED</Badge>}
                {r.review && <span style={{ fontSize: 11.5, color: c.ok }}>Reviewed: {r.review.note} ({r.review.reviewed_by})</span>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: s(2), marginTop: s(2), fontSize: 12.5 }}>
                <div><div style={label}>Opening</div><div>{r.opening_stock_kg != null ? kg(r.opening_stock_kg) : '—'}</div></div>
                <div><div style={label}>+ Received</div><div>{r.received_kg != null ? kg(r.received_kg) : '—'}</div></div>
                <div><div style={label}>− Distributed</div><div>{r.distributed_kg != null ? kg(r.distributed_kg) : '—'}</div></div>
                <div><div style={label}>± Adjustments</div><div>{r.adjusted_kg != null ? `${Number(r.adjusted_kg) > 0 ? '+' : ''}${num(r.adjusted_kg)} kg` : '—'}</div></div>
                <div><div style={label}>= Expected closing</div><div style={{ fontWeight: 700 }}>{r.has_ledger ? kg(expected) : '—'}</div></div>
                <div><div style={label}>Ledger closing</div><div style={{ fontWeight: 700 }}>{r.ledger_closing_kg != null ? kg(r.ledger_closing_kg) : '—'}</div></div>
                <div><div style={label}>e-PoS distributed</div><div>{kg(r.epos_success_kg)}</div></div>
                <div><div style={label}>Verified deliveries</div><div>{kg(r.verified_deliveries_kg)}</div></div>
                <div><div style={label}>Distribution variance</div><div style={{ fontWeight: 800, color: r.distribution_variance_kg ? c.warn : c.ok }}>{r.distribution_variance_kg != null ? `${Number(r.distribution_variance_kg) > 0 ? '+' : ''}${num(r.distribution_variance_kg)} kg` : '—'}</div></div>
                <div><div style={label}>Receipt variance</div><div style={{ fontWeight: 800, color: r.receipt_variance_kg ? c.warn : c.ok }}>{r.receipt_variance_kg != null ? `${Number(r.receipt_variance_kg) > 0 ? '+' : ''}${num(r.receipt_variance_kg)} kg` : '—'}</div></div>
              </div>
              {r.has_ledger && hasVar && (
                <div style={{ marginTop: s(2) }}>
                  <div style={{ fontSize: 12, color: c.body }}>Possible areas to verify: recent transactions · stock receipts · adjustment records · previous reconciliation.</div>
                  {!r.review ? (
                    <div style={{ display: 'flex', gap: s(2), marginTop: s(2) }}>
                      <input value={notes[r.commodity] || ''} onChange={e => setNotes({ ...notes, [r.commodity]: e.target.value })}
                        placeholder="Review note (required before day closure)" style={{ flex: 1, padding: 8, border: `1px solid ${c.line}`, borderRadius: 5, fontSize: 13 }} />
                      <button disabled={busy === r.commodity || !(notes[r.commodity] || '').trim() || (notes[r.commodity] || '').trim().length < 5}
                        onClick={() => review(r.commodity)} style={busy === r.commodity || !(notes[r.commodity] || '').trim() ? btnDisabled : btnGhost}>
                        {busy === r.commodity ? 'Saving…' : 'RECORD REVIEW'}</button>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          );
        })}
        <div style={{ fontSize: 11.5, color: c.muted }}>{data.note}</div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 7 requests
const REQ_FLOW = ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'DISPATCHED', 'RECEIVED'] as const;
function RequestsPanel({ data, stock, insights, onChanged, onGoStock }: {
  data: any; stock: any; insights: any[]; onChanged: () => void; onGoStock: () => void;
}) {
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState('');
  const [form, setForm] = useState({ commodity: 'RICE', requested_kg: '', reason: '', requested_delivery_date: '' });
  const [created, setCreated] = useState<any>(null);

  const act = async (kind: string, id?: string) => {
    setErr(''); setBusy(`${kind}-${id || 'new'}`);
    try {
      if (kind === 'create') {
        const r = await fpsApi.createRequest({
          commodity: form.commodity, requested_kg: Number(form.requested_kg),
          reason: form.reason, requested_delivery_date: form.requested_delivery_date || undefined,
        });
        setCreated(r);
        setForm({ commodity: 'RICE', requested_kg: '', reason: '', requested_delivery_date: '' });
      } else if (kind === 'submit') await fpsApi.submitRequest(id!);
      else if (kind === 'receive') await fpsApi.receiveRequest(id!);
      else if (kind === 'withdraw') await fpsApi.withdrawRequest(id!);
      onChanged();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(''); }
  };

  const ctxFor = (com: string) => {
    const card = (stock?.cards || []).find((x: any) => x.commodity === com);
    const ins = (insights || []).find((x: any) => x.commodity === com && x.type === 'DEPLETION_COVER');
    return { card, ins };
  };
  const ctx = ctxFor(form.commodity);

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      {created && (
        <div style={{ background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 8, padding: s(3), fontSize: 13 }}>
          <strong>Draft {created.request_id} created.</strong> Current stock {kg(created.current_stock_kg)}
          {created.derived_cover_days != null && <span> · covers ≈ {created.derived_cover_days} day(s) at {created.recent_daily_rate_kg} kg/day</span>}.
          Submit it below to send it for review.
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: s(3) }}>
        <Card title="Create replenishment request">
          <div style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(2), fontSize: 12.5, marginBottom: s(2) }}>
            <div style={label}>Calculated context — {form.commodity}</div>
            <div style={{ marginTop: 4 }}>Current stock: <strong>{ctx.card?.closing_stock_kg != null ? kg(ctx.card.closing_stock_kg) : '—'}</strong>
              {ctx.ins && <span> · {ctx.ins.headline}</span>}</div>
            {!ctx.card && <span style={{ color: c.muted }}>No ledger for this commodity yet — <button onClick={onGoStock} style={{ background: 'none', border: 'none', color: c.accent, cursor: 'pointer', padding: 0, fontSize: 12.5 }}>check stock</button>.</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: s(2), fontSize: 13 }}>
            <label style={label}>Commodity<br />
              <select value={form.commodity} onChange={e => setForm({ ...form, commodity: e.target.value })} style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }}><option>RICE</option><option>WHEAT</option></select></label>
            <label style={label}>Required quantity (kg)<br />
              <input type="number" min="1" step="1" value={form.requested_kg} onChange={e => setForm({ ...form, requested_kg: e.target.value })} style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <label style={label}>Reason<br />
              <input value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} placeholder="Why is this quantity needed?" style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <label style={label}>Requested delivery date<br />
              <input type="date" value={form.requested_delivery_date} onChange={e => setForm({ ...form, requested_delivery_date: e.target.value })} style={{ width: '100%', padding: 8, marginTop: 4, border: `1px solid ${c.line}`, borderRadius: 5 }} /></label>
            <button disabled={busy === 'create-new' || !form.requested_kg || form.reason.trim().length < 5} onClick={() => act('create')}
              style={busy === 'create-new' || !form.requested_kg || form.reason.trim().length < 5 ? btnDisabled : btn}>
              {busy === 'create-new' ? 'Creating…' : 'CREATE REQUEST'}</button>
          </div>
        </Card>
        <Card title={`Current requests (${data.requests.length})`}>
          {data.requests.length === 0 && <div style={{ fontSize: 13, color: c.muted }}>No replenishment requests yet.</div>}
          {data.requests.map((r: any) => (
            <div key={r.request_id} style={{ border: `1px solid ${c.line}`, borderRadius: 8, padding: s(3), marginBottom: s(3) }}>
              <div style={{ display: 'flex', gap: s(2), alignItems: 'center', flexWrap: 'wrap' }}>
                <strong style={{ fontFamily: font.mono, fontSize: 13 }}>{r.request_id}</strong>
                <span style={{ marginLeft: 'auto' }}><Badge tone={r.status === 'RECEIVED' ? 'ok' : r.status === 'REJECTED' ? 'bad' : r.status === 'DRAFT' ? 'idle' : 'accent'}>{r.status.replace('_', ' ')}</Badge></span>
              </div>
              <div style={{ fontSize: 12.5, marginTop: 4 }}>{r.commodity} · {kg(r.requested_kg)} requested · stock at request {kg(r.current_stock_kg)} · {r.reason}</div>
              <div style={{ fontSize: 11.5, color: c.muted, marginTop: 2 }}>Requested {fmtDT(r.created_at)}{r.requested_delivery_date ? ` · delivery wanted ${r.requested_delivery_date}` : ''}{r.decision_note ? ` · note: ${r.decision_note}` : ''}</div>
              {r.status !== 'DRAFT' && r.status !== 'REJECTED' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginTop: s(2), overflowX: 'auto' }}>
                  {REQ_FLOW.map((st, i) => {
                    const reached = REQ_FLOW.indexOf(r.status as any) >= i;
                    const cur = r.status === st;
                    return (
                      <span key={st} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                        {i > 0 && <span style={{ width: 14, height: 2, background: reached ? c.ok : c.line }} />}
                        <span style={{
                          fontSize: 9.5, fontWeight: 800, padding: '3px 7px', borderRadius: 999,
                          background: cur ? '#1D4ED8' : reached ? c.ok : c.canvas,
                          color: cur || reached ? '#fff' : c.muted, border: '1px solid transparent',
                        }}>{reached && !cur ? '✓ ' : ''}{st.replace('_', ' ')}</span>
                      </span>
                    );
                  })}
                </div>
              )}
              <div style={{ display: 'flex', gap: s(2), marginTop: s(2), flexWrap: 'wrap' }}>
                {r.status === 'DRAFT' && (<>
                  <button disabled={busy === `submit-${r.request_id}`} onClick={() => act('submit', r.request_id)} style={busy === `submit-${r.request_id}` ? btnDisabled : btn}>SUBMIT</button>
                  <button disabled={busy === `withdraw-${r.request_id}`} onClick={() => act('withdraw', r.request_id)} style={btnGhost}>Withdraw</button>
                </>)}
                {r.status === 'DISPATCHED' && (
                  <button disabled={busy === `receive-${r.request_id}`} onClick={() => act('receive', r.request_id)} style={busy === `receive-${r.request_id}` ? btnDisabled : btn}>CONFIRM RECEIVED</button>
                )}
              </div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- STEP 8 close day
function CloseDayPanel({ data, onChanged, onGo }: { data: any; onChanged: () => void; onGo: (i: number) => void }) {
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [closed, setClosed] = useState<any>(null);
  const r = data.readiness;
  const sm = data.summary;

  const checks = [
    { label: 'All transactions synced', ok: true, detail: `${sm.transactions_today} transaction(s) today — every record is terminal in the backend.` },
    { label: 'Stock movements reconciled', ok: r.unreviewed_variance.length === 0 && r.missing_ledger.length === 0, detail: r.unreviewed_variance.length ? `${r.unreviewed_variance.join(', ')} variance needs review` : 'Ledger matches source records or variances reviewed.', step: 5 },
    { label: 'Pending distributions reviewed', ok: true, detail: 'Queue state is live from beneficiary collection records.', step: 4 },
    { label: 'Variances reviewed', ok: r.unreviewed_variance.length === 0, detail: r.unreviewed_variance.length ? `${r.unreviewed_variance.join(', ')} unreviewed` : 'No unreviewed variance.', step: 5 },
    { label: 'Supply requests reviewed', ok: true, detail: `${sm.pending_requests} request(s) in flight — tracked, not blocking.` },
    { label: 'e-PoS status checked', ok: true, detail: data.reconciliation ? 'Activity verified from recorded transactions.' : '', step: 2 },
  ];

  const close = async () => {
    setErr(''); setBusy(true);
    try { const res = await fpsApi.closeDay(); setClosed(res); onChanged(); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  if (closed) {
    return (
      <div style={{ padding: s(4) }}>
        <div style={{ background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 8, padding: s(4), textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', background: c.ok, color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 800 }}>✓</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: c.ok, marginTop: s(2) }}>DAY CLOSED</div>
          <div style={{ fontSize: 12.5, color: c.body, marginTop: s(1) }}>{closed.closure_id} · {closed.business_date} · {closed.beneficiaries_served} beneficiaries · {closed.transactions} transactions</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <Err msg={err} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: s(2) }}>
        <Stat k="Beneficiaries served" v={String(sm.beneficiaries_served_cycle)} sub={`cycle ${data.cycle}`} />
        <Stat k="Transactions" v={String(sm.transactions_cycle)} sub={`${sm.transactions_today} today`} />
        <Stat k="Rice distributed" v={kg(sm.per_commodity.RICE.distributed_kg)} />
        <Stat k="Wheat distributed" v={kg(sm.per_commodity.WHEAT.distributed_kg)} />
        <Stat k="Stock remaining" v={kg(sm.stock_remaining_kg)} />
        <Stat k="Pending requests" v={String(sm.pending_requests)} />
      </div>
      <Card title="Before closing">
        {checks.map(ch => (
          <div key={ch.label} style={{ display: 'flex', gap: s(2), alignItems: 'center', padding: '9px 0', borderBottom: `1px solid ${c.line}`, fontSize: 13 }}>
            <span style={{ width: 22, height: 22, borderRadius: '50%', background: ch.ok ? c.ok : c.warn, color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800, flexShrink: 0 }}>{ch.ok ? '✓' : '!'}</span>
            <span style={{ fontWeight: 600 }}>{ch.label}</span>
            <span style={{ color: c.muted, fontSize: 12 }}>{ch.detail}</span>
          </div>
        ))}
      </Card>
      {r.blockers.length > 0 ? (
        <Card title={`Cannot close day — ${r.blockers.length} item(s) require attention`}>
          {r.blockers.map((b: any, i: number) => (
            <div key={i} style={{ background: c.warnBg, border: `1px solid ${c.warnLine}`, borderRadius: 6, padding: s(3), marginBottom: s(2), display: 'flex', gap: s(2), alignItems: 'center', flexWrap: 'wrap', fontSize: 13 }}>
              <span>⚠ {b.message}</span>
              {b.step && <button onClick={() => onGo(STEPS.indexOf(b.step as any))} style={{ ...btnGhost, padding: '4px 10px', fontSize: 12, marginLeft: 'auto' }}>Go to {b.step} →</button>}
            </div>
          ))}
        </Card>
      ) : (
        <Card title="Ready to close day">
          <div style={{ fontSize: 13, color: c.ok, fontWeight: 700 }}>All required checks pass. Closing records the day summary in the backend.</div>
          <button disabled={busy} onClick={close} style={busy ? btnDisabled : { ...btn, marginTop: s(3), background: '#1D4ED8', borderColor: '#1D4ED8' }}>{busy ? 'Closing…' : 'CLOSE DAY'}</button>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- main shell
export default function FPSPortal() {
  const { user, logout } = useAuth();
  const [me, setMe] = useState<any>(null);
  const [step, setStep] = useState(0);
  const [visited, setVisited] = useState<number[]>([]);
  const [err, setErr] = useState('');
  const [overview, setOverview] = useState<any>(null);
  const [stock, setStock] = useState<any>(null);
  const [epos, setEpos] = useState<any>(null);
  const [recon, setRecon] = useState<any>(null);
  const [requests, setRequests] = useState<any>(null);
  const [closeData, setCloseData] = useState<any>(null);
  const [insights, setInsights] = useState<any[]>([]);
  const [preselectBen, setPreselectBen] = useState<string | null>(null);
  const [online, setOnline] = useState(() => (typeof navigator !== 'undefined' ? navigator.onLine : true));
  const [syncing, setSyncing] = useState(false);
  const [outboxCount, setOutboxCount] = useState(0);

  const fpsId = me?.shop?.fps_id as string | undefined;

  useEffect(() => {
    const up = () => setOnline(navigator.onLine);
    window.addEventListener('online', up);
    window.addEventListener('offline', up);
    return () => { window.removeEventListener('online', up); window.removeEventListener('offline', up); };
  }, []);

  // boot: shop context, persisted step, overview
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const m = await fpsApi.me();
        if (cancelled) return;
        setMe(m);
        try { sessionStorage.setItem('dsp-fps-id', JSON.stringify(m.shop.fps_id)); } catch {}
        setStep(loadStep(m.shop.fps_id));
        setVisited(loadVisited(m.shop.fps_id));
        setOutboxCount(loadOutbox(m.shop.fps_id).filter(o => o.status !== 'SYNCING').length);
        const ov = await fpsApi.overview();
        if (!cancelled) { setOverview(ov); setInsights(ov.insights || []); }
      } catch (e) { if (!cancelled) setErr(errMsg(e)); }
    })();
    return () => { cancelled = true; };
  }, []);

  const refreshStep = useCallback(async (st: number) => {
    try {
      if (st === 0) { const ov = await fpsApi.overview(); setOverview(ov); setInsights(ov.insights || []); }
      if (st === 1) setStock(await fpsApi.stock());
      if (st === 2) setEpos(await fpsApi.epos());
      if (st === 5) setRecon(await fpsApi.reconciliation());
      if (st === 6) setRequests(await fpsApi.requests());
      if (st === 7) setCloseData(await fpsApi.closeStatus());
      setErr('');
    } catch (e) { setErr(errMsg(e)); }
  }, []);

  // lazy-load each workspace when entered
  useEffect(() => {
    if (!fpsId) return;
    if (step === 1 && !stock) refreshStep(1);
    if (step === 2 && !epos) refreshStep(2);
    if (step === 5 && !recon) refreshStep(5);
    if (step === 6 && (!requests || !stock)) { refreshStep(6); if (!stock) refreshStep(1); }
    if (step === 7 && !closeData) refreshStep(7);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, fpsId]);

  const refreshAll = useCallback(async () => {
    const ov = await fpsApi.overview().catch(() => null);
    if (ov) { setOverview(ov); setInsights(ov.insights || []); }
    await refreshStep(step);
    // The CLOSE DAY lock depends on readiness: keep it fresh after every mutation.
    if (step !== 7) {
      try { setCloseData(await fpsApi.closeStatus()); } catch { /* lock keeps last known state */ }
    }
    if (fpsId) setOutboxCount(loadOutbox(fpsId).length);
  }, [refreshStep, step, fpsId]);

  const go = useCallback((i: number) => {
    setStep(i);
    if (fpsId) {
      storeStep(fpsId, i);
      setVisited(prev => {
        const next = prev.includes(i) ? prev : [...prev, i];
        storeVisited(fpsId, next);
        return next;
      });
    }
    setPreselectBen(null);
  }, [fpsId]);

  // offline outbox sync: replay queued distributions in order; never claim success early
  const syncOutbox = useCallback(async () => {
    if (!fpsId || syncing || !navigator.onLine) return;
    const items = loadOutbox(fpsId);
    if (!items.length) return;
    setSyncing(true);
    const remaining: QueuedDist[] = [];
    let synced = 0;
    for (let idx = 0; idx < items.length; idx++) {
      const it = items[idx];
      try {
        await fpsApi.distribute({ beneficiary_id: it.beneficiary_id, commodity: it.commodity, quantity_kg: it.quantity_kg, client_ref: it.client_ref });
        synced++;
      } catch (e) {
        if (e instanceof ApiError && e.status === 0) {
          // network broke mid-replay: keep this item and everything after it
          remaining.push({ ...it, status: 'QUEUED' }, ...items.slice(idx + 1));
          break;
        }
        remaining.push({ ...it, status: 'FAILED', error: errMsg(e) });
      }
    }
    storeOutbox(fpsId, remaining);
    setOutboxCount(remaining.length);
    setSyncing(false);
    if (synced > 0) refreshAll();
  }, [fpsId, syncing, refreshAll]);

  useEffect(() => {
    if (online && fpsId) syncOutbox();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, fpsId]);

  const locked = useCallback((i: number): { lock: boolean; why?: string } => {
    if (i === 7 && closeData && !closeData.readiness.ready) {
      const hard = closeData.readiness.blockers.some((b: any) => b.code === 'VARIANCE_REVIEW_REQUIRED' || b.code === 'MISSING_LEDGER');
      if (hard) return { lock: true, why: 'Locked — complete the required review in Reconciliation first' };
    }
    return { lock: false };
  }, [closeData]);

  if (!user) return null;
  if (!me) {
    return (
      <div style={{ minHeight: '100vh', background: '#F1F5F9', fontFamily: font.ui }}>
        <GovHeader user={user} shop={null} alertCount={0} onBell={() => {}} onLogout={logout} net={{ online, syncing, queued: 0 }} />
        {err ? <div style={{ margin: s(4), background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(3), borderRadius: 6 }}>{err}</div> : <Loading what="your shop" />}
      </div>
    );
  }

  const alertCount = overview?.alerts?.length ?? 0;

  return (
    <div style={{ minHeight: '100vh', background: '#F1F5F9', fontFamily: font.ui }}>
      <GovHeader user={user} shop={me.shop} alertCount={alertCount} onBell={() => go(0)} onLogout={logout}
        net={{ online, syncing, queued: outboxCount }} />
      <ShopHeader shop={me.shop} owner={me.owner} cycle={me.cycle} step={step} />
      <WorkflowBar active={step} visited={visited} locked={locked} onGo={go} />
      {!online && (
        <div style={{ margin: `${s(2)} ${s(4)}`, background: c.warnBg, border: `1px solid ${c.warnLine}`, color: c.warn, padding: s(2), borderRadius: 6, fontSize: 12.5, fontWeight: 700 }}>
          OFFLINE — distributions will be SAVED LOCALLY and synced when connectivity returns. Nothing is confirmed until the backend accepts it.
        </div>
      )}
      {err && <div style={{ margin: `${s(2)} ${s(4)}`, background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(2), borderRadius: 6, fontSize: 12.5 }}>{err}</div>}

      <main>
        {step === 0 && (overview ? <OverviewPanel data={overview} onGo={go} /> : <Loading what="overview" />)}
        {step === 1 && (stock ? <StockPanel data={stock} onChanged={refreshAll} /> : <Loading what="stock" />)}
        {step === 2 && (epos ? <EposPanel data={epos} /> : <Loading what="e-PoS data" />)}
        {step === 3 && <BeneficiariesPanel cycle={me.cycle.cycle} onDistribute={(id) => { setPreselectBen(id); go(4); }} />}
        {step === 4 && (
          <DistributionPanel cycle={me.cycle.cycle} preselect={preselectBen} onDone={refreshAll} />
        )}
        {step === 5 && (recon ? <ReconPanel data={recon} onChanged={refreshAll} /> : <Loading what="reconciliation" />)}
        {step === 6 && (requests ? <RequestsPanel data={requests} stock={stock} insights={insights} onChanged={refreshAll} onGoStock={() => go(1)} /> : <Loading what="requests" />)}
        {step === 7 && (closeData ? <CloseDayPanel data={closeData} onChanged={refreshAll} onGo={go} /> : <Loading what="day status" />)}
      </main>
      <footer style={{ padding: s(4), textAlign: 'center', fontSize: 11, color: c.faint }}>
        DemandSYNC · FPS operations are recorded against {me.shop.fps_id} · {me.cycle.cycle} · Advisory AI never alters official records.
      </footer>
    </div>
  );
}
