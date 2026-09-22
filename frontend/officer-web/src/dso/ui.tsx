/**
 * Shared primitives for the control centre.
 *
 * `DataUnavailable` is deliberately prominent: when the backend has nothing, the officer is told so
 * explicitly rather than shown a zero, a dash, or an empty chart that reads as "nothing is wrong".
 */
import { CSSProperties, ReactNode, useEffect, useState } from 'react';
import { c, font, label, panel, s, Tone, tone, toneFor } from './theme';

export function Panel({ title, action, children, style, pad = true, subtitle }:
  { title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; style?: CSSProperties; pad?: boolean }) {
  return (
    <section style={{ ...panel, display: 'flex', flexDirection: 'column', minWidth: 0, ...style }}>
      {title && (
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: s(3),
          padding: `${s(3)} ${s(4)}`, borderBottom: `1px solid ${c.line}` }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ ...label, color: c.ink, fontSize: 11.5 }}>{title}</div>
            {subtitle && <div style={{ fontSize: 11.5, color: c.muted, marginTop: 2 }}>{subtitle}</div>}
          </div>
          {action}
        </header>
      )}
      <div style={{ padding: pad ? s(4) : 0, minWidth: 0, flex: 1 }}>{children}</div>
    </section>
  );
}

export function Badge({ children, t, title }: { children: ReactNode; t?: Tone; title?: string }) {
  const k = t ?? toneFor(String(children));
  const v = tone[k];
  return (
    <span title={title} style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 3, fontSize: 10.5,
      fontWeight: 700, letterSpacing: '0.06em', color: v.fg, background: v.bg, border: `1px solid ${v.line}`,
      whiteSpace: 'nowrap' }}>{children}</span>
  );
}

export function DataUnavailable({ what, why }: { what: string; why?: string }) {
  return (
    <div style={{ padding: s(6), textAlign: 'center', border: `1px dashed ${c.lineStrong}`, borderRadius: 5,
      background: c.raised }}>
      <div style={{ ...label, color: c.muted }}>{what}</div>
      {why && <div style={{ fontSize: 12, color: c.faint, marginTop: 6, maxWidth: 440, marginInline: 'auto', lineHeight: 1.5 }}>{why}</div>}
    </div>
  );
}

export function Loading({ what = 'Loading' }: { what?: string }) {
  return <div style={{ padding: s(6), textAlign: 'center', ...label, color: c.faint }}>{what}…</div>;
}

export function ErrorNote({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div style={{ padding: s(3), borderRadius: 5, background: c.badBg, border: `1px solid ${c.badLine}`,
      color: c.bad, fontSize: 12.5, display: 'flex', justifyContent: 'space-between', gap: s(3), alignItems: 'center' }}>
      <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>{error}</span>
      {onRetry && <button onClick={onRetry} style={{ background: 'none', border: `1px solid ${c.badLine}`,
        color: c.bad, borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 11.5, whiteSpace: 'nowrap' }}>Retry</button>}
    </div>
  );
}

/** One figure in the situation strip. `hint` carries the comparison, or says it is unavailable. */
export function Metric({ name, value, hint, t, emphasis }:
  { name: string; value: ReactNode; hint?: ReactNode; t?: Tone; emphasis?: boolean }) {
  const v = t ? tone[t] : null;
  return (
    <div style={{ padding: `${s(3)} ${s(4)}`, borderRight: `1px solid ${c.line}`, minWidth: 0, flex: '1 1 0' }}>
      <div style={{ ...label }}>{name}</div>
      <div style={{ font: `${emphasis ? 700 : 600} ${emphasis ? 24 : 20}px ${font.ui}`, color: v ? v.fg : c.ink,
        marginTop: 4, letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
      <div style={{ fontSize: 11, color: c.muted, marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {hint ?? 'Comparison unavailable'}
      </div>
    </div>
  );
}

export function MetricStrip({ children }: { children: ReactNode }) {
  return (
    <div style={{ ...panel, display: 'flex', flexWrap: 'wrap', overflow: 'hidden' }}>{children}</div>
  );
}

/** Dense table. Columns are plain strings; rows render their own cells. */
export function Table({ head, children, maxHeight }: { head: string[]; children: ReactNode; maxHeight?: number }) {
  return (
    <div style={{ overflow: 'auto', maxHeight, border: `1px solid ${c.line}`, borderRadius: 5 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
        <thead>
          <tr>{head.map(h => (
            <th key={h} style={{ ...label, textAlign: 'left', padding: `${s(2)} ${s(3)}`, background: c.raised,
              borderBottom: `1px solid ${c.line}`, position: 'sticky', top: 0, zIndex: 1, whiteSpace: 'nowrap' }}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export const td: CSSProperties = { padding: `${s(2)} ${s(3)}`, borderBottom: `1px solid ${c.line}`, color: c.body, verticalAlign: 'middle' };
export const tdMono: CSSProperties = { ...td, fontFamily: font.mono, fontSize: 11.5 };

/** Horizontal utilisation/progress bar. */
export function Bar({ value, max, t = 'accent', height = 6 }: { value: number; max: number; t?: Tone; height?: number }) {
  const p = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div style={{ background: c.idleBg, borderRadius: 999, height, overflow: 'hidden', minWidth: 60 }}>
      <div style={{ width: `${p}%`, height: '100%', background: tone[t].fg, borderRadius: 999 }} />
    </div>
  );
}

/** Right-hand detail drawer. Closes on Escape; overlay click closes too. */
export function Drawer({ open, onClose, title, subtitle, children, width = 520 }:
  { open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; width?: number }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(11,37,69,0.35)', zIndex: 40 }} />
      <aside role="dialog" aria-modal="true" style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: `min(${width}px, 94vw)`,
        background: c.surface, borderLeft: `1px solid ${c.lineStrong}`, boxShadow: '-8px 0 24px rgba(15,23,42,0.12)',
        zIndex: 41, display: 'flex', flexDirection: 'column' }}>
        <header style={{ padding: s(4), borderBottom: `1px solid ${c.line}`, display: 'flex', justifyContent: 'space-between', gap: s(3) }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ font: `700 15px ${font.ui}`, color: c.ink, overflowWrap: 'anywhere' }}>{title}</div>
            {subtitle && <div style={{ fontSize: 12, color: c.muted, marginTop: 3 }}>{subtitle}</div>}
          </div>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', fontSize: 20,
            color: c.muted, cursor: 'pointer', lineHeight: 1, padding: 0 }}>×</button>
        </header>
        <div style={{ padding: s(4), overflow: 'auto', display: 'flex', flexDirection: 'column', gap: s(4) }}>{children}</div>
      </aside>
    </>
  );
}

/** Label/value pair grid used inside drawers and evidence blocks. */
export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: `${s(2)} ${s(4)}`, margin: 0, fontSize: 12.5 }}>
      {items.map(([k, v], i) => (
        <div key={i} style={{ display: 'contents' }}>
          <dt style={{ ...label, paddingTop: 2 }}>{k}</dt>
          <dd style={{ margin: 0, color: c.ink, overflowWrap: 'anywhere' }}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A small block of supporting evidence — always attributed to its source table(s). */
export function Evidence({ children, source }: { children: ReactNode; source: string }) {
  return (
    <div style={{ background: c.raised, border: `1px solid ${c.line}`, borderRadius: 5, padding: s(3) }}>
      <div style={{ ...label, marginBottom: 6 }}>Evidence</div>
      <div style={{ fontSize: 12.5, color: c.body, lineHeight: 1.6 }}>{children}</div>
      <div style={{ fontSize: 10.5, color: c.faint, marginTop: 8, fontFamily: font.mono }}>source: {source}</div>
    </div>
  );
}

/** Generic async data hook: tracks loading/error and exposes a manual reload. */
export function useData<T>(fn: () => Promise<T>, deps: unknown[]): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true); setError(null);
    fn().then(d => { if (live) { setData(d); setLoading(false); } })
      .catch(e => { if (live) { setError(e?.message || String(e)); setLoading(false); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { data, error, loading, reload: () => setN(x => x + 1) };
}

/** Wraps a data region so loading / error / empty are handled uniformly and never silently blank. */
export function Region<T>({ q, empty, children }:
  { q: { data: T | null; error: string | null; loading: boolean; reload: () => void }; empty?: ReactNode; children: (d: T) => ReactNode }) {
  if (q.loading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} onRetry={q.reload} />;
  if (q.data === null) return <DataUnavailable what="No data available" />;
  if (Array.isArray(q.data) && q.data.length === 0 && empty) return <>{empty}</>;
  return <>{children(q.data)}</>;
}
