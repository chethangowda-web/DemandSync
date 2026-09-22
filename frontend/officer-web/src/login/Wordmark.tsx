/**
 * Departmental lockup and the DemandSYNC mark.
 *
 * The repository ships no branding assets, and the State Emblem of India is not something to
 * approximate by hand -- its use is restricted under the State Emblem of India (Prohibition of
 * Improper Use) Act, 2005. So the insignia here is an original mark (a chakra-derived ring around a
 * grain form, for food distribution), and the departmental identification is set in type.
 *
 * To drop in the official artwork later: put the file in `public/` and replace <Insignia /> with an
 * <img>. Nothing else on the screen depends on the mark's internals.
 */
import { lc, lfont } from './loginTheme';

export function Insignia({ size = 34, tint = lc.saffron, ring = lc.onDarkBody }:
  { size?: number; tint?: string; ring?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <circle cx="24" cy="24" r="22" fill="none" stroke={ring} strokeOpacity="0.45" strokeWidth="1.2" />
      {/* Chakra-derived spokes: a rhythm mark, not a reproduction of any official emblem. */}
      <g stroke={ring} strokeOpacity="0.32" strokeWidth="1">
        {Array.from({ length: 16 }, (_, i) => {
          const a = (i * Math.PI * 2) / 16;
          return <line key={i} x1={24 + Math.cos(a) * 17} y1={24 + Math.sin(a) * 17}
            x2={24 + Math.cos(a) * 21} y2={24 + Math.sin(a) * 21} />;
        })}
      </g>
      {/* Grain form. */}
      <path d="M24 10 C29.5 15 32 20 32 25 C32 31 28.5 36 24 39 C19.5 36 16 31 16 25 C16 20 18.5 15 24 10 Z"
        fill={tint} fillOpacity="0.18" stroke={tint} strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M24 13 V37" stroke={tint} strokeWidth="1.3" strokeLinecap="round" />
      <g stroke={tint} strokeOpacity="0.75" strokeWidth="1.1" strokeLinecap="round">
        <path d="M24 20 L19.5 24" /><path d="M24 20 L28.5 24" />
        <path d="M24 26 L19.5 30" /><path d="M24 26 L28.5 30" />
      </g>
    </svg>
  );
}

/** Government identification. `tone` switches it for the dark brand panel or the light access card. */
export function GovernmentLockup({ tone = 'dark', size = 34 }: { tone?: 'dark' | 'light'; size?: number }) {
  const strong = tone === 'dark' ? lc.onDark : lc.ink;
  const soft = tone === 'dark' ? lc.onDarkMuted : lc.muted;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
      <Insignia size={size} tint={lc.saffron} ring={tone === 'dark' ? lc.onDarkBody : lc.gov} />
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: `600 12px ${lfont.ui}`, color: strong, letterSpacing: '0.01em' }}>
          Government of India
        </span>
        <span style={{ display: 'block', font: `500 11px ${lfont.ui}`, color: soft, marginTop: 1 }}>
          Department of Food &amp; Public Distribution
        </span>
      </span>
    </div>
  );
}

/** The product lockup used at the top of the brand panel. */
export default function Wordmark() {
  return (
    <div className="ds-wordmark">
      <GovernmentLockup tone="dark" size={34} />
      <span className="ds-wordmark-rule" aria-hidden="true" />
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: `700 19px ${lfont.ui}`, color: lc.onDark, letterSpacing: '-0.01em' }}>
          PDS <span style={{ color: lc.saffron }}>DemandSYNC</span>
        </span>
        <span style={{ display: 'block', font: `500 10.5px ${lfont.ui}`, color: lc.onDarkMuted,
          letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>
          Public Distribution System Intelligence Platform
        </span>
      </span>
    </div>
  );
}
