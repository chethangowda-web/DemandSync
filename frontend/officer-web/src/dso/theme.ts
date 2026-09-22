/**
 * Design tokens for the DSO Control Centre.
 *
 * Government-operational, not consumer-SaaS: a navy/slate foundation, restrained status colour used
 * only to carry meaning (never decoration), small radii, hairline borders, and a dense but legible
 * type scale. Status colours are chosen for contrast against both white surfaces and their own tints.
 */
export const c = {
  navy: '#0B2545',
  navyDeep: '#071A31',
  navyLine: '#17385C',
  ink: '#0F172A',
  body: '#334155',
  muted: '#64748B',
  faint: '#94A3B8',
  line: '#E2E8F0',
  lineStrong: '#CBD5E1',
  surface: '#FFFFFF',
  canvas: '#F1F5F9',
  raised: '#F8FAFC',

  ok: '#15803D',
  okBg: '#F0FDF4',
  okLine: '#BBF7D0',
  warn: '#B45309',
  warnBg: '#FFFBEB',
  warnLine: '#FDE68A',
  bad: '#B91C1C',
  badBg: '#FEF2F2',
  badLine: '#FECACA',
  idle: '#64748B',
  idleBg: '#F1F5F9',
  idleLine: '#E2E8F0',
  accent: '#1D4ED8',
  accentBg: '#EFF6FF',
} as const;

export const font = {
  ui: "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
  mono: "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace",
} as const;

/** 4px spacing scale. */
export const s = (n: number) => `${n * 4}px`;

/** Small uppercase section/field label. */
export const label: React.CSSProperties = {
  fontSize: 10.5, fontWeight: 700, letterSpacing: '0.09em', textTransform: 'uppercase', color: c.muted,
};

export const panel: React.CSSProperties = {
  background: c.surface, border: `1px solid ${c.line}`, borderRadius: 6,
};

export const panelPad: React.CSSProperties = { ...panel, padding: s(4) };

export const btn: React.CSSProperties = {
  font: `600 13px ${font.ui}`, padding: '9px 16px', borderRadius: 5, border: `1px solid ${c.navy}`,
  background: c.navy, color: '#fff', cursor: 'pointer',
};

export const btnGhost: React.CSSProperties = {
  ...btn, background: c.surface, color: c.navy,
};

export const btnSmall: React.CSSProperties = {
  ...btnGhost, padding: '4px 10px', fontSize: 11.5, borderColor: c.lineStrong, color: c.body,
};

export const btnDisabled: React.CSSProperties = {
  ...btn, background: c.idleBg, color: c.faint, borderColor: c.line, cursor: 'not-allowed',
};

/** Status colour triple for a semantic state. */
export type Tone = 'ok' | 'warn' | 'bad' | 'idle' | 'accent';
export const tone: Record<Tone, { fg: string; bg: string; line: string }> = {
  ok: { fg: c.ok, bg: c.okBg, line: c.okLine },
  warn: { fg: c.warn, bg: c.warnBg, line: c.warnLine },
  bad: { fg: c.bad, bg: c.badBg, line: c.badLine },
  idle: { fg: c.idle, bg: c.idleBg, line: c.idleLine },
  accent: { fg: c.accent, bg: c.accentBg, line: '#BFDBFE' },
};

/** Maps a backend status string to a tone. Unknown values stay neutral rather than guessing. */
export function toneFor(status: string | null | undefined): Tone {
  switch ((status || '').toUpperCase()) {
    case 'APPROVED': case 'VERIFIED': case 'READY': case 'LOCKED': case 'DELIVERED': case 'CLOSED':
    case 'AVAILABLE': case 'RECONCILED': case 'SUCCESS': case 'ACTIVE': case 'PASS':
      return 'ok';
    case 'BLOCKED': case 'REJECTED': case 'FAILED': case 'HIGH': case 'CRITICAL': case 'FAIL':
      return 'bad';
    case 'VARIANCE': case 'MEDIUM': case 'ACTION_REQUIRED': case 'MAINTENANCE': case 'PARTIAL':
      return 'warn';
    case 'DRAFT': case 'VALIDATED': case 'DISPATCHED': case 'IN_TRANSIT': case 'OPEN': case 'ASSIGNED':
      return 'accent';
    default:
      return 'idle';
  }
}

/** kg with thousands separators; null-safe so callers can pass a possibly-absent figure straight in. */
export const kg = (v: number | null | undefined, unit = ' kg') =>
  v === null || v === undefined ? '—' : `${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 1 })}${unit}`;

export const num = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 1 });

export const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${v}%`;

export const clock = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
};

export const dateTime = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
};
