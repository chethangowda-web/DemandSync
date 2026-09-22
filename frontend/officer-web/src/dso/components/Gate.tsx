/**
 * Decision gates.
 *
 * A gate never enables its action on optimism: the button is live only when every blocking check has
 * actually passed according to the backend. When it is blocked, the officer is told exactly which
 * check failed rather than a generic refusal.
 */
import { ReactNode } from 'react';
import { c, font, label, s, tone } from '../theme';

export interface Check { label: string; status: 'PASS' | 'FAIL' | 'WARN'; detail?: string; }

/** Turns the backend's closure-check map into display rows, in a stable, meaningful order. */
export const CLOSURE_LABELS: Record<string, string> = {
  ALL_MANIFESTS_DELIVERED: 'All deliveries recorded',
  NO_REJECTED_DELIVERIES: 'No rejected deliveries',
  DELIVERIES_WITHIN_TOLERANCE: 'Variance within tolerance',
  ALLOCATION_MATCHES_DELIVERY: 'Allocation matches delivery',
  AUDIT_CHAIN_INTACT: 'Audit chain intact',
  MANIFEST_HASHES_VERIFIED: 'Manifest hashes verified',
  NO_OPEN_BLOCKING_EXCEPTIONS: 'No blocking exceptions',
};

export function checksFromMap(m: Record<string, boolean>): Check[] {
  const order = Object.keys(CLOSURE_LABELS);
  const keys = [...order.filter(k => k in m), ...Object.keys(m).filter(k => !order.includes(k))];
  return keys.map(k => ({ label: CLOSURE_LABELS[k] ?? k.replace(/_/g, ' '), status: m[k] ? 'PASS' : 'FAIL' }));
}

export function CheckList({ checks }: { checks: Check[] }) {
  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column' }}>
      {checks.map((ck, i) => {
        const t = ck.status === 'PASS' ? tone.ok : ck.status === 'WARN' ? tone.warn : tone.bad;
        return (
          <li key={i} style={{ display: 'flex', alignItems: 'center', gap: s(3), padding: `${s(2)} 0`,
            borderBottom: i < checks.length - 1 ? `1px solid ${c.line}` : 'none' }}>
            <span aria-hidden style={{ width: 18, height: 18, borderRadius: '50%', flex: '0 0 18px',
              display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 700,
              background: t.bg, color: t.fg, border: `1px solid ${t.line}` }}>
              {ck.status === 'PASS' ? '✓' : ck.status === 'WARN' ? '!' : '✕'}
            </span>
            <span style={{ fontSize: 13, color: ck.status === 'PASS' ? c.body : c.ink,
              fontWeight: ck.status === 'PASS' ? 400 : 600, flex: 1, minWidth: 0 }}>{ck.label}</span>
            {ck.detail && <span style={{ fontSize: 11.5, color: t.fg, textAlign: 'right' }}>{ck.detail}</span>}
          </li>
        );
      })}
    </ul>
  );
}

export function DecisionGate({ title, intro, checks, action, onAction, busy, blockedNote, children }: {
  title: string; intro?: ReactNode; checks: Check[]; action: string;
  onAction: () => void; busy?: boolean; blockedNote?: string; children?: ReactNode;
}) {
  const failed = checks.filter(ck => ck.status === 'FAIL');
  const ready = failed.length === 0 && checks.length > 0;
  return (
    <section style={{ border: `1px solid ${ready ? tone.ok.line : c.lineStrong}`, borderRadius: 6,
      background: c.surface, overflow: 'hidden' }}>
      <header style={{ padding: `${s(3)} ${s(4)}`, background: ready ? tone.ok.bg : c.raised,
        borderBottom: `1px solid ${ready ? tone.ok.line : c.line}` }}>
        <div style={{ ...label, color: c.ink, fontSize: 11.5 }}>{title}</div>
        {intro && <div style={{ fontSize: 12, color: c.muted, marginTop: 3 }}>{intro}</div>}
      </header>

      <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
        <CheckList checks={checks} />
        {children}

        {ready ? (
          <div style={{ fontSize: 12.5, color: tone.ok.fg, fontWeight: 600 }}>
            All conditions met — this decision is yours to make.
          </div>
        ) : (
          <div style={{ background: tone.bad.bg, border: `1px solid ${tone.bad.line}`, borderRadius: 5,
            padding: s(3), fontSize: 12.5, color: tone.bad.fg }}>
            <strong>Blocked.</strong>{' '}
            {failed.length > 0
              ? <>Resolve {failed.length === 1 ? 'this' : `these ${failed.length}`}: {failed.map(f => f.label).join(', ')}.</>
              : blockedNote || 'Preconditions have not been evaluated yet.'}
          </div>
        )}

        <button onClick={onAction} disabled={!ready || busy}
          style={{ font: `700 13.5px ${font.ui}`, padding: '12px 18px', borderRadius: 5, border: 'none',
            background: ready && !busy ? c.navy : c.idleBg, color: ready && !busy ? '#fff' : c.faint,
            cursor: ready && !busy ? 'pointer' : 'not-allowed', letterSpacing: '0.02em' }}>
          {busy ? 'Working…' : action}
        </button>
      </div>
    </section>
  );
}

/** A simpler action card for steps that have no multi-check gate in front of them. */
export function ActionCard({ title, body, action, onAction, busy, disabled, danger, note }: {
  title: string; body: ReactNode; action: string; onAction: () => void;
  busy?: boolean; disabled?: boolean; danger?: boolean; note?: ReactNode;
}) {
  const off = disabled || busy;
  return (
    <section style={{ border: `1px solid ${c.line}`, borderRadius: 6, background: c.surface, padding: s(4),
      display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ ...label, color: c.ink, fontSize: 11.5 }}>{title}</div>
      <div style={{ fontSize: 13, color: c.body, lineHeight: 1.6 }}>{body}</div>
      {note}
      <button onClick={onAction} disabled={off}
        style={{ alignSelf: 'flex-start', font: `600 13px ${font.ui}`, padding: '10px 18px', borderRadius: 5,
          border: 'none', background: off ? c.idleBg : danger ? c.bad : c.navy, color: off ? c.faint : '#fff',
          cursor: off ? 'not-allowed' : 'pointer' }}>
        {busy ? 'Working…' : action}
      </button>
    </section>
  );
}
