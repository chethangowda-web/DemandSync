/**
 * The Plotly chart itself. Loaded only via the lazy boundary in DemandChart.tsx, so the ~5 MB Plotly
 * bundle never lands in the initial payload.
 *
 * Four questions are answered without merging them: what beneficiaries asked for (intent), what the
 * model predicts (forecast), and what normally happens (historical baseline). No chart is rendered at
 * all when there is nothing to plot — the caller shows DataUnavailable instead of an empty axis that
 * would read as "zero".
 */
import Plot from 'react-plotly.js';
import { DemandRow } from '../api';
import { c, font } from '../theme';
import { totalsByCommodity } from './DemandSignal';

export function DemandChart({ rows, height = 300 }: { rows: DemandRow[]; height?: number }) {
  const totals = totalsByCommodity(rows);
  const commodities = Object.keys(totals).sort();
  if (!commodities.length) return null;

  const series = [
    { name: 'Historical baseline', key: 'baseline' as const, colour: '#94A3B8' },
    { name: 'Forecast demand', key: 'forecast' as const, colour: '#1D4ED8' },
    { name: 'Beneficiary intent', key: 'intent' as const, colour: '#F5C518' },
  ];

  return (
    <Plot
      data={series.map(sr => ({
        type: 'bar',
        name: sr.name,
        x: commodities,
        y: commodities.map(cm => {
          const v = totals[cm][sr.key];
          return v === null ? null : Number(v);
        }),
        marker: { color: sr.colour },
        hovertemplate: `%{x} · ${sr.name}<br>%{y:,.0f} kg<extra></extra>`,
      }))}
      layout={{
        height,
        barmode: 'group',
        margin: { l: 64, r: 16, t: 8, b: 40 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { family: font.ui, size: 11, color: c.body },
        yaxis: { title: { text: 'kg', standoff: 12 }, gridcolor: c.line, zerolinecolor: c.lineStrong, rangemode: 'tozero' },
        xaxis: { tickfont: { size: 12 } },
        legend: { orientation: 'h', y: -0.18, x: 0, font: { size: 11 } },
        showlegend: true,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
      useResizeHandler
    />
  );
}
