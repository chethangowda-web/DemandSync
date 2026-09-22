/**
 * The five stages of the PDS cycle, named exactly as the platform's own routes name them.
 *
 * This is the spine of the product -- Demand -> Allocation -> Logistics -> Distribution -> Beneficiary --
 * so it is stated once, plainly, rather than implied by decoration.
 */
import { lc, lfont } from './loginTheme';

const STAGES = [
  { key: 'demand', name: 'Demand', sub: 'Forecasting' },
  { key: 'allocation', name: 'Allocation', sub: 'Planning' },
  { key: 'logistics', name: 'Logistics', sub: 'Transportation' },
  { key: 'distribution', name: 'Distribution', sub: 'FPS network' },
  { key: 'beneficiary', name: 'Beneficiary', sub: 'Food security' },
];

export default function PipelineRail() {
  return (
    <ol className="ds-pipeline" aria-label="Distribution pipeline">
      {STAGES.map((s, i) => (
        <li key={s.key} className="ds-stage ds-rise" style={{ animationDelay: `${0.5 + i * 0.07}s` }}>
          <span className="ds-stage-dot" aria-hidden="true" />
          <span style={{ display: 'block', font: `600 12px ${lfont.ui}`, color: lc.onDark, whiteSpace: 'nowrap' }}>
            {s.name}
          </span>
          <span style={{ display: 'block', font: `500 10.5px ${lfont.ui}`, color: lc.onDarkMuted, marginTop: 1, whiteSpace: 'nowrap' }}>
            {s.sub}
          </span>
        </li>
      ))}
    </ol>
  );
}
