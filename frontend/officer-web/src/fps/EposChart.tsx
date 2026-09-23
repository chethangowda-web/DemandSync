// e-PoS transaction activity chart. Loaded only via a lazy boundary, so the Plotly
// bundle never lands in the initial payload. Renders nothing when there is no data.
import Plot from 'react-plotly.js';
import { c, font } from '../dso/theme';

export function EposChart({ byHour, byDay }: { byHour: any[]; byDay: any[] }) {
  const hours = (byHour || []).map(r => `${r.hour}:00`);
  const counts = (byHour || []).map(r => r.n);
  if (!hours.length) return null;
  return (
    <Plot
      data={[
        {
          type: 'bar',
          name: 'Transactions by hour',
          x: hours,
          y: counts,
          marker: { color: '#1D4ED8' },
          hovertemplate: `%{x} · %{y} transactions<extra></extra>`,
        },
      ]}
      layout={{
        height: 240,
        margin: { l: 48, r: 16, t: 8, b: 40 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { family: font.ui, size: 11, color: c.body },
        yaxis: { title: { text: 'transactions', standoff: 12 }, gridcolor: c.line, zerolinecolor: c.lineStrong, rangemode: 'tozero' },
        xaxis: { title: { text: 'hour of day', standoff: 12 } },
        showlegend: false,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}

export function EposDailyChart({ byDay }: { byDay: any[] }) {
  const days = (byDay || []).map(r => r.d);
  const ok = (byDay || []).map(r => r.success);
  const fail = (byDay || []).map(r => r.failed);
  if (!days.length) return null;
  return (
    <Plot
      data={[
        { type: 'bar', name: 'Successful', x: days, y: ok, marker: { color: '#15803D' },
          hovertemplate: `%{x} · %{y} successful<extra></extra>` },
        { type: 'bar', name: 'Failed', x: days, y: fail, marker: { color: '#B91C1C' },
          hovertemplate: `%{x} · %{y} failed<extra></extra>` },
      ]}
      layout={{
        height: 240,
        barmode: 'stack',
        margin: { l: 48, r: 16, t: 8, b: 64 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { family: font.ui, size: 11, color: c.body },
        yaxis: { title: { text: 'transactions', standoff: 12 }, gridcolor: c.line, zerolinecolor: c.lineStrong, rangemode: 'tozero' },
        legend: { orientation: 'h', y: -0.28, x: 0, font: { size: 11 } },
        showlegend: true,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}
