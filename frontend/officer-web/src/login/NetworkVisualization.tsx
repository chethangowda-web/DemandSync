/**
 * The distribution network, drawn from real coordinates.
 *
 * Every district node is placed by projecting the lat/lon the backend publishes in
 * `operating_geography` (manifest) onto the viewBox -- this is the actual operating geography, not a
 * decorative scatter. Warehouse and FPS nodes are derived positions around their district, shown to
 * convey tier and fan-out; they are not claimed to be individual real shops, and nothing is labelled
 * as though it were.
 *
 * Until the manifest resolves, the map renders nothing rather than inventing placeholder geography.
 */
import { useMemo } from 'react';
import { lc, lfont } from './loginTheme';

interface Props { geography: Record<string, { lat: number; lon: number }> | null }

const W = 520;
const H = 560;
const PAD_X = 74;
/** Room above the districts for the state tier and its label, and below for the FPS fan-out. */
const PAD_TOP = 112;
const PAD_BOTTOM = 62;
const HUB_Y = 44;

const titleCase = (k: string) =>
  k.toLowerCase().split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

export default function NetworkVisualization({ geography }: Props) {
  const nodes = useMemo(() => {
    const entries = Object.entries(geography ?? {});
    if (entries.length === 0) return [];
    const lats = entries.map(([, v]) => v.lat);
    const lons = entries.map(([, v]) => v.lon);
    const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
    const [minLon, maxLon] = [Math.min(...lons), Math.max(...lons)];
    // Equirectangular, aspect-corrected at the mean latitude, then fitted to the box with uniform
    // scale so the geography is not stretched.
    const midLat = (minLat + maxLat) / 2;
    const kx = Math.cos((midLat * Math.PI) / 180);
    const spanX = Math.max((maxLon - minLon) * kx, 1e-6);
    const spanY = Math.max(maxLat - minLat, 1e-6);
    const boxW = W - PAD_X * 2;
    const boxH = H - PAD_TOP - PAD_BOTTOM;
    const scale = Math.min(boxW / spanX, boxH / spanY);
    const offX = (W - spanX * scale) / 2;
    const offY = PAD_TOP + (boxH - spanY * scale) / 2;
    return entries.map(([name, v], i) => ({
      name,
      label: titleCase(name),
      x: offX + (v.lon - minLon) * kx * scale,
      y: offY + (maxLat - v.lat) * scale, // latitude increases northward, y increases downward
      i,
    }));
  }, [geography]);

  if (nodes.length === 0) return null;

  // The state tier sits above the districts it allocates to, inside the reserved top band so its
  // label can never spill out of the viewBox and collide with whatever is stacked above the map.
  const hub = { x: nodes.reduce((a, n) => a + n.x, 0) / nodes.length, y: HUB_Y };

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="ds-net"
      role="img"
      aria-label={`Distribution network across ${nodes.length} operating districts: state allocation flowing to district, Fair Price Shop network and beneficiaries.`}
      style={{ width: '100%', height: '100%' }}
    >
      <defs>
        <radialGradient id="ds-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={lc.sky} stopOpacity="0.30" />
          <stop offset="100%" stopColor={lc.sky} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ds-link" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lc.sky} stopOpacity="0.55" />
          <stop offset="100%" stopColor={lc.sky} stopOpacity="0.12" />
        </linearGradient>
      </defs>

      <circle cx={hub.x} cy={hub.y} r="150" fill="url(#ds-glow)" />

      {/* State -> district allocation paths. */}
      <g fill="none" stroke="url(#ds-link)" strokeWidth="1.1">
        {nodes.map(n => {
          const d = `M ${hub.x} ${hub.y} C ${hub.x} ${(hub.y + n.y) / 2}, ${n.x} ${(hub.y + n.y) / 2}, ${n.x} ${n.y}`;
          return (
            <g key={`l-${n.name}`}>
              <path d={d} />
              <path d={d} className="ds-flow" stroke={lc.saffron} strokeWidth="1.6" strokeLinecap="round"
                strokeDasharray="3 150" style={{ animationDelay: `${n.i * 0.85}s` }} />
            </g>
          );
        })}
      </g>

      {/* District tier, and the FPS fan-out beneath each one. */}
      {nodes.map(n => (
        <g key={n.name}>
          <g stroke={lc.sky} strokeOpacity="0.22" strokeWidth="0.8">
            {[-30, -10, 10, 30].map(dx => (
              <line key={dx} x1={n.x} y1={n.y} x2={n.x + dx * 0.9} y2={n.y + 34} />
            ))}
          </g>
          {[-30, -10, 10, 30].map((dx, k) => (
            <circle key={dx} cx={n.x + dx * 0.9} cy={n.y + 34} r="1.9" fill={lc.sky} fillOpacity="0.5"
              className="ds-pulse" style={{ animationDelay: `${n.i * 0.4 + k * 0.22}s` }} />
          ))}
          <circle cx={n.x} cy={n.y} r="13" fill={lc.sky} fillOpacity="0.10" className="ds-halo"
            style={{ animationDelay: `${n.i * 0.7}s` }} />
          <circle cx={n.x} cy={n.y} r="5.2" fill={lc.navy} stroke={lc.saffron} strokeWidth="1.7" />
          <text x={n.x} y={n.y - 17} textAnchor="middle"
            style={{ font: `600 10px ${lfont.ui}`, letterSpacing: '0.07em', fill: lc.onDarkBody }}>
            {n.label}
          </text>
        </g>
      ))}

      {/* State tier. */}
      <circle cx={hub.x} cy={hub.y} r="9.5" fill={lc.saffron} />
      <circle cx={hub.x} cy={hub.y} r="17" fill="none" stroke={lc.saffron} strokeOpacity="0.4" className="ds-halo" />
      <text x={hub.x} y={hub.y - 27} textAnchor="middle"
        style={{ font: `700 10px ${lfont.ui}`, letterSpacing: '0.16em', fill: lc.onDark }}>
        STATE
      </text>
    </svg>
  );
}
