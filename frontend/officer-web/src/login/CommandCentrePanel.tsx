/**
 * The left, brand-side half of the sign-in screen.
 *
 * Its job in the first five seconds: establish that this is government distribution infrastructure
 * operating at national scale. It does that with the real operating geography and the real platform
 * figures -- see platform.ts -- rather than with stock imagery.
 */
import { lc, lfont, eyebrow } from './loginTheme';
import NetworkVisualization from './NetworkVisualization';
import PipelineRail from './PipelineRail';
import SystemStatus from './SystemStatus';
import { Load, Health, Manifest, figuresFrom, provenanceOf } from './platform';
import Wordmark from './Wordmark';

export default function CommandCentrePanel({ health, manifest }:
  { health: Load<Health>; manifest: Load<Manifest> }) {
  const m = manifest.state === 'ready' ? manifest.data : null;
  const figures = figuresFrom(m);
  const provenance = provenanceOf(m);

  return (
    <section className="ds-brand" aria-labelledby="ds-brand-heading">
      <div className="ds-brand-bg" aria-hidden="true">
        <div className="ds-grid" />
        <div className="ds-aurora ds-aurora-a" />
        <div className="ds-aurora ds-aurora-b" />
      </div>

      <div className="ds-brand-inner">
        <header className="ds-rise" style={{ animationDelay: '0.05s' }}>
          <Wordmark />
        </header>

        <div className="ds-brand-mid">
          <div style={{ minWidth: 0 }}>
            <h1 id="ds-brand-heading" className="ds-headline ds-rise" style={{ animationDelay: '0.15s' }}>
              Intelligent distribution.
              <span style={{ display: 'block', color: lc.saffron }}>Stronger food security.</span>
            </h1>
            <p className="ds-lede ds-rise" style={{ animationDelay: '0.25s' }}>
              AI-powered demand intelligence, allocation, logistics and field operations for
              India&rsquo;s Public Distribution System.
            </p>
          </div>

          <figure className="ds-map ds-rise" style={{ animationDelay: '0.3s' }}>
            {manifest.state === 'ready' && m?.operating_geography
              ? <NetworkVisualization geography={m.operating_geography} />
              : (
                <figcaption style={{ ...eyebrow, font: `600 10.5px ${lfont.ui}`, color: lc.onDarkFaint,
                  letterSpacing: '0.14em', textTransform: 'uppercase', textAlign: 'center', padding: 24 }}>
                  {manifest.state === 'loading' ? 'Loading network geography' : 'Network geography unavailable'}
                </figcaption>
              )}
          </figure>
        </div>

        {/* Full-width band: the five stages need the whole panel to sit on one line. */}
        <div className="ds-rise" style={{ animationDelay: '0.45s' }}>
          <PipelineRail />
        </div>

        <div className="ds-brand-foot">
          <dl className="ds-figures ds-rise" style={{ animationDelay: '0.55s' }}>
            {figures.map(f => (
              <div key={f.label} className="ds-figure">
                <dt style={{ ...eyebrow, font: `700 10px ${lfont.ui}`, letterSpacing: '0.14em',
                  textTransform: 'uppercase', color: lc.onDarkMuted }}>
                  {f.label}
                </dt>
                <dd className="ds-figure-value">
                  {f.value ?? <span className="ds-figure-none">Unavailable</span>}
                </dd>
                <dd className="ds-figure-caption">{f.value ? f.caption : 'Not published by the platform'}</dd>
              </div>
            ))}
          </dl>

          <div className="ds-brand-meta">
            <SystemStatus health={health} />
            <span className="ds-sep" aria-hidden="true" />
            <span style={{ ...eyebrow, font: `700 10.5px ${lfont.ui}`, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: lc.onDarkMuted }}>
              Secure government operations platform
            </span>
          </div>

          {provenance && (
            <p className="ds-provenance" title="Source of the figures shown above">
              Figures from {provenance}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
