/**
 * The status lamp. Reflects GET /health -- including its real database probe -- and nothing else.
 *
 * "Operational" is only ever shown when the API reports status ok *and* the database is connected.
 * A reachable API sitting on an unreachable database is a degraded platform, and an officer about to
 * sign in deserves to know that before they try, not after.
 */
import { lc, lfont, eyebrow } from './loginTheme';
import { Load, Health } from './platform';

export default function SystemStatus({ health }: { health: Load<Health> }) {
  const view = (() => {
    if (health.state === 'loading') return { colour: lc.onDarkMuted, text: 'Checking platform status', live: false };
    if (health.state === 'unavailable') return { colour: lc.bad, text: 'Platform status unavailable', live: false };
    const { status, database } = health.data;
    if (status === 'ok' && database === 'connected') return { colour: lc.live, text: 'System operational', live: true };
    if (status === 'ok') return { colour: lc.warn, text: `Degraded · database ${database.replace(/_/g, ' ')}`, live: false };
    return { colour: lc.bad, text: `Platform reporting ${status}`, live: false };
  })();

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
      <span
        className={view.live ? 'ds-lamp' : undefined}
        style={{ width: 8, height: 8, borderRadius: '50%', background: view.colour, flexShrink: 0,
          ['--ds-lamp' as string]: view.colour }}
      />
      <span role="status" style={{ ...eyebrow, font: `700 10.5px ${lfont.ui}`, letterSpacing: '0.16em',
        textTransform: 'uppercase', color: view.live ? lc.onDarkBody : view.colour }}>
        {view.text}
      </span>
    </div>
  );
}
