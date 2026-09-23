/**
 * Phase 8 — shared operational-intelligence rendering.
 *
 * Serious government-operations styling: no chatbot chrome, no robot icons,
 * no glowing buttons, no invented percentages. Every card answers WHAT / WHY
 * / EVIDENCE / WHAT CAN I DO, carries an ADVISORY badge, and shows
 * "Confidence unavailable" whenever the backend has no legitimate value.
 *
 * Self-contained (inline styles only) so every portal — DSO, Inspector, FPS,
 * Auditor, Admin — can use it without theme coupling.
 */
import { useEffect, useState } from 'react';
import { ApiError } from '../api/client';
import { intel, AskResponse, Insight, OpsBrief } from '../api/intelligence';

const INK = '#1F2937';
const BODY = '#374151';
const FAINT = '#6B7280';
const LINE = '#E5E7EB';
const SURFACE = '#FFFFFF';
const RAISED = '#F9FAFB';

const SEV: Record<string, { fg: string; bg: string; ln: string }> = {
  HIGH: { fg: '#991B1B', bg: '#FEF2F2', ln: '#FECACA' },
  MEDIUM: { fg: '#92400E', bg: '#FFFBEB', ln: '#FDE68A' },
  LOW: { fg: '#065F46', bg: '#ECFDF5', ln: '#A7F3D0' },
};

function sevOf(s: string) { return SEV[s] ?? SEV.LOW; }

export function AdvisoryTag() {
  return (
    <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.4, color: '#1D4ED8',
      background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 3, padding: '1px 6px' }}>
      ADVISORY
    </span>
  );
}

export function InsightCard({ insight }: { insight: Insight }) {
  const v = sevOf(insight.severity);
  return (
    <article style={{ border: `1px solid ${LINE}`, borderLeft: `3px solid ${v.fg}`, borderRadius: 5,
      padding: 12, background: SURFACE }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.4, color: v.fg,
          background: v.bg, border: `1px solid ${v.ln}`, borderRadius: 3, padding: '1px 6px' }}>
          {insight.severity}
        </span>
        <span style={{ fontSize: 10.5, color: FAINT, fontFamily: 'monospace' }}>{insight.type}</span>
        <span style={{ marginLeft: 'auto' }}><AdvisoryTag /></span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 13, color: INK, marginBottom: 4 }}>{insight.title}</div>
      <div style={{ fontSize: 12.5, color: BODY, lineHeight: 1.6 }}>{insight.summary}</div>
      {insight.stale && (
        <div style={{ marginTop: 6, fontSize: 12, color: '#92400E' }}>
          DATA STALE — generated {insight.generated_at}
          {insight.data_timestamp ? ` from data last updated ${insight.data_timestamp}` : ''}.
        </div>
      )}
      {(insight.evidence?.length > 0) && (
        <div style={{ marginTop: 8, fontSize: 12, color: BODY }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: FAINT, marginBottom: 2 }}>EVIDENCE</div>
          <ul style={{ margin: '0 0 0 16px', padding: 0, lineHeight: 1.6 }}>
            {insight.evidence.slice(0, 6).map((e, i) => (
              <li key={i}>
                <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{e.record}</span>
                {e.field ? <span style={{ color: FAINT }}> · {e.field}</span> : null}
                {e.value !== undefined && e.value !== null
                  ? <span> — <strong>{String(e.value).slice(0, 160)}</strong></span> : null}
                {e.detail ? <div style={{ color: FAINT, fontSize: 11.5 }}>{e.detail}</div> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {insight.recommendation && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${LINE}`,
          display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', fontSize: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: FAINT }}>WHAT CAN I DO</span>
          <span style={{ color: INK }}>{insight.recommendation}</span>
          <span style={{ fontSize: 11, fontWeight: 700, color: FAINT }}>CONFIDENCE</span>
          <span style={{ color: BODY }}>{insight.confidence_display || 'Confidence unavailable'}</span>
          {(insight.model_version || insight.dataset_version) && (
            <>
              <span style={{ fontSize: 11, fontWeight: 700, color: FAINT }}>MODEL</span>
              <span style={{ color: FAINT, fontFamily: 'monospace', fontSize: 11 }}>
                {[insight.model_version, insight.dataset_version].filter(Boolean).join(' · ')}
              </span>
            </>
          )}
        </div>
      )}
    </article>
  );
}

export function InsightList({ insights, emptyWhy }: { insights: Insight[]; emptyWhy: string }) {
  if (!insights || insights.length === 0) {
    return (
      <div style={{ border: `1px dashed ${LINE}`, borderRadius: 5, padding: 12, background: RAISED,
        fontSize: 12.5, color: FAINT }}>
        No operational signals. {emptyWhy}
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {insights.map(i => <InsightCard key={i.insight_id} insight={i} />)}
    </div>
  );
}

export function BriefView({ brief }: { brief: OpsBrief }) {
  return (
    <div style={{ border: `1px solid ${LINE}`, borderRadius: 5, background: RAISED, padding: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: FAINT, marginBottom: 8, letterSpacing: 0.4 }}>
        AI OPERATIONS BRIEF — {brief.cycle} <AdvisoryTag />
      </div>
      <div style={{ display: 'grid', gap: 8 }}>
        {brief.sections.map(s => (
          <div key={s.title} style={{ display: 'grid', gridTemplateColumns: 110, gap: 4 } as any}>
            <span style={{ fontSize: 11, fontWeight: 700, color: INK }}>{s.title}</span>
            {s.lines.map((l, i) => <div key={i} style={{ fontSize: 12.5, color: BODY }}>{l}</div>)}
          </div>
        ))}
      </div>
    </div>
  );
}

export function AskPanel({ cycle, placeholder }: { cycle?: string; placeholder?: string }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [resp, setResp] = useState<AskResponse | null>(null);
  const run = async () => {
    if (!q.trim() || busy) return;
    setBusy(true); setErr(null);
    try {
      setResp(await intel.ask({ question: q.trim(), cycle }));
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };
  return (
    <div style={{ border: `1px solid ${LINE}`, borderRadius: 5, background: SURFACE, padding: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: FAINT, marginBottom: 8, letterSpacing: 0.4 }}>
        OPERATIONAL ASSISTANT — answers from records only <AdvisoryTag />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={q} onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') run(); }}
          placeholder={placeholder || 'Ask about allocations, demand, stock, dispatch readiness…'}
          style={{ flex: 1, fontSize: 13, padding: '7px 10px', border: `1px solid ${LINE}`,
            borderRadius: 4, color: INK }} />
        <button onClick={run} disabled={busy || !q.trim()}
          style={{ fontSize: 12.5, fontWeight: 600, padding: '7px 14px', borderRadius: 4,
            border: '1px solid #1D4ED8', background: busy ? '#EFF6FF' : '#1D4ED8', color: busy ? '#1D4ED8' : '#fff',
            cursor: busy ? 'wait' : 'pointer' }}>
          {busy ? 'Reading records…' : 'Ask'}
        </button>
      </div>
      {err && <div style={{ marginTop: 8, fontSize: 12.5, color: '#991B1B' }}>{err}</div>}
      {resp && (
        <div style={{ marginTop: 10, fontSize: 12.5, color: BODY, lineHeight: 1.6 }}>
          <div>{resp.answer}</div>
          {resp.evidence?.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 11.5, color: FAINT }}>
              Evidence: {resp.evidence.slice(0, 4).map(e =>
                `${e.record}${e.value !== undefined ? ` (${String(e.value).slice(0, 80)})` : ''}`).join(' · ')}
            </div>
          )}
          <div style={{ marginTop: 6, fontSize: 11, color: FAINT }}>
            {resp.model} · {new Date(resp.generated_at).toLocaleString('en-IN')} · advisory only — a human decides.
          </div>
        </div>
      )}
    </div>
  );
}

/** Fetch-on-mount section: cycle-scoped insight list with graceful fallback. */
export function IntelSection({ title, subtitle, fetch, emptyWhy }:
  { title: string; subtitle?: string; fetch: () => Promise<Insight[]>; emptyWhy: string }) {
  const [data, setData] = useState<Insight[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  useEffect(() => {
    let live = true;
    fetch().then(d => { if (live) setData(d); })
      .catch((e: any) => {
        if (!live) return;
        if (e instanceof ApiError && (e.status >= 500 || e.status === 0)) setDown(true);
        else setError(e?.message || String(e));
      });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <section style={{ border: `1px solid ${LINE}`, borderRadius: 6, background: SURFACE, padding: 14 }}>
      <div style={{ fontWeight: 700, fontSize: 13.5, color: INK }}>{title}</div>
      {subtitle && <div style={{ fontSize: 12, color: FAINT, marginTop: 2 }}>{subtitle}</div>}
      <div style={{ marginTop: 10 }}>
        {down ? (
          <div style={{ fontSize: 12.5, color: FAINT, border: `1px dashed ${LINE}`,
            borderRadius: 5, padding: 12, background: RAISED }}>
            AI INSIGHTS TEMPORARILY UNAVAILABLE — the core workflow below remains fully operational.
          </div>
        ) : error ? (
          <div style={{ fontSize: 12.5, color: '#991B1B' }}>{error}</div>
        ) : data === null ? (
          <div style={{ fontSize: 12.5, color: FAINT }}>Reading records…</div>
        ) : (
          <InsightList insights={data} emptyWhy={emptyWhy} />
        )}
      </div>
    </section>
  );
}

/** Raw fetcher for pages with their own layout: returns {data, down, error}. */
export async function fetchIntel(path: 'dso' | 'inspector' | 'fps' | 'auditor' | 'admin',
  cycle?: string): Promise<{ insights: Insight[]; brief?: OpsBrief }> {
  if (path === 'dso') {
    const r = await intel.dsoSummary(cycle);
    return { insights: r.insights, brief: r.brief };
  }
  if (path === 'inspector') {
    const r = await intel.inspectorSummary(cycle);
    const cards: Insight[] = (r.inspection_priorities || []).map((p: any, i: number) => ({
      insight_id: `insp-${i}`, type: 'INSPECTION_PRIORITY',
      severity: p.level, title: `Inspect ${p.fps_id} — ${p.fps_name}`,
      summary: `Risk score ${p.score}. Focus: ${(p.focus || []).join('; ')}. ` +
        (p.factors || []).map((f: any) => `${f.label}: ${f.detail}`).join(' '),
      recommendation: 'Schedule a visit; findings must be recorded by the inspector, never pre-filled.',
      entity_type: 'FPS', entity_id: p.fps_id, evidence: [], calculation: { score: p.score },
      source_records: ['inventory', 'epos_transactions', 'grievances', 'inspections'],
      model_type: 'deterministic', model_version: null, dataset_version: null,
      generated_at: new Date().toISOString(), confidence: null,
      confidence_display: 'Confidence unavailable', status: 'ADVISORY',
    }));
    return { insights: cards };
  }
  if (path === 'fps') {
    const r = await intel.fpsSummary(cycle);
    const cards: Insight[] = [
      ...((r.stock_risks || []) as Insight[]),
      ...((r.allocation_explanations || []).map((e: any, i: number): Insight => ({
        insight_id: `fps-exp-${i}`, type: 'ALLOCATION_EXPLANATION', severity: 'LOW' as const,
        title: `Why your ${e.commodity} allocation is what it is`,
        summary: e.answer, recommendation: null, entity_type: 'FPS', entity_id: r.fps_id,
        evidence: e.evidence || [], calculation: e.detail || {},
        source_records: ['allocations', 'exceptions'], model_type: 'deterministic',
        model_version: null, dataset_version: null, generated_at: new Date().toISOString(),
        confidence: null, confidence_display: 'Confidence unavailable', status: 'ADVISORY' as const,
      }))),
    ];
    return { insights: cards };
  }
  if (path === 'auditor') {
    const r = await intel.auditorSummary(cycle);
    return { insights: (r.insights || []) as Insight[] };
  }
  const r = await intel.adminSummary();
  return { insights: r.insights };
}
