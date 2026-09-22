/**
 * Lazy boundary around the Plotly chart.
 *
 * Plotly dominates the bundle (~5 MB unminified), so it is loaded on demand: the control centre shell
 * stays light for officers on constrained connections and the chart arrives a moment later behind an
 * explicit placeholder rather than a silent gap.
 *
 * The numeric interpretation lives in DemandSignal, which has no Plotly dependency and therefore
 * renders immediately — the figures an officer needs are never gated on a chart bundle downloading.
 */
import { lazy, Suspense } from 'react';
import { DemandRow } from '../api';
import { c, label } from '../theme';

const Impl = lazy(() => import('./DemandChartImpl').then(m => ({ default: m.DemandChart })));

export function DemandChart({ rows, height = 300 }: { rows: DemandRow[]; height?: number }) {
  return (
    <Suspense fallback={
      <div style={{ height, display: 'grid', placeItems: 'center', border: `1px solid ${c.line}`,
        borderRadius: 5, background: c.raised }}>
        <span style={{ ...label, color: c.faint }}>Loading chart…</span>
      </div>
    }>
      <Impl rows={rows} height={height} />
    </Suspense>
  );
}
