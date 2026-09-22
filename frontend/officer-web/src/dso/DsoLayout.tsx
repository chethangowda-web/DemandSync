/**
 * The control centre shell: a fixed operations rail, a command bar carrying cycle selection and live
 * backend state, and the routed workspace.
 *
 * Cycle selection and the cycle summary live here so every workspace reads the same operational truth
 * and a single action anywhere refreshes all of it.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { CycleRow, Summary, dso, stageStatuses } from './api';
import { c, clock, font, label, s } from './theme';
import { Badge } from './ui';

interface CycleCtx {
  cycle: string | null;
  cycles: CycleRow[];
  summary: Summary | null;
  summaryError: string | null;
  setCycle: (c: string) => void;
  refresh: () => void;
  lastSync: string | null;
  connected: boolean;
}
const Ctx = createContext<CycleCtx>(null as unknown as CycleCtx);
export const useCycle = () => useContext(Ctx);

const NAV: { to: string; label: string; group?: string }[] = [
  { to: '/dso', label: 'Command Centre', group: 'OPERATIONS' },
  { to: '/dso/demand', label: 'Demand Intelligence' },
  { to: '/dso/allocation', label: 'Allocation' },
  { to: '/dso/optimization', label: 'Optimization' },
  { to: '/dso/dispatch', label: 'Dispatch' },
  { to: '/dso/tracking', label: 'Tracking' },
  { to: '/dso/reconciliation', label: 'Delivery & Reconciliation' },
  { to: '/dso/exceptions', label: 'Exceptions', group: 'OVERSIGHT' },
  { to: '/dso/audit', label: 'Audit & Decision Trace' },
];

function NavRail({ summary }: { summary: Summary | null }) {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const stages = stageStatuses(summary?.state);
  const active = stages.find(x => x.status === 'ACTIVE');

  return (
    <nav style={{ width: 232, flex: '0 0 232px', background: c.navy, color: '#fff', display: 'flex',
      flexDirection: 'column', height: '100vh', position: 'sticky', top: 0 }}>
      <div style={{ padding: `${s(4)} ${s(4)} ${s(3)}`, borderBottom: `1px solid ${c.navyLine}` }}>
        <div style={{ font: `700 16px ${font.ui}`, letterSpacing: '-0.01em' }}>DemandSYNC</div>
        <div style={{ ...label, color: '#7FA8D4', marginTop: 3 }}>DSO Control Centre</div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: `${s(3)} 0` }}>
        {NAV.map(item => {
          const isActive = pathname === item.to;
          return (
            <div key={item.to}>
              {item.group && <div style={{ ...label, color: '#5C87B8', padding: `${s(3)} ${s(4)} ${s(2)}` }}>{item.group}</div>}
              <Link to={item.to} style={{
                display: 'flex', alignItems: 'center', gap: s(2), padding: `8px ${s(4)}`, fontSize: 13,
                color: isActive ? '#fff' : '#BBD3EC', textDecoration: 'none', fontWeight: isActive ? 600 : 400,
                background: isActive ? c.navyDeep : 'transparent',
                borderLeft: `3px solid ${isActive ? '#F5C518' : 'transparent'}`,
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', flex: '0 0 5px',
                  background: isActive ? '#F5C518' : '#3E6B9B' }} />
                {item.label}
              </Link>
            </div>
          );
        })}
      </div>

      <div style={{ borderTop: `1px solid ${c.navyLine}`, padding: s(4), fontSize: 12 }}>
        <div style={{ ...label, color: '#5C87B8' }}>Current stage</div>
        <div style={{ color: '#fff', fontWeight: 600, marginTop: 3, fontSize: 12.5 }}>
          {active ? `${active.short} ${active.label}` : summary?.state === 'CLOSED' ? 'Cycle closed' : '—'}
        </div>
        <div style={{ ...label, color: '#5C87B8', marginTop: s(3) }}>Officer</div>
        <div style={{ color: '#fff', marginTop: 3 }}>{user?.name}</div>
        <div style={{ color: '#7FA8D4', fontSize: 11 }}>{user?.role} · {user?.district || 'District unavailable'}</div>
        <div style={{ display: 'flex', gap: s(2), marginTop: s(3) }}>
          <Link to="/change-password" style={{ color: '#BBD3EC', fontSize: 11.5 }}>Change password</Link>
          <button onClick={logout} style={{ marginLeft: 'auto', background: 'transparent', color: '#BBD3EC',
            border: `1px solid ${c.navyLine}`, borderRadius: 4, padding: '2px 10px', cursor: 'pointer', fontSize: 11.5 }}>Sign out</button>
        </div>
      </div>
    </nav>
  );
}

function CommandBar({ ctx }: { ctx: CycleCtx }) {
  const { user } = useAuth();
  return (
    <header style={{ display: 'flex', alignItems: 'center', gap: s(5), padding: `0 ${s(6)}`, height: 56,
      background: c.surface, borderBottom: `1px solid ${c.line}`, position: 'sticky', top: 0, zIndex: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(3) }}>
        <span style={{ ...label }}>Current cycle</span>
        <select value={ctx.cycle ?? ''} onChange={e => ctx.setCycle(e.target.value)}
          style={{ font: `600 13px ${font.ui}`, padding: '6px 10px', borderRadius: 5, border: `1px solid ${c.lineStrong}`,
            background: c.surface, color: c.ink, minWidth: 190 }}>
          {ctx.cycles.map(x => <option key={x.cycle} value={x.cycle}>{x.cycle} — {x.state}</option>)}
        </select>
      </div>

      <div style={{ borderLeft: `1px solid ${c.line}`, paddingLeft: s(5) }}>
        <div style={{ ...label }}>Jurisdiction</div>
        <div style={{ fontSize: 12.5, color: c.ink, fontWeight: 600 }}>{user?.district || 'Not assigned'}</div>
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: s(5) }}>
        {ctx.summary && ctx.summary.exceptions.critical > 0 && (
          <Badge t="bad">{ctx.summary.exceptions.critical} critical</Badge>
        )}
        <div style={{ textAlign: 'right' }}>
          <div style={{ ...label }}>Backend</div>
          <div style={{ fontSize: 12, color: ctx.connected ? c.ok : c.bad, fontWeight: 600 }}>
            {ctx.connected ? 'CONNECTED' : 'UNREACHABLE'}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ ...label }}>Last sync</div>
          <div style={{ fontSize: 12, color: c.body, fontFamily: font.mono }}>{clock(ctx.lastSync)}</div>
        </div>
        <button onClick={ctx.refresh} style={{ font: `600 12px ${font.ui}`, padding: '6px 14px', borderRadius: 5,
          border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.navy, cursor: 'pointer' }}>Refresh</button>
      </div>
    </header>
  );
}

export default function DsoLayout() {
  const [cycles, setCycles] = useState<CycleRow[]>([]);
  const [cycle, setCycleState] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [connected, setConnected] = useState(true);
  const [tick, setTick] = useState(0);
  const navigate = useNavigate();

  const refresh = useCallback(() => setTick(t => t + 1), []);

  useEffect(() => {
    dso.cycles().then(list => {
      setCycles(list); setConnected(true);
      setCycleState(prev => prev ?? (list.find(x => x.state !== 'CLOSED')?.cycle ?? list[0]?.cycle ?? null));
    }).catch(() => setConnected(false));
  }, [tick]);

  useEffect(() => {
    if (!cycle) return;
    dso.summary(cycle)
      .then(sm => { setSummary(sm); setSummaryError(null); setConnected(true); setLastSync(new Date().toISOString()); })
      .catch(e => { setSummary(null); setSummaryError(e?.message || String(e)); setConnected(false); });
  }, [cycle, tick]);

  const setCycle = useCallback((next: string) => { setCycleState(next); setSummary(null); }, []);

  const ctx = useMemo<CycleCtx>(() => ({
    cycle, cycles, summary, summaryError, setCycle, refresh, lastSync, connected,
  }), [cycle, cycles, summary, summaryError, setCycle, refresh, lastSync, connected]);

  // keyboard: g then a number jumps to that stage's workspace
  useEffect(() => {
    let armed = false;
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA|SELECT/)) return;
      if (e.key === 'g') { armed = true; return; }
      if (armed && /[1-7]/.test(e.key)) {
        const st = stageStatuses(summary?.state)[Number(e.key) - 1];
        if (st) navigate(st.route);
      }
      armed = false;
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [navigate, summary?.state]);

  return (
    <Ctx.Provider value={ctx}>
      <div style={{ display: 'flex', minHeight: '100vh', background: c.canvas, font: `400 13px ${font.ui}`, color: c.body }}>
        <NavRail summary={summary} />
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <CommandBar ctx={ctx} />
          <main style={{ padding: s(6), display: 'flex', flexDirection: 'column', gap: s(5), minWidth: 0, flex: 1 }}>
            <Outlet />
          </main>
        </div>
      </div>
    </Ctx.Provider>
  );
}
