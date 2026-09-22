/**
 * Exception Command Centre and its detail drawer.
 *
 * This replaces the raw JSON dump the earlier screen showed. Two things matter here:
 *
 *  1. Scope. The seeded dataset carries its own historical exceptions for every cycle (entity_type
 *     DELIVERY/EPOS/MANIFEST). Those are not this workflow's business, so callers pass entity_type and
 *     the counts shown reflect what the officer can actually act on — not a five-figure number that
 *     makes 2 real problems look like 1,553.
 *  2. Translation. A rule_code is a backend identifier; the officer is shown what it means, what it
 *     blocks, and what can be done about it.
 */
import { useState } from 'react';
import { Allocation, Exception, dso } from '../api';
import { c, font, kg, label, s, Tone } from '../theme';
import { Badge, Drawer, Evidence, Facts, Table, td, tdMono } from '../ui';

/** Officer-facing translation of each gate this workflow can raise. */
const RULES: Record<string, { title: string; means: string; fix: string; overridable: boolean }> = {
  FPS_CAPACITY_EXCEEDED: {
    title: 'FPS storage capacity exceeded',
    means: 'The quantity this shop is due cannot physically fit in its recorded storage capacity.',
    fix: 'Correct the capacity figure if it is stale, or override to deliver the legally required quantity anyway.',
    overridable: true,
  },
  WAREHOUSE_STOCK_SHORTFALL: {
    title: 'Warehouse stock shortfall',
    means: 'The serving warehouse does not hold enough of this commodity to cover everything committed this cycle.',
    fix: 'Arrange replenishment, or accept a reduced allocation for this shop. Stock is a hard physical limit.',
    overridable: false,
  },
  WAREHOUSE_TRUCK_CAPACITY_SHORTFALL: {
    title: 'Vehicle capacity shortfall',
    means: 'The vehicles based at this warehouse cannot carry everything committed to it this cycle.',
    fix: 'Free up or reassign vehicles before optimisation, or expect some stops to go unrouted.',
    overridable: true,
  },
  ROUTE_NOT_FEASIBLE: {
    title: 'Shop not reachable',
    means: 'This FPS is not ACTIVE, or has no coordinates on file, so no route can be planned to it.',
    fix: 'Reactivate the shop or correct its location record. It will not be routed until then.',
    overridable: true,
  },
  BELOW_NFSA_ENTITLEMENT_FLOOR: {
    title: 'Below NFSA entitlement floor',
    means: 'Submitted intent is below what this shop’s active beneficiaries are legally entitled to; the engine raised the proposal to the floor.',
    fix: 'No action usually required — this is the system protecting entitlement. The floor can never be overridden downward.',
    overridable: false,
  },
  ALLOCATION_BELOW_DEMAND: {
    title: 'Allocation below locked demand',
    means: 'A physical constraint forced the allocation below what was requested.',
    fix: 'Resolve the constraint that caused the clamp, or accept the shortfall knowingly.',
    overridable: true,
  },
  NO_VEHICLE_AVAILABLE: {
    title: 'No vehicle available',
    means: 'No AVAILABLE vehicle is based at the warehouse serving this shop, so it could not be routed.',
    fix: 'Return a vehicle to AVAILABLE status and re-run optimisation on a later cycle.',
    overridable: false,
  },
  INSUFFICIENT_FLEET_CAPACITY: {
    title: 'Fleet cannot cover this stop',
    means: 'After routing every other stop, the available fleet had no remaining capacity for this one.',
    fix: 'Add fleet capacity at this warehouse. The stop was left unmanifested rather than silently dropped.',
    overridable: false,
  },
};

export function ruleInfo(code: string) {
  return RULES[code] ?? {
    title: code.replace(/_/g, ' ').toLowerCase().replace(/^./, (m) => m.toUpperCase()),
    means: 'A closure or validation check recorded by the workflow.',
    fix: 'Resolve the underlying condition, then re-run the step that raised it.',
    overridable: false,
  };
}

const sevTone = (s: string): Tone => (s === 'HIGH' ? 'bad' : s === 'MEDIUM' ? 'warn' : 'idle');

/** Severity counters across the supplied (already scoped) exception set. */
export function SeverityStrip({ exceptions }: { exceptions: Exception[] }) {
  const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 } as Record<string, number>;
  exceptions.forEach(e => { counts[e.severity] = (counts[e.severity] ?? 0) + 1; });
  const cells: { name: string; n: number; t: Tone }[] = [
    { name: 'Critical', n: counts.HIGH, t: 'bad' },
    { name: 'Medium', n: counts.MEDIUM, t: 'warn' },
    { name: 'Low', n: counts.LOW, t: 'idle' },
  ];
  return (
    <div style={{ display: 'flex', gap: s(3) }}>
      {cells.map(x => (
        <div key={x.name} style={{ flex: 1, border: `1px solid ${c.line}`, borderRadius: 5, padding: s(3),
          background: x.n > 0 ? undefined : c.raised }}>
          <div style={{ ...label }}>{x.name}</div>
          <div style={{ font: `700 22px ${font.ui}`, color: x.n > 0 ? (x.t === 'bad' ? c.bad : x.t === 'warn' ? c.warn : c.muted) : c.faint, marginTop: 2 }}>{x.n}</div>
        </div>
      ))}
    </div>
  );
}

export function ExceptionTable({ exceptions, onSelect, maxHeight = 420 }:
  { exceptions: Exception[]; onSelect: (e: Exception) => void; maxHeight?: number }) {
  return (
    <Table head={['Severity', 'Exception', 'Entity', 'Status', '']} maxHeight={maxHeight}>
      {exceptions.map(e => {
        const info = ruleInfo(e.rule_code);
        return (
          <tr key={e.exception_id} onClick={() => onSelect(e)} style={{ cursor: 'pointer' }}
            onMouseEnter={ev => (ev.currentTarget.style.background = c.raised)}
            onMouseLeave={ev => (ev.currentTarget.style.background = 'transparent')}>
            <td style={td}><Badge t={sevTone(e.severity)}>{e.severity}</Badge></td>
            <td style={td}>
              <div style={{ color: c.ink, fontWeight: 600 }}>{info.title}</div>
              <div style={{ fontSize: 11, color: c.faint, fontFamily: font.mono }}>{e.rule_code}</div>
            </td>
            <td style={tdMono}>{e.entity_id}</td>
            <td style={td}><Badge>{e.status}</Badge></td>
            <td style={{ ...td, textAlign: 'right', color: c.accent, fontWeight: 600, whiteSpace: 'nowrap' }}>Review →</td>
          </tr>
        );
      })}
    </Table>
  );
}

/** Splits "FPS-0244:RICE" into its parts; anything else is left alone. */
function parseEntity(entityId: string): { fps: string | null; commodity: string | null } {
  const m = /^(FPS-[\w-]+):(RICE|WHEAT)$/.exec(entityId);
  return m ? { fps: m[1], commodity: m[2] } : { fps: /^FPS-/.test(entityId) ? entityId : null, commodity: null };
}

export function ExceptionDrawer({ exception, cycle, allocation, onClose, onResolved }:
  { exception: Exception | null; cycle: string; allocation?: Allocation; onClose: () => void; onResolved: () => void }) {
  const [kgValue, setKgValue] = useState<string>('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<'view' | 'override'>('view');

  if (!exception) return null;
  const info = ruleInfo(exception.rule_code);
  const { fps, commodity } = parseEntity(exception.entity_id);
  const canOverride = info.overridable && fps && commodity && allocation;

  const submit = async () => {
    if (!fps || !commodity) return;
    setBusy(true); setErr(null);
    try {
      await dso.override(cycle, fps, commodity, Number(kgValue), reason.trim());
      setMode('view'); setReason(''); onResolved(); onClose();
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer open onClose={onClose} title={info.title}
      subtitle={<span style={{ fontFamily: font.mono }}>{exception.rule_code} · {exception.entity_id}</span>}>

      <div style={{ display: 'flex', gap: s(2) }}>
        <Badge t={sevTone(exception.severity)}>{exception.severity}</Badge>
        <Badge>{exception.status}</Badge>
        {allocation && <Badge>{allocation.status}</Badge>}
      </div>

      <div>
        <div style={{ ...label, marginBottom: 6 }}>Why this is flagged</div>
        <p style={{ margin: 0, fontSize: 13, color: c.body, lineHeight: 1.65 }}>{info.means}</p>
      </div>

      <Evidence source="exceptions (recorded by the constraint engine at allocation time)">
        {exception.reason}
      </Evidence>

      {allocation && (
        <div>
          <div style={{ ...label, marginBottom: 6 }}>Current allocation</div>
          <Facts items={[
            ['Requested', kg(allocation.requested_kg)],
            ['Allocated', kg(allocation.allocated_kg)],
            ['Warehouse', allocation.warehouse_id],
            ['Source', allocation.source || '—'],
            ['Status', <Badge key="s">{allocation.status}</Badge>],
          ]} />
        </div>
      )}

      <div>
        <div style={{ ...label, marginBottom: 6 }}>Recommended action</div>
        <p style={{ margin: 0, fontSize: 13, color: c.body, lineHeight: 1.65 }}>{info.fix}</p>
      </div>

      {err && <div style={{ background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad,
        padding: s(3), borderRadius: 5, fontSize: 12.5 }}>{err}</div>}

      {mode === 'view' ? (
        canOverride ? (
          <button onClick={() => { setKgValue(String(allocation!.allocated_kg)); setMode('override'); }}
            style={{ font: `600 13px ${font.ui}`, padding: '10px 16px', borderRadius: 5, border: 'none',
              background: c.navy, color: '#fff', cursor: 'pointer' }}>
            Apply audited override
          </button>
        ) : (
          <div style={{ fontSize: 12.5, color: c.muted, background: c.raised, border: `1px solid ${c.line}`,
            borderRadius: 5, padding: s(3), lineHeight: 1.6 }}>
            {info.overridable
              ? 'This exception is not tied to a single allocation, so it cannot be overridden from here.'
              : 'This condition cannot be overridden — it is a legal floor or a physical limit, not officer discretion.'}
          </div>
        )
      ) : (
        <div style={{ border: `1px solid ${c.lineStrong}`, borderRadius: 5, padding: s(4), background: c.raised,
          display: 'flex', flexDirection: 'column', gap: s(3) }}>
          <div style={{ ...label, color: c.ink }}>Audited override</div>
          <Facts items={[
            ['Before', kg(allocation!.allocated_kg)],
            ['After', <input key="i" type="number" value={kgValue} onChange={e => setKgValue(e.target.value)}
              style={{ width: 130, padding: '5px 8px', border: `1px solid ${c.lineStrong}`, borderRadius: 4,
                font: `600 13px ${font.mono}` }} />],
          ]} />
          <div>
            <div style={{ ...label, marginBottom: 5 }}>Reason (required, recorded in the audit trail)</div>
            <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3}
              placeholder="Why is this override justified?"
              style={{ width: '100%', padding: s(2), border: `1px solid ${c.lineStrong}`, borderRadius: 4,
                font: `400 13px ${font.ui}`, resize: 'vertical', boxSizing: 'border-box' }} />
          </div>
          <div style={{ fontSize: 11.5, color: c.muted, lineHeight: 1.55 }}>
            This records your officer ID, the before and after values, your reason and a timestamp against the
            immutable audit chain. It cannot be edited afterwards.
          </div>
          <div style={{ display: 'flex', gap: s(2) }}>
            <button disabled={busy || !reason.trim() || kgValue === ''} onClick={submit}
              style={{ font: `600 13px ${font.ui}`, padding: '9px 16px', borderRadius: 5, border: 'none',
                background: !reason.trim() || kgValue === '' ? c.lineStrong : c.navy,
                color: !reason.trim() || kgValue === '' ? c.faint : '#fff',
                cursor: !reason.trim() || kgValue === '' ? 'not-allowed' : 'pointer' }}>
              {busy ? 'Recording…' : 'Confirm override'}
            </button>
            <button onClick={() => setMode('view')} style={{ font: `600 13px ${font.ui}`, padding: '9px 16px',
              borderRadius: 5, border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.body, cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </Drawer>
  );
}
