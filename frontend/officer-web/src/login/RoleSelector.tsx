/**
 * Officer role directory.
 *
 * Read this before changing it: POST /api/v1/auth/officer/login takes an officer ID and a password
 * and *nothing else*. The role comes back from the server, resolved from the officer's own record
 * (backend/core/rbac.py), and the portal the officer lands in is server-decided. So this control is
 * deliberately NOT an authentication input -- wiring it into the credentials would either be ignored
 * by the API or, worse, imply a client-side access decision that does not exist.
 *
 * What it honestly is: a directory of the five officer portals that tailors the form's helper copy
 * and tells the officer where they are headed. It is announced as such to screen readers, and the
 * card states plainly that the officer record is what actually governs access.
 *
 * Role identifiers are taken from PORTAL_ROLE so they cannot drift from the routing table.
 */
import { KeyboardEvent, useRef } from 'react';
import { PORTAL_ROLE } from '../auth/AuthContext';
import { lc, lfont } from './loginTheme';

export interface RoleCard {
  /** Canonical role identifier, e.g. 'DSO' -- matches backend Role. */
  id: string;
  portal: string;
  name: string;
  remit: string;
  focus: string;
  icon: (p: { colour: string }) => JSX.Element;
}

const stroke = (colour: string) => ({
  fill: 'none', stroke: colour, strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
});

/** Icons are drawn to the remit, not to generic "user" shapes. */
const ICONS: Record<string, (p: { colour: string }) => JSX.Element> = {
  DSO: ({ colour }) => (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...stroke(colour)}>
      <path d="M3 20h18" /><path d="M6 20V10l6-4 6 4v10" /><path d="M10 20v-5h4v5" /><path d="M12 3v1.6" />
    </svg>
  ),
  FIELD_FOOD_INSPECTOR: ({ colour }) => (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...stroke(colour)}>
      <circle cx="11" cy="11" r="6" /><path d="M15.5 15.5 21 21" /><path d="M8.6 11l1.7 1.8 3.2-3.4" />
    </svg>
  ),
  FPS_OWNER: ({ colour }) => (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...stroke(colour)}>
      <path d="M4 10v10h16V10" /><path d="M3 10l1.6-5h14.8L21 10z" /><path d="M9 20v-6h6v6" />
    </svg>
  ),
  AUDITOR: ({ colour }) => (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...stroke(colour)}>
      <path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 12h6" /><path d="M9 16h4" />
    </svg>
  ),
  SYSTEM_ADMIN: ({ colour }) => (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...stroke(colour)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.2M12 18.8V21M21 12h-2.2M5.2 12H3M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6M18.4 18.4l-1.6-1.6M7.2 7.2 5.6 5.6" />
    </svg>
  ),
};

const META: Record<string, { name: string; remit: string; focus: string }> = {
  DSO: { name: 'DSO', remit: 'District Supply Officer', focus: 'Command & allocation' },
  FIELD_FOOD_INSPECTOR: { name: 'Field Food Inspector', remit: 'Field operations', focus: 'Inspection & verification' },
  FPS_OWNER: { name: 'FPS Owner', remit: 'Fair Price Shop operations', focus: 'Inventory & e-PoS' },
  AUDITOR: { name: 'Auditor', remit: 'Independent oversight', focus: 'Audit trail & assurance' },
  SYSTEM_ADMIN: { name: 'System Admin', remit: 'Platform administration', focus: 'Security & system health' },
};

/** Built from the routing table so a new portal shows up here automatically. */
export const ROLES: RoleCard[] = Object.entries(PORTAL_ROLE)
  .map(([portal, id]) => ({ id, portal, ...META[id], icon: ICONS[id] }))
  .filter(r => r.name && r.icon)
  .sort((a, b) => Object.keys(META).indexOf(a.id) - Object.keys(META).indexOf(b.id));

export default function RoleSelector({ value, onChange, disabled }:
  { value: string | null; onChange: (id: string | null) => void; disabled?: boolean }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  // Roving focus, as a radiogroup should: arrows move and select, space/enter toggles off.
  const onKeyDown = (e: KeyboardEvent, i: number) => {
    const delta = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1
      : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const next = (i + delta + ROLES.length) % ROLES.length;
    onChange(ROLES[next].id);
    refs.current[next]?.focus();
  };

  const selectedIndex = ROLES.findIndex(r => r.id === value);

  return (
    <div
      role="radiogroup"
      aria-label="Officer portal — optional, for guidance only; your actual access is set by your officer record"
      className="ds-roles"
    >
      {ROLES.map((r, i) => {
        const on = r.id === value;
        const Icon = r.icon;
        return (
          <button
            key={r.id}
            ref={el => { refs.current[i] = el; }}
            type="button"
            role="radio"
            aria-checked={on}
            disabled={disabled}
            // Roving tabindex: the group is one tab stop.
            tabIndex={on || (selectedIndex === -1 && i === 0) ? 0 : -1}
            onClick={() => onChange(on ? null : r.id)}
            onKeyDown={e => onKeyDown(e, i)}
            className={`ds-role${on ? ' is-on' : ''}`}
          >
            <span className="ds-role-icon" aria-hidden="true">
              <Icon colour={on ? lc.gov : lc.muted} />
            </span>
            <span className="ds-role-text">
              <span style={{ display: 'block', font: `700 11.5px ${lfont.ui}`, color: on ? lc.gov : lc.ink,
                letterSpacing: '0.02em' }}>
                {r.name}
              </span>
              <span style={{ display: 'block', font: `500 10.5px ${lfont.ui}`, color: lc.muted, marginTop: 2,
                lineHeight: 1.35 }}>
                {r.remit}
              </span>
            </span>
            <span className="ds-role-check" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="13" height="13" {...stroke('#fff')}><path d="m5 12.5 4.5 4.5L19 7" /></svg>
            </span>
          </button>
        );
      })}
    </div>
  );
}
