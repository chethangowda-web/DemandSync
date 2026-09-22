/**
 * AI Operations Brief.
 *
 * Two kinds of signal appear here and they are never blurred together:
 *
 *   MODEL   — output of the real XGBoost demand forecast (GET /ai/forecast), carrying the model's own
 *             confidence, reason and model_version straight from the ai_predictions envelope.
 *   RULE    — a deterministic threshold evaluated over real backend figures. These show the rule that
 *             fired instead of a confidence percentage, because inventing a confidence for a hand-written
 *             `if` would be dishonest.
 *
 * Nothing here decides anything. Every card ends in a recommendation for the officer, and the panel
 * says plainly that authorisation stays with the human.
 */
import { AiForecast, Summary } from '../api';
import { c, font, kg, label, pct, s, Tone, tone } from '../theme';
import { Badge, DataUnavailable } from '../ui';

export interface Signal {
  kind: 'MODEL' | 'RULE';
  title: string;
  level: string;
  levelTone: Tone;
  evidence: string;
  recommendation: string;
  source: string;
  confidence?: number;
  modelVersion?: string;
}

/** Build the brief from figures the backend actually returned. Absent data produces no card at all. */
export function buildSignals(summary: Summary | null, ai: AiForecast | null): Signal[] {
  const out: Signal[] = [];
  if (!summary) return out;

  // --- MODEL: the real forecast envelope, when one exists for this cycle
  if (ai) {
    out.push({
      kind: 'MODEL',
      title: 'Demand forecast',
      level: ai.confidence >= 70 ? 'Confident' : ai.confidence >= 45 ? 'Moderate' : 'Low confidence',
      levelTone: ai.confidence >= 70 ? 'ok' : ai.confidence >= 45 ? 'warn' : 'bad',
      evidence: ai.reason,
      recommendation: ai.what_next || 'Review the forecast before locking demand.',
      source: `ai_predictions · ${ai.model_version}`,
      confidence: ai.confidence,
      modelVersion: ai.model_version,
    });
  }

  // --- RULE: intent materially diverges from forecast
  const d = summary.forecast.intent_vs_forecast_kg;
  if (d !== null && summary.forecast.kg) {
    const rel = Math.abs(d) / summary.forecast.kg * 100;
    if (rel >= 5) {
      out.push({
        kind: 'RULE',
        title: 'Demand divergence',
        level: rel >= 20 ? 'High' : 'Moderate',
        levelTone: rel >= 20 ? 'bad' : 'warn',
        evidence: `Submitted intent differs from forecast by ${kg(Math.abs(d))} (${rel.toFixed(1)}% of forecast).`,
        recommendation: 'Review validated demand before locking; a large gap usually means low participation, not low need.',
        source: 'intent_signals + demand_forecast · rule: |intent − forecast| ≥ 5% of forecast',
      });
    }
  }

  // --- RULE: allocations the constraint engine could not approve
  if (summary.allocation.blocked > 0) {
    out.push({
      kind: 'RULE',
      title: 'Allocation pressure',
      level: summary.allocation.blocked >= 10 ? 'High' : 'Moderate',
      levelTone: summary.allocation.blocked >= 10 ? 'bad' : 'warn',
      evidence: `${summary.allocation.blocked} of ${summary.allocation.rows} allocations are BLOCKED by a constraint gate and will not be routed.`,
      recommendation: 'Open each blocked item, read the gate that fired, and either correct the underlying data or record an audited override.',
      source: 'allocations + exceptions · rule: status = BLOCKED',
    });
  }

  // --- RULE: fleet capacity against what has actually been planned
  if (summary.manifests.count > 0 && summary.fleet.total > 0 && summary.fleet.available === 0) {
    out.push({
      kind: 'RULE',
      title: 'Fleet risk',
      level: 'High',
      levelTone: 'bad',
      evidence: `No vehicle is currently AVAILABLE across a fleet of ${summary.fleet.total}.`,
      recommendation: 'Confirm vehicle statuses before dispatch; routing can only assign AVAILABLE vehicles.',
      source: 'vehicles · rule: count(status = AVAILABLE) = 0',
    });
  }

  // --- RULE: exception backlog
  if (summary.exceptions.critical > 0) {
    out.push({
      kind: 'RULE',
      title: 'Exception priority',
      level: 'High',
      levelTone: 'bad',
      evidence: `${summary.exceptions.critical} high-severity exception${summary.exceptions.critical === 1 ? '' : 's'} open on this cycle's own gates.`,
      recommendation: 'Clear high-severity exceptions before reconciliation; they block the closure gate.',
      source: 'exceptions · rule: severity = HIGH and status = OPEN',
    });
  }

  // --- RULE: delivery variance observed during reconciliation
  if (summary.delivery.records > 0 && (summary.delivery.variance > 0 || summary.delivery.rejected > 0)) {
    out.push({
      kind: 'RULE',
      title: 'Delivery anomaly',
      level: summary.delivery.rejected > 0 ? 'High' : 'Moderate',
      levelTone: summary.delivery.rejected > 0 ? 'bad' : 'warn',
      evidence: `${summary.delivery.variance} delivery line(s) outside tolerance and ${summary.delivery.rejected} rejected, across ${summary.delivery.records} recorded.`,
      recommendation: 'Investigate variances before closing; they fail the closure checks.',
      source: 'delivery_history · rule: status in (VARIANCE, REJECTED)',
    });
  }

  // --- RULE: coverage shortfall
  if (summary.coverage.pct !== null && summary.coverage.pct < 100 && summary.allocation.rows > 0) {
    const missing = summary.coverage.active_fps - summary.coverage.fps_with_approved_allocation;
    out.push({
      kind: 'RULE',
      title: 'Coverage gap',
      level: summary.coverage.pct < 80 ? 'High' : 'Moderate',
      levelTone: summary.coverage.pct < 80 ? 'bad' : 'warn',
      evidence: `${missing} active FPS have no approved allocation (${summary.coverage.pct}% covered).`,
      recommendation: 'Check whether those shops are suspended, over capacity, or short of warehouse stock.',
      source: 'fps + allocations · rule: active FPS without an APPROVED allocation',
    });
  }

  return out;
}

function SignalCard({ sig }: { sig: Signal }) {
  const v = tone[sig.levelTone];
  return (
    <article style={{ border: `1px solid ${c.line}`, borderLeft: `3px solid ${v.fg}`, borderRadius: 5,
      padding: s(3), background: c.surface }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(2), marginBottom: 6, flexWrap: 'wrap' }}>
        <Badge t={sig.kind === 'MODEL' ? 'accent' : 'idle'}>{sig.kind === 'MODEL' ? 'Model signal' : 'Rule signal'}</Badge>
        <span style={{ font: `700 13px ${font.ui}`, color: c.ink }}>{sig.title}</span>
        <span style={{ marginLeft: 'auto' }}><Badge t={sig.levelTone}>{sig.level}</Badge></span>
      </div>

      <div style={{ fontSize: 12.5, color: c.body, lineHeight: 1.6 }}>{sig.evidence}</div>

      <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${c.line}`, display: 'grid',
        gridTemplateColumns: 'auto 1fr', gap: `4px ${s(3)}`, fontSize: 12 }}>
        <span style={{ ...label }}>Recommend</span>
        <span style={{ color: c.ink }}>{sig.recommendation}</span>
        <span style={{ ...label }}>{sig.kind === 'MODEL' ? 'Confidence' : 'Basis'}</span>
        <span style={{ color: c.body }}>
          {sig.kind === 'MODEL' && sig.confidence !== undefined
            ? <>{sig.confidence}% <span style={{ color: c.faint }}>· {sig.modelVersion}</span></>
            : <span style={{ color: c.faint }}>Deterministic rule — no model confidence applies</span>}
        </span>
        <span style={{ ...label }}>Source</span>
        <span style={{ color: c.faint, fontFamily: font.mono, fontSize: 11, overflowWrap: 'anywhere' }}>{sig.source}</span>
      </div>
    </article>
  );
}

export function AIBrief({ summary, ai, aiUnavailableReason }:
  { summary: Summary | null; ai: AiForecast | null; aiUnavailableReason?: string }) {
  const signals = buildSignals(summary, ai);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
      {signals.length === 0 ? (
        <DataUnavailable what="No operational signals"
          why={aiUnavailableReason || 'Nothing in this cycle currently crosses a risk threshold, and no forecast has been generated yet.'} />
      ) : signals.map((sg, i) => <SignalCard key={i} sig={sg} />)}

      <div style={{ fontSize: 11.5, color: c.muted, borderTop: `1px solid ${c.line}`, paddingTop: s(3), lineHeight: 1.6 }}>
        AI and rule signals are <strong>advisory only</strong>. They never allocate, authorise, dispatch or close a
        cycle — every such action requires an explicit, audited decision by the District Supply Officer.
      </div>
    </div>
  );
}
