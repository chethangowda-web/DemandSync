/**
 * The numeric side of demand intelligence — deliberately free of any Plotly import so it renders
 * immediately, even before the chart bundle has loaded.
 *
 * The two differences the architecture insists on keeping distinct are computed and labelled as such,
 * never collapsed into a single "variance": Intent − Forecast, and Forecast − Baseline.
 */
import { DemandRow } from '../api';
import { c, font, kg, label, num, s } from '../theme';

export interface DemandTotals { intent: number; forecast: number | null; baseline: number | null; }

/** Aggregate the per-FPS rows the backend returns into the three series, per commodity. */
export function totalsByCommodity(rows: DemandRow[]): Record<string, DemandTotals> {
  const out: Record<string, DemandTotals> = {};
  for (const r of rows) {
    const t = out[r.commodity] ?? (out[r.commodity] = { intent: 0, forecast: null, baseline: null });
    t.intent += Number(r.intent_demand_kg || 0);
    if (r.forecast_demand_kg !== null && r.forecast_demand_kg !== undefined) t.forecast = (t.forecast ?? 0) + Number(r.forecast_demand_kg);
    if (r.baseline_demand_kg !== null && r.baseline_demand_kg !== undefined) t.baseline = (t.baseline ?? 0) + Number(r.baseline_demand_kg);
  }
  return out;
}

export function DemandSignal({ rows }: { rows: DemandRow[] }) {
  const totals = totalsByCommodity(rows);
  const commodities = Object.keys(totals).sort();
  if (!commodities.length) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ ...label }}>Demand signal</div>
      {commodities.map(cm => {
        const t = totals[cm];
        const iMinusF = t.forecast === null ? null : Math.round((t.intent - t.forecast) * 10) / 10;
        const fMinusB = t.forecast === null || t.baseline === null ? null : Math.round((t.forecast - t.baseline) * 10) / 10;
        return (
          <div key={cm} style={{ border: `1px solid ${c.line}`, borderRadius: 5, padding: s(3), background: c.raised }}>
            <div style={{ font: `700 12.5px ${font.ui}`, color: c.ink, marginBottom: 6 }}>{cm}</div>
            <div style={{ fontSize: 12.5, color: c.body, lineHeight: 1.7 }}>
              {iMinusF === null ? (
                <div style={{ color: c.muted }}>Intent vs forecast unavailable — no forecast has been generated for this cycle.</div>
              ) : (
                <div>
                  Intent is <strong style={{ color: iMinusF >= 0 ? c.warn : c.body }}>
                    {iMinusF >= 0 ? 'above' : 'below'} forecast by {kg(Math.abs(iMinusF))}
                  </strong>
                  <span style={{ color: c.faint }}> · Intent {num(t.intent)} − Forecast {num(t.forecast)}</span>
                </div>
              )}
              {fMinusB === null ? (
                <div style={{ color: c.muted }}>Forecast vs baseline unavailable — insufficient historical data.</div>
              ) : (
                <div>
                  Forecast is <strong>{fMinusB >= 0 ? 'above' : 'below'} the historical baseline by {kg(Math.abs(fMinusB))}</strong>
                  <span style={{ color: c.faint }}> · Forecast {num(t.forecast)} − Baseline {num(t.baseline)}</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
