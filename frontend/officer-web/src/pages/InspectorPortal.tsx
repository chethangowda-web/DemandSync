/**
 * Field Food Inspector — Stateful Workflow-Driven Command Center
 * REBUILT FRESH per spec: TOP = persistent workflow bar, BELOW = step content.
 * NO left/right sidebars. One continuous journey. Backend-sourced, no mocks.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { ApiError } from '../api/client';
import { c, font, label, s, btn, btnGhost, btnDisabled } from '../dso/theme';
import { inspectorApi, Target } from '../inspector/api';
import { IntelSection, fetchIntel } from '../components/Intelligence';

// ---------------------------------------------------------------- constants
const STEPS = ['TARGET', 'TRAVEL', 'VERIFY', 'INSPECT', 'EVIDENCE', 'FINDINGS', 'REVIEW', 'SUBMIT'] as const;
type StepIdx = number;

const VERIFY_KEYS: { key: string; label: string }[] = [
  { key: 'fps_identity', label: 'FPS identity verified' },
  { key: 'shop_location', label: 'Shop location verified' },
  { key: 'owner_verified', label: 'FPS owner verified' },
  { key: 'license_verified', label: 'License / details verified' },
  { key: 'epos_available', label: 'e-PoS device verified' },
  { key: 'records_available', label: 'Required records available' },
];

const STOCK_ITEMS = [
  { k: 'rice_verified', l: 'Rice — physical stock matches system' },
  { k: 'wheat_verified', l: 'Wheat — physical stock matches system' },
  { k: 'physical_match', l: 'Physical stock matches records' },
  { k: 'damaged_checked', l: 'Damaged / expired stock checked' },
];
const EPOS_ITEMS = [
  { k: 'epos_operational', l: 'e-PoS operational' },
  { k: 'txn_reviewed', l: 'Recent transactions reviewed' },
  { k: 'txn_records', l: 'Transaction records available' },
];
const DIST_ITEMS = [
  { k: 'dist_records', l: 'Entitlement & distribution records verified' },
  { k: 'records_maintained', l: 'Collection records maintained' },
  { k: 'irregularities', l: 'Irregularities observed (check if any)' },
];
const COMPLIANCE_ITEMS = [
  { k: 'info_displayed', l: 'Required information displayed' },
  { k: 'shop_operational', l: 'Shop operational' },
  { k: 'equipment_available', l: 'Required equipment available' },
];

// persistence keys
const stepKey = (id: string) => `dsp-insp-step-${id}`;
const arrivedKey = (id: string) => `dsp-insp-arrived-${id}`;
function loadStep(id: string): number { try { const v = Number(localStorage.getItem(stepKey(id))); return Number.isFinite(v) && v >= 0 && v <= 7 ? v : 0; } catch { return 0; } }
function storeStep(id: string, n: number) { try { localStorage.setItem(stepKey(id), String(n)); } catch {} }
function loadArrived(id: string): boolean { try { return localStorage.getItem(arrivedKey(id)) === '1'; } catch { return false; } }
function storeArrived(id: string, v: boolean) { try { localStorage.setItem(arrivedKey(id), v ? '1' : '0'); } catch {} }

// helpers
function osmEmbed(lat: number, lon: number): string {
  const d = 0.015;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${lon - d},${lat - d},${lon + d},${lat + d}&layer=mapnik&marker=${lat},${lon}`;
}
function mapsUrl(lat?: number | null, lon?: number | null): string | null {
  if (lat == null || lon == null) return null;
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;
}
function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true });
}

// ---------------------------------------------------------------- Gov header
function GovHeader({ user, onLogout }: { user: any; onLogout: () => void }) {
  return (
    <header style={{ background: '#071A31', color: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: s(3), padding: `${s(2)} ${s(4)}`, flexWrap: 'wrap' }}>
        <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>◈</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 9, letterSpacing: '0.1em', opacity: 0.7, fontWeight: 700 }}>GOVERNMENT OF INDIA</div>
          <div style={{ fontSize: 11, opacity: 0.7 }}>Department of Food & Public Distribution</div>
          <div style={{ fontSize: 14, fontWeight: 800, marginTop: 2 }}>PDS DemandSYNC <span style={{ fontWeight: 400, opacity: 0.75, fontSize: 11 }}>— Public Distribution System Intelligence Platform</span></div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: s(3), flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#16A34A' }} /> System Operational
          </span>
          <span style={{ fontSize: 12, textAlign: 'right' }}>
            <strong>{user.name}</strong>
            <span style={{ display: 'block', fontSize: 11, opacity: 0.7 }}>Field Food Inspector · {user.district ?? '—'}</span>
          </span>
          <button onClick={onLogout} style={{ background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 5, padding: '6px 12px', font: `600 12px ${font.ui}`, cursor: 'pointer' }}>Logout</button>
        </div>
      </div>
      <div style={{ display: 'flex', height: 3 }}><div style={{ flex: 1, background: '#FF9933' }} /><div style={{ flex: 1, background: '#fff' }} /><div style={{ flex: 1, background: '#138808' }} /></div>
    </header>
  );
}

function InspectionHeader({ inspection, fps, step }: { inspection: any | null; fps: any | null; step: number }) {
  if (!inspection) {
    return (
      <div style={{ background: '#0F2542', color: '#fff', padding: `${s(3)} ${s(4)}`, borderBottom: '1px solid #1A3A5C' }}>
        <div style={{ fontSize: 10, letterSpacing: '0.14em', opacity: 0.6, fontWeight: 800 }}>FIELD FOOD INSPECTOR</div>
        <div style={{ fontSize: 20, fontWeight: 800, marginTop: 2 }}>Inspect. Verify. Ensure Food Security.</div>
        <div style={{ fontSize: 12, opacity: 0.7, marginTop: 2 }}>Select a Fair Price Shop to begin — your progress is tracked in the workflow bar below.</div>
      </div>
    );
  }
  return (
    <div style={{ background: '#0F2542', color: '#fff', padding: `${s(3)} ${s(4)}`, borderBottom: '1px solid #1A3A5C' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: s(4), alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 9, letterSpacing: '0.12em', opacity: 0.6, fontWeight: 800 }}>INSPECTION</div>
          <div style={{ fontSize: 13, fontWeight: 800, fontFamily: font.mono }}>{inspection.inspection_id}</div>
          <div style={{ fontSize: 11, opacity: 0.75 }}>{fps?.fps_name ?? inspection.fps_id} · {inspection.fps_id} · {fps?.taluk ?? fps?.district ?? ''}</div>
        </div>
        <div style={{ width: 1, height: 44, background: 'rgba(255,255,255,0.15)' }} />
        <div style={{ fontSize: 12 }}><div style={{ opacity: 0.6, fontSize: 10, letterSpacing: '0.08em', fontWeight: 700 }}>STARTED</div><div>{fmtDate(inspection.inspection_date ?? inspection.updated_at)}</div></div>
        <div style={{ fontSize: 12 }}><div style={{ opacity: 0.6, fontSize: 10, letterSpacing: '0.08em', fontWeight: 700 }}>STATUS</div><div style={{ background: inspection.status === 'DRAFT' ? '#FF9933' : '#16A34A', color: inspection.status === 'DRAFT' ? '#071A31' : '#fff', padding: '2px 8px', borderRadius: 999, fontWeight: 800, fontSize: 11, display: 'inline-block', marginTop: 2 }}>{inspection.status === 'DRAFT' ? 'IN PROGRESS' : inspection.status}</div></div>
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{ fontSize: 11, opacity: 0.7 }}>Step {Math.min(step + 1, 8)} of 8</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: '#FF9933' }}>{STEPS[step]}</div>
        </div>
      </div>
    </div>
  );
}

function WorkflowBar({ active, locked, onGo }: { active: number; locked: (i: number) => boolean; onGo: (i: number) => void }) {
  return (
    <div style={{ background: '#fff', borderBottom: `1px solid ${c.line}`, padding: `${s(2)} ${s(4)}`, overflowX: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, minWidth: 760 }}>
        {STEPS.map((nm, i) => {
          const isLocked = locked(i);
          const done = i < active;
          const cur = i === active;
          const circleStyle: React.CSSProperties = done
            ? { background: c.ok, borderColor: c.ok, color: '#fff' }
            : cur ? { background: '#1D4ED8', borderColor: '#1D4ED8', color: '#fff', boxShadow: '0 0 0 4px #DBEAFE' }
              : isLocked ? { background: c.canvas, borderColor: c.lineStrong, color: c.faint }
                : { background: '#fff', borderColor: c.lineStrong, color: c.muted };
          return (
            <span key={nm} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              {i > 0 && <span style={{ width: 28, height: 2, background: done ? c.ok : c.line, margin: '0 4px' }} />}
              <button onClick={() => !isLocked && onGo(i)} disabled={isLocked}
                title={isLocked ? 'Complete previous steps to unlock' : nm}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, background: cur ? '#EFF6FF' : 'transparent',
                  border: `1px solid ${cur ? '#BFDBFE' : 'transparent'}`, borderRadius: 999, padding: '8px 12px',
                  cursor: isLocked ? 'not-allowed' : 'pointer', opacity: isLocked ? 0.55 : 1,
                }}>
                <span style={{
                  width: 26, height: 26, borderRadius: '50%', border: '1px solid', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontWeight: 800, ...circleStyle,
                }}>{done ? '✓' : isLocked ? '🔒' : i + 1}</span>
                <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.06em', color: done ? c.ok : cur ? '#1D4ED8' : isLocked ? c.faint : c.body }}>{nm}</span>
              </button>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- panels

function TargetPanel({ onStart, picked, setPicked }: { onStart: (fpsId: string) => void; picked: Target | null; setPicked: (t: Target) => void }) {
  const [targets, setTargets] = useState<Target[] | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [err, setErr] = useState('');
  const [q, setQ] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    inspectorApi.targets(80).then((r: any) => setTargets(r.targets)).catch((e: any) => setErr(e instanceof ApiError ? e.message : String(e)));
  }, []);
  useEffect(() => { if (picked) inspectorApi.target(picked.fps_id).then(setDetail).catch(() => setDetail(null)); }, [picked]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); searchRef.current?.focus(); } };
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h);
  }, []);
  const filtered = useMemo(() => {
    if (!targets) return null;
    const n = q.trim().toLowerCase();
    if (!n) return targets;
    return targets.filter(t => `${t.fps_id} ${t.fps_name} ${t.taluk} ${t.district}`.toLowerCase().includes(n));
  }, [targets, q]);

  if (err) return <div style={{ padding: s(4), color: c.bad, background: c.badBg, border: `1px solid ${c.badLine}`, borderRadius: 6, margin: s(4) }}>{err}</div>;
  if (!filtered) return <div style={{ padding: s(4), color: c.muted }}>Loading inspection targets…</div>;

  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(4) }}>
      <div style={{ display: 'flex', gap: s(2), alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ ...label }}>Select FPS</div>
        <input ref={searchRef} value={q} onChange={e => setQ(e.target.value)} placeholder="Search FPS ID / name / taluk (Ctrl+K)" style={{ flex: '1 1 260px', border: `1px solid ${c.lineStrong}`, borderRadius: 6, padding: '9px 10px', fontSize: 13 }} />
        <span style={{ fontSize: 11, color: c.muted }}>{filtered.length} shops</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(4) }}>
        {/* left: map */}
        <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(3) }}>
          <div style={{ ...label, marginBottom: s(2) }}>Karnataka · FPS location</div>
          {!picked?.latitude ? (
            <div style={{ height: 360, background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: c.muted, flexDirection: 'column', gap: s(2), padding: s(3) }}>
              <div style={{ fontSize: 13 }}>Choose a shop on the right to see its location</div>
              <div style={{ display: 'flex', gap: 6 }}>{filtered.slice(0, 10).map(t => <span key={t.fps_id} style={{ width: 10, height: 10, borderRadius: '50%', background: t.risk_level === 'HIGH' ? c.bad : t.risk_level === 'MEDIUM' ? c.warn : c.ok, display: 'inline-block' }} />)}</div>
              <div style={{ fontSize: 11, color: c.faint }}>Dots are risk-colored; not live GPS.</div>
            </div>
          ) : (
            <iframe title="map" src={osmEmbed(picked.latitude!, picked.longitude!)} style={{ width: '100%', height: 360, border: `1px solid ${c.line}`, borderRadius: 6 }} loading="lazy" />
          )}
          {picked && (
            <div style={{ marginTop: s(2), fontSize: 12, color: c.body }}>
              <strong>{picked.fps_name}</strong> · {picked.fps_id} · {picked.taluk ?? picked.district} · AI <strong style={{ color: picked.risk_level === 'HIGH' ? c.bad : picked.risk_level === 'MEDIUM' ? c.warn : c.ok }}>{picked.risk_level} {picked.risk_score}/100</strong>
              {picked.latitude && <span> · <a href={mapsUrl(picked.latitude, picked.longitude)!} target="_blank" rel="noreferrer" style={{ color: c.accent }}>Open in Maps ↗</a></span>}
            </div>
          )}
        </div>

        {/* right: list + details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
          <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, maxHeight: 300, overflowY: 'auto' }}>
            {filtered.map(t => (
              <button key={t.fps_id} onClick={() => setPicked(t)}
                style={{
                  width: '100%', textAlign: 'left', display: 'flex', gap: s(2), padding: s(3), border: 'none', borderBottom: `1px solid ${c.line}`, cursor: 'pointer',
                  background: picked?.fps_id === t.fps_id ? '#EFF6FF' : '#fff',
                }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: t.risk_level === 'HIGH' ? c.bad : t.risk_level === 'MEDIUM' ? c.warn : c.ok, marginTop: 4, flexShrink: 0 }} />
                <span style={{ minWidth: 0 }}>
                  <span style={{ fontWeight: 700, fontSize: 13, color: c.ink }}>{t.fps_name}</span>
                  <span style={{ display: 'block', fontSize: 11.5, color: c.muted }}>{t.fps_id} · {t.taluk ?? t.district} · Last: {t.last_inspection ? fmtDate(t.last_inspection) : 'never'}</span>
                  <span style={{ display: 'block', fontSize: 11.5, color: c.body, marginTop: 2 }}>{t.risk_factors.slice(0, 2).map(f => f.label).join(' · ') || 'Routine verification'} {t.risk_level === 'HIGH' ? '🔴' : t.risk_level === 'MEDIUM' ? '🟠' : '🟢'}</span>
                </span>
                <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 800, color: t.risk_level === 'HIGH' ? c.bad : t.risk_level === 'MEDIUM' ? c.warn : c.ok }}>{t.risk_level} {t.risk_score}</span>
              </button>
            ))}
          </div>

          {picked && (
            <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
              <div style={label}>FPS details</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(2), fontSize: 12.5, marginTop: s(2) }}>
                <div><span style={label}>FPS Name</span><div>{picked.fps_name}</div></div>
                <div><span style={label}>FPS ID</span><div style={{ fontFamily: font.mono }}>{picked.fps_id}</div></div>
                <div><span style={label}>Owner</span><div>{detail?.owner?.name ?? '—'}</div></div>
                <div><span style={label}>District / Taluk</span><div>{picked.district} / {picked.taluk ?? '—'}</div></div>
                <div><span style={label}>License / Status</span><div>{detail?.fps?.status ?? picked.status}</div></div>
                <div><span style={label}>Last inspection</span><div>{detail?.signals?.last_inspection?.inspection_date ? fmtDate(detail.signals.last_inspection.inspection_date) : 'Never'}</div></div>
              </div>

              <div style={{ marginTop: s(3), background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
                <div style={label}>Dispatch &amp; delivery{detail?.dispatch?.cycle ? ` · ${detail.dispatch.cycle}` : ''}</div>
                {!detail?.dispatch?.items?.length && <div style={{ fontSize: 12, color: c.muted, marginTop: s(1) }}>No dispatch planned for this shop in the current cycle.</div>}
                {(detail?.dispatch?.items || []).slice(0, 6).map((d: any, i: number) => (
                  <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, marginTop: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ fontFamily: font.mono, fontWeight: 700 }}>{d.manifest_id}</span>
                    <span>{d.commodity} · {d.planned_kg} kg</span>
                    <span style={{ fontSize: 10.5, fontWeight: 800, background: d.manifest_status === 'DISPATCHED' || d.manifest_status === 'DELIVERED' ? c.okBg : c.canvas, color: d.manifest_status === 'DISPATCHED' || d.manifest_status === 'DELIVERED' ? c.ok : c.muted, border: `1px solid ${d.manifest_status === 'DISPATCHED' || d.manifest_status === 'DELIVERED' ? c.okLine : c.line}`, padding: '2px 7px', borderRadius: 999 }}>{d.manifest_status}</span>
                    <span style={{ color: c.muted }}>{d.delivery_status ? `delivered ${d.delivered_kg} kg (${d.delivery_status})` : 'delivery not recorded'}</span>
                  </div>
                ))}
                <div style={{ fontSize: 11, color: c.muted, marginTop: s(1) }}>Same manifest records the DSO operates on — read-only.</div>
              </div>

              <div style={{ marginTop: s(3), background: c.badBg, border: `1px solid ${c.badLine}`, borderRadius: 6, padding: s(3) }}>
                <div style={{ ...label, color: c.bad }}>AI inspection priority · {picked.risk_level} priority</div>
                <div style={{ fontSize: 12, color: c.body, marginTop: s(1) }}>Why prioritized:</div>
                <ul style={{ margin: `${s(1)} 0 0`, paddingLeft: 18, fontSize: 12.5, color: c.body, lineHeight: 1.6 }}>
                  {picked.risk_factors.length ? picked.risk_factors.map(f => <li key={f.key}>{f.label} — {f.detail}</li>) : <li>Routine verification</li>}
                </ul>
                <div style={{ fontSize: 11, color: c.muted, marginTop: s(1) }}>AI suggests focus, not an official finding.</div>
              </div>

              <div style={{ marginTop: s(3), background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 6, padding: s(3) }}>
                <div style={label}>Recommended inspection focus</div>
                {picked.recommended_focus.map((x: string) => <div key={x} style={{ fontSize: 12.5, marginTop: 4 }}>✓ {x}</div>)}
              </div>

              <button onClick={() => onStart(picked.fps_id)} style={{ ...btn, width: '100%', marginTop: s(3), background: '#FF9933', borderColor: '#FF9933', color: '#071A31' }}>START INSPECTION →</button>
              <div style={{ fontSize: 11, color: c.muted, marginTop: s(1), textAlign: 'center' }}>Creates official inspection record — you can resume later.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TravelPanel({ fps, arrived, setArrived }: { fps: any | null; arrived: boolean; setArrived: (v: boolean) => void }) {
  const url = mapsUrl(fps?.latitude, fps?.longitude);
  return (
    <div style={{ padding: s(4) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
        <div style={label}>Field navigation</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: s(4), marginTop: s(3) }}>
          <div>
            {fps?.latitude ? (
              <iframe title="route" src={osmEmbed(fps.latitude, fps.longitude)} style={{ width: '100%', height: 420, border: `1px solid ${c.line}`, borderRadius: 6 }} loading="lazy" />
            ) : (
              <div style={{ height: 420, background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: c.muted }}>LOCATION DATA UNAVAILABLE — no coordinates on record.</div>
            )}
          </div>
          <div>
            <div style={{ background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
              <div style={label}>FPS</div>
              <div style={{ fontWeight: 700 }}>{fps?.fps_name ?? '—'} <span style={{ color: c.muted, fontWeight: 400 }}>({fps?.fps_id ?? '—'})</span></div>
              <div style={{ fontSize: 12, color: c.muted, marginTop: 4 }}>{fps?.taluk ?? ''} {fps?.district ?? ''}</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(2), marginTop: s(3), fontSize: 12.5 }}>
                <div><div style={label}>Distance</div><div>Unavailable — no routing feed</div></div>
                <div><div style={label}>Est. travel time</div><div>Unavailable — no routing feed</div></div>
              </div>
              <div style={{ fontSize: 11, color: c.muted, marginTop: s(2) }}>Do not fake GPS or distance. Use the live Maps link when available.</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: s(2), marginTop: s(3) }}>
                {url ? <a href={url} target="_blank" rel="noreferrer" style={{ ...btn, textAlign: 'center', textDecoration: 'none' }}>START NAVIGATION ↗</a> : <span style={{ fontSize: 12, color: c.muted }}>Route unavailable</span>}
                {!arrived ? (
                  <button onClick={() => setArrived(true)} style={{ ...btn, background: c.ok, borderColor: c.ok }}>I HAVE ARRIVED →</button>
                ) : (
                  <div style={{ background: c.okBg, border: `1px solid ${c.okLine}`, color: c.ok, padding: s(2), borderRadius: 6, fontSize: 12, fontWeight: 700, textAlign: 'center' }}>✓ Arrived — travel completed. Proceed to VERIFY.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function VerifyPanel({ verification, setVerification, locked, onSave, onContinue }: {
  verification: Record<string, boolean>; setVerification: (v: Record<string, boolean>) => void; locked: boolean; onSave: () => void; onContinue: () => void;
}) {
  const done = Object.values(verification).filter(Boolean).length;
  return (
    <div style={{ padding: s(4) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(3) }}>
          <div style={{ ...label }}>FPS verification</div>
          <span style={{ fontSize: 11, fontWeight: 800, background: done >= 4 ? c.okBg : c.warnBg, color: done >= 4 ? c.ok : c.warn, border: `1px solid ${done >= 4 ? c.okLine : c.warnLine}`, padding: '3px 8px', borderRadius: 999 }}>{done} / 6 VERIFIED</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginTop: s(3) }}>
          {VERIFY_KEYS.map(it => (
            <label key={it.key} style={{ display: 'flex', alignItems: 'center', gap: s(2), padding: '12px 0', borderBottom: `1px solid ${c.line}`, cursor: locked ? 'not-allowed' : 'pointer', opacity: locked ? 0.6 : 1 }}>
              <input type="checkbox" checked={!!verification[it.key]} disabled={locked} onChange={e => setVerification({ ...verification, [it.key]: e.target.checked })} />
              <span style={{ fontSize: 13, color: c.ink, flex: 1 }}>{it.label}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: verification[it.key] ? c.ok : c.muted, background: verification[it.key] ? c.okBg : c.canvas, border: `1px solid ${verification[it.key] ? c.okLine : c.line}`, padding: '2px 8px', borderRadius: 999 }}>{verification[it.key] ? 'VERIFIED' : 'NOT VERIFIED'}</span>
            </label>
          ))}
        </div>
        <div style={{ display: 'flex', gap: s(2), marginTop: s(3) }}>
          <button onClick={onSave} disabled={locked} style={locked ? btnDisabled : btnGhost}>SAVE VERIFICATION</button>
          <button onClick={onContinue} disabled={locked || done < 4} style={locked || done < 4 ? btnDisabled : btn}>CONTINUE TO INSPECTION →</button>
        </div>
        {done < 4 && <div style={{ fontSize: 11, color: c.muted, marginTop: s(1) }}>Complete at least 4 items to continue. AI does not auto-verify.</div>}
      </div>
    </div>
  );
}

function InspectPanel({ checklist, setChecklist, locked, onSave }: {
  checklist: Record<string, boolean>; setChecklist: (v: Record<string, boolean>) => void; locked: boolean; onSave: () => void;
}) {
  const done = Object.values(checklist).filter(Boolean).length;
  const total = STOCK_ITEMS.length + EPOS_ITEMS.length + DIST_ITEMS.length + COMPLIANCE_ITEMS.length;
  const Group = ({ title, items }: { title: string; items: typeof STOCK_ITEMS }) => (
    <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(3) }}>
      <div style={label}>{title}</div>
      <div style={{ marginTop: s(2) }}>
        {items.map(it => (
          <label key={it.k} style={{ display: 'flex', alignItems: 'center', gap: s(2), padding: '9px 0', borderBottom: `1px solid ${c.line}`, cursor: locked ? 'not-allowed' : 'pointer' }}>
            <input type="checkbox" checked={!!checklist[it.k]} disabled={locked} onChange={e => setChecklist({ ...checklist, [it.k]: e.target.checked })} />
            <span style={{ fontSize: 13, color: c.ink }}>{it.l}</span>
            <span style={{ marginLeft: 'auto', fontSize: 10, fontWeight: 700, color: checklist[it.k] ? c.ok : c.faint }}>{checklist[it.k] ? 'PASS' : 'NOT VERIFIED'}</span>
          </label>
        ))}
      </div>
    </div>
  );
  return (
    <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(3), display: 'flex', alignItems: 'center', gap: s(2) }}>
        <div style={label}>Inspection progress</div>
        <span style={{ fontSize: 11, fontWeight: 800, background: c.accentBg, color: c.accent, border: '1px solid #BFDBFE', padding: '3px 8px', borderRadius: 999 }}>{done} / {total} checks</span>
        <div style={{ flex: 1, height: 6, background: c.canvas, borderRadius: 999, overflow: 'hidden', marginLeft: s(2) }}><div style={{ width: `${Math.round((done / total) * 100)}%`, height: '100%', background: c.ok }} /></div>
      </div>
      <Group title="STOCK VERIFICATION" items={STOCK_ITEMS} />
      <Group title="e-PoS VERIFICATION" items={EPOS_ITEMS} />
      <Group title="BENEFICIARY DISTRIBUTION" items={DIST_ITEMS} />
      <Group title="SHOP COMPLIANCE" items={COMPLIANCE_ITEMS} />
      <div style={{ display: 'flex', gap: s(2) }}>
        <button onClick={onSave} disabled={locked} style={locked ? btnDisabled : btn}>SAVE & CONTINUE →</button>
        <span style={{ fontSize: 11, color: c.muted, alignSelf: 'center' }}>Inspector decides PASS/FAIL — AI only highlights.</span>
      </div>
    </div>
  );
}

function EvidencePanel({ evidence, setEvidence, notes, setNotes, locked, onSave, inspectionId, fpsId }: {
  evidence: any[]; setEvidence: (v: any[]) => void; notes: string; setNotes: (v: string) => void; locked: boolean; onSave: () => void; inspectionId: string; fpsId: string;
}) {
  const [offline] = useState(!navigator.onLine);
  const add = (type: string, labelTxt: string) => setEvidence([...evidence, { type, label: labelTxt, at: new Date().toISOString(), inspectionId, fpsId }]);
  return (
    <div style={{ padding: s(4) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
          <div style={label}>Field evidence</div>
          <span style={{ fontSize: 11, fontWeight: 700, background: c.canvas, border: `1px solid ${c.line}`, padding: '3px 8px', borderRadius: 999 }}>{evidence.length} items</span>
          <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, background: offline ? c.warnBg : c.okBg, color: offline ? c.warn : c.ok, border: `1px solid ${offline ? c.warnLine : c.okLine}`, padding: '3px 8px', borderRadius: 999 }}>{offline ? 'OFFLINE — Saved on device' : 'Online'}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: s(2), marginTop: s(3) }}>
          {evidence.length === 0 ? <div style={{ fontSize: 12, color: c.muted, padding: s(2) }}>No evidence yet — add a photo, document or note. Each item is linked to {inspectionId} · {fpsId}.</div> :
            evidence.map((e: any, i: number) => (
              <div key={i} style={{ border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3), background: c.raised }}>
                <div style={label}>{e.type?.toUpperCase()}</div>
                <div style={{ fontWeight: 700, fontSize: 13, marginTop: 2 }}>{e.label}</div>
                <div style={{ fontSize: 11, color: c.muted, marginTop: 4 }}>{fmtDate(e.at)}</div>
                {!locked && <button onClick={() => setEvidence(evidence.filter((_, j) => j !== i))} style={{ ...btnGhost, padding: '3px 8px', fontSize: 11, marginTop: s(2) }}>Remove</button>}
              </div>
            ))}
        </div>

        <textarea value={notes} onChange={e => setNotes(e.target.value)} disabled={locked} placeholder="Inspector observation — timestamped with inspection" style={{ width: '100%', minHeight: 90, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(2), fontSize: 13, marginTop: s(3) }} />

        <div style={{ display: 'flex', gap: s(2), marginTop: s(3), flexWrap: 'wrap' }}>
          <button onClick={() => add('photo', 'STOCK PHOTOGRAPH')} disabled={locked} style={locked ? btnDisabled : btnGhost}>ADD PHOTO</button>
          <button onClick={() => add('document', 'LICENSE')} disabled={locked} style={locked ? btnDisabled : btnGhost}>ADD DOCUMENT</button>
          <button onClick={() => add('note', `Observation ${evidence.length + 1}`)} disabled={locked} style={locked ? btnDisabled : btnGhost}>ADD NOTE</button>
          <button onClick={onSave} disabled={locked} style={locked ? btnDisabled : btn}>SAVE EVIDENCE →</button>
        </div>
        {offline && <div style={{ fontSize: 11, color: c.warn, marginTop: s(1) }}>Waiting for synchronization — will show SYNCING… then SYNCED ✓ when online.</div>}
      </div>
    </div>
  );
}

function FindingsPanel({ findings, setFindings, locked, onSave }: {
  findings: any[]; setFindings: (v: any[]) => void; locked: boolean; onSave: () => void;
}) {
  const [draft, setDraft] = useState<any>({ category: 'Stock', severity: 'MEDIUM', finding: '', notes: '', evidence: '' });
  const add = () => {
    if (!draft.finding.trim()) return;
    setFindings([...findings, { ...draft, category: draft.category, severity: draft.severity }]);
    setDraft({ category: 'Stock', severity: 'MEDIUM', finding: '', notes: '', evidence: '' });
  };
  return (
    <div style={{ padding: s(4) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(2) }}>
          <div style={label}>Inspection findings</div>
          <span style={{ fontSize: 11, background: c.canvas, border: `1px solid ${c.line}`, padding: '3px 8px', borderRadius: 999, fontWeight: 700 }}>{findings.length} findings</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: s(3), marginTop: s(3), background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
          <label style={label}>Category<br /><select value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })} disabled={locked} style={{ width: '100%', padding: 7, border: `1px solid ${c.line}`, borderRadius: 5, marginTop: 4 }}><option>Stock</option><option>e-PoS</option><option>Beneficiary Distribution</option><option>Documentation</option><option>Infrastructure</option><option>Compliance</option><option>Other</option></select></label>
          <label style={label}>Severity<br /><select value={draft.severity} onChange={e => setDraft({ ...draft, severity: e.target.value })} disabled={locked} style={{ width: '100%', padding: 7, border: `1px solid ${c.line}`, borderRadius: 5, marginTop: 4 }}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
          <label style={{ ...label, gridColumn: '1 / -1' }}>Description<br /><input value={draft.finding} onChange={e => setDraft({ ...draft, finding: e.target.value })} disabled={locked} placeholder="Inspector observation (official)" style={{ width: '100%', padding: 8, border: `1px solid ${c.line}`, borderRadius: 5, marginTop: 4 }} /></label>
          <label style={label}>Evidence ref<br /><input value={draft.evidence} onChange={e => setDraft({ ...draft, evidence: e.target.value })} disabled={locked} placeholder="Photo #03" style={{ width: '100%', padding: 7, border: `1px solid ${c.line}`, borderRadius: 5, marginTop: 4 }} /></label>
          <label style={label}>Recommended action<br /><input value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} disabled={locked} placeholder="Corrective action" style={{ width: '100%', padding: 7, border: `1px solid ${c.line}`, borderRadius: 5, marginTop: 4 }} /></label>
          <div style={{ alignSelf: 'end' }}><button onClick={add} disabled={locked} style={locked ? btnDisabled : btn}>+ ADD FINDING</button></div>
        </div>
        <div style={{ fontSize: 11, color: c.muted, marginTop: s(1) }}>AI suggestions never become findings automatically.</div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: s(2), marginTop: s(3) }}>
          {findings.map((f: any, i: number) => (
            <div key={i} style={{ border: `1px solid ${f.severity === 'HIGH' || f.severity === 'CRITICAL' ? c.badLine : c.line}`, borderLeft: `4px solid ${f.severity === 'HIGH' || f.severity === 'CRITICAL' ? c.bad : f.severity === 'MEDIUM' ? c.warn : c.ok}`, borderRadius: 6, padding: s(3), background: '#fff' }}>
              <div style={{ display: 'flex', gap: s(2), alignItems: 'center' }}>
                <span style={{ ...label, color: c.ink }}>{f.category}</span>
                <span style={{ fontSize: 10, fontWeight: 800, background: f.severity === 'HIGH' || f.severity === 'CRITICAL' ? c.badBg : f.severity === 'MEDIUM' ? c.warnBg : c.okBg, color: f.severity === 'HIGH' || f.severity === 'CRITICAL' ? c.bad : f.severity === 'MEDIUM' ? c.warn : c.ok, border: `1px solid ${f.severity === 'HIGH' || f.severity === 'CRITICAL' ? c.badLine : f.severity === 'MEDIUM' ? c.warnLine : c.okLine}`, padding: '2px 6px', borderRadius: 999 }}>{f.severity}</span>
                <button onClick={() => !locked && setFindings(findings.filter((_, j) => j !== i))} disabled={locked} style={{ marginLeft: 'auto', ...btnGhost, padding: '2px 8px', fontSize: 11 }}>Remove</button>
              </div>
              <div style={{ fontSize: 13, marginTop: s(1) }}>{f.finding}</div>
              {f.evidence && <div style={{ fontSize: 11, color: c.muted, marginTop: 4 }}>Evidence: {f.evidence}</div>}
              <div style={{ fontSize: 11, color: c.muted, marginTop: 2 }}>Status: OPEN</div>
            </div>
          ))}
        </div>

        <button onClick={onSave} disabled={locked} style={locked ? btnDisabled : {...btn, marginTop: s(3)}}>SAVE FINDINGS →</button>
      </div>
    </div>
  );
}

function ReviewPanel({ inspection, fps, verification, checklist, evidence, findings, onGo, onSaveDraft }: {
  inspection: any; fps: any; verification: any; checklist: any; evidence: any[]; findings: any[]; onGo: (i: number) => void; onSaveDraft: () => void;
}) {
  const vDone = Object.values(verification).filter(Boolean).length;
  const cDone = Object.values(checklist).filter(Boolean).length;
  const cTotal = STOCK_ITEMS.length + EPOS_ITEMS.length + DIST_ITEMS.length + COMPLIANCE_ITEMS.length;
  // completeness: verification 4/6, checklist 5/ total, evidence >=1, findings >=1
  const parts = [vDone >= 4 ? 1 : 0, cDone >= 5 ? 1 : 0, evidence.length > 0 ? 1 : 0, findings.length > 0 ? 1 : 0];
  const pct = Math.round((parts.reduce((a, b) => a + b, 0) / 4) * 100);
  const missing: { label: string; go: number }[] = [];
  if (vDone < 4) missing.push({ label: 'Verification incomplete', go: 2 });
  if (cDone < 5) missing.push({ label: 'Inspection checklist incomplete', go: 3 });
  if (evidence.length === 0) missing.push({ label: 'Evidence missing', go: 4 });
  if (findings.length === 0) missing.push({ label: 'Findings missing', go: 5 });

  return (
    <div style={{ padding: s(4) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
        <div style={label}>Review inspection</div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(3), marginTop: s(3), fontSize: 12.5 }}>
          <div style={{ background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
            <div style={label}>Inspection details</div>
            <div style={{ marginTop: s(1), lineHeight: 1.7 }}>
              FPS: <strong>{fps?.fps_name ?? inspection.fps_id}</strong> ({inspection.fps_id})<br />
              ID: <strong style={{ fontFamily: font.mono }}>{inspection.inspection_id}</strong><br />
              Date: {fmtDate(inspection.inspection_date ?? inspection.updated_at)}
            </div>
          </div>
          <div style={{ background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
            <div style={label}>Inspection completeness</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: s(2), marginTop: s(1) }}>
              <div style={{ flex: 1, height: 10, background: '#E2E8F0', borderRadius: 999, overflow: 'hidden' }}><div style={{ width: `${pct}%`, height: '100%', background: pct >= 80 ? c.ok : c.warn }} /></div>
              <span style={{ fontWeight: 800, color: pct >= 80 ? c.ok : c.warn }}>{pct}%</span>
            </div>
            {missing.length ? (
              <div style={{ fontSize: 12, color: c.bad, marginTop: s(1) }}>{missing.length} items require attention — click to jump:</div>
            ) : <div style={{ fontSize: 12, color: c.ok, marginTop: s(1) }}>All required sections complete.</div>}
            {missing.map(m => <button key={m.label} onClick={() => onGo(m.go)} style={{ ...btnGhost, padding: '3px 8px', fontSize: 11, marginTop: 6, marginRight: 6 }}>{m.label} →</button>)}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: s(2), marginTop: s(3) }}>
          {[
            ['Verification', `${vDone} / 6`, vDone >= 4],
            ['Checklist', `${cDone} / ${cTotal}`, cDone >= 5],
            ['Evidence', `${evidence.length} items`, evidence.length > 0],
            ['Findings', `${findings.length} findings`, findings.length > 0],
          ].map(([k, v, ok]: any) => (
            <div key={k as string} style={{ border: `1px solid ${ok ? c.okLine : c.line}`, background: ok ? c.okBg : '#fff', borderRadius: 6, padding: s(2), textAlign: 'center' }}>
              <div style={{ ...label, color: ok ? c.ok : c.muted }}>{k as string}</div>
              <div style={{ fontWeight: 700, fontSize: 13, color: ok ? c.ok : c.ink }}>{v as string}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: s(2), marginTop: s(3) }}>
          <button onClick={onSaveDraft} style={btnGhost}>SAVE DRAFT</button>
          <button onClick={() => onGo(7)} disabled={pct < 100} style={pct < 100 ? btnDisabled : {...btn, background: '#1D4ED8', borderColor: '#1D4ED8' }}>READY FOR SUBMISSION →</button>
        </div>
        <div style={{ fontSize: 11, color: c.muted, marginTop: s(1) }}>AI insights are shown separately — not mixed with official findings.</div>
      </div>
    </div>
  );
}

function SubmitPanel({ inspection, fps, evidence, findings, onSubmit, submitted, onHome, onNext }: {
  inspection: any; fps: any; evidence: any[]; findings: any[]; onSubmit: () => void; submitted: boolean; onHome: () => void; onNext: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const doSubmit = async () => {
    setBusy(true); setErr('');
    try { await onSubmit(); } catch (e: any) { setErr(e instanceof ApiError ? e.message : String(e)); } finally { setBusy(false); }
  };
  if (submitted) {
    return (
      <div style={{ padding: s(4) }}>
        <div style={{ background: c.okBg, border: `1px solid ${c.okLine}`, borderRadius: 8, padding: s(4), textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', background: c.ok, color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 800 }}>✓</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: c.ok, marginTop: s(2) }}>INSPECTION SUBMITTED</div>
          <div style={{ fontSize: 12, color: c.body, marginTop: s(1) }}>{inspection.inspection_id} · {fps?.fps_name ?? inspection.fps_id} · {fmtDate(new Date().toISOString())} · SUBMITTED</div>
          <div style={{ display: 'flex', gap: s(2), justifyContent: 'center', marginTop: s(3) }}>
            <button onClick={onHome} style={btnGhost}>BACK TO HOME</button>
            <button onClick={onNext} style={{ ...btn, background: c.ok, borderColor: c.ok }}>NEXT INSPECTION →</button>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div style={{ padding: s(4) }}>
      <div style={{ background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4) }}>
        <div style={label}>Submit inspection</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: s(2), fontSize: 12.5, marginTop: s(2), background: c.canvas, border: `1px solid ${c.line}`, borderRadius: 6, padding: s(3) }}>
          <div>FPS: <strong>{fps?.fps_name ?? inspection.fps_id}</strong></div>
          <div>ID: <strong style={{ fontFamily: font.mono }}>{inspection.inspection_id}</strong></div>
          <div>Date: {fmtDate(inspection.inspection_date ?? inspection.updated_at)}</div>
          <div>Findings: <strong>{findings.length}</strong> · Evidence: <strong>{evidence.length}</strong></div>
        </div>
        <div style={{ background: c.warnBg, border: `1px solid ${c.warnLine}`, color: c.warn, padding: s(3), borderRadius: 6, fontSize: 12.5, marginTop: s(3) }}>
          After submission, the inspection will be recorded as an official inspection.
        </div>
        {err && <div style={{ background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(2), borderRadius: 6, fontSize: 12, marginTop: s(2) }}>{err}</div>}
        <button onClick={doSubmit} disabled={busy} style={busy ? btnDisabled : {...btn, marginTop: s(3), background: '#1D4ED8', borderColor: '#1D4ED8' }}>{busy ? 'Submitting…' : 'SUBMIT INSPECTION'}</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- main shell
export default function InspectorPortal() {
  const { user, logout } = useAuth();
  const [targets, setTargets] = useState<Target[] | null>(null);
  const [picked, setPicked] = useState<Target | null>(null);
  const [inspection, setInspection] = useState<any | null>(null);
  const [fps, setFps] = useState<any | null>(null);
  const [step, setStep] = useState<StepIdx>(0);
  const [err, setErr] = useState('');

  const [verification, setVerification] = useState<Record<string, boolean>>({});
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [evidence, setEvidence] = useState<any[]>([]);
  const [notes, setNotes] = useState('');
  const [findings, setFindings] = useState<any[]>([]);
  const [arrived, setArrivedState] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const setArrived = useCallback((v: boolean) => {
    if (inspection) storeArrived(inspection.inspection_id, v);
    setArrivedState(v);
    if (v) setStep(2);
  }, [inspection]);

  // load resume: if drafts exist, offer continue
  const tryResume = useCallback(async () => {
    try {
      const r: any = await inspectorApi.list();
      const drafts = r.inspections.filter((x: any) => x.status === 'DRAFT');
      if (drafts.length) {
        // pick most recent draft
        const id = drafts[0].inspection_id;
        const d: any = await inspectorApi.detail(id);
        setInspection(d.inspection);
        setFps(d.fps);
        setVerification(d.inspection.verification ?? {});
        setChecklist(d.inspection.checklist ?? {});
        setEvidence(d.inspection.evidence ?? []);
        setNotes(d.inspection.notes ?? '');
        setFindings(d.inspection.findings ?? []);
        const a = loadArrived(id);
        setArrivedState(a);
        const sIdx = loadStep(id);
        // clamp to allowed
        setStep(sIdx);
        // set picked from fps
        if (d.fps) setPicked({ fps_id: d.fps.fps_id, fps_name: d.fps.fps_name, district: d.fps.district, taluk: d.fps.taluk, latitude: d.fps.latitude, longitude: d.fps.longitude, status: d.fps.status, risk_score: d.risk?.score ?? 0, risk_level: d.risk?.level ?? 'LOW', risk_factors: d.risk?.factors ?? [], recommended_focus: d.risk?.focus ?? [], last_inspection: null, last_finding: null, inventory: [], grievances_recent: 0, grievances_open: 0, epos_failed_90d: 0, epos_odd_hours_90d: 0 } as any);
        setTargets(null); // will fetch
        inspectorApi.targets(80).then((rr: any) => setTargets(rr.targets)).catch(() => {});
        return;
      }
    } catch {}
    inspectorApi.targets(80).then((r: any) => setTargets(r.targets)).catch((e: any) => setErr(e instanceof ApiError ? e.message : String(e)));
  }, []);

  useEffect(() => { tryResume(); }, [tryResume]);
  useEffect(() => { if (inspection) storeStep(inspection.inspection_id, step); }, [inspection, step]);

  const start = async (fpsId: string) => {
    setErr('');
    try {
      const r: any = await inspectorApi.start(fpsId);
      const d: any = await inspectorApi.detail(r.inspection_id);
      setInspection(d.inspection);
      setFps(d.fps);
      setVerification(d.inspection.verification ?? {});
      setChecklist(d.inspection.checklist ?? {});
      setEvidence(d.inspection.evidence ?? []);
      setNotes(d.inspection.notes ?? '');
      setFindings(d.inspection.findings ?? []);
      setArrivedState(false);
      storeArrived(r.inspection_id, false);
      setStep(r.resumed ? loadStep(r.inspection_id) || 1 : 1);
      if (r.resumed) {
        // keep existing progress
      } else {
        // fresh: ensure step persists
        storeStep(r.inspection_id, 1);
      }
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };

  const save = async () => {
    if (!inspection || inspection.status !== 'DRAFT') return;
    try {
      const r: any = await inspectorApi.update(inspection.inspection_id, { verification, checklist, evidence, notes, findings });
      setInspection(r);
      setErr('');
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };

  const saveAnd = async (next: number) => { await save(); setStep(next); };

  // derived locks
  const isTargetDone = !!inspection;
  const isTravelDone = arrived;
  const isVerifyDone = Object.values(verification).filter(Boolean).length >= 4;
  const isInspectDone = Object.values(checklist).filter(Boolean).length >= 5;
  const isEvidenceDone = evidence.length > 0 || notes.trim().length > 0;
  const isFindingsDone = findings.length > 0;
  const locked = useCallback((i: number): boolean => {
    if (i === 0) return false;
    if (i === 1) return !isTargetDone;
    if (i === 2) return !isTravelDone;
    if (i === 3) return !isVerifyDone;
    if (i === 4) return !isInspectDone;
    if (i === 5) return !isEvidenceDone;
    if (i === 6) return !isFindingsDone;
    if (i === 7) return !(isTargetDone && isTravelDone && isVerifyDone && isInspectDone && isEvidenceDone && isFindingsDone);
    return false;
  }, [isTargetDone, isTravelDone, isVerifyDone, isInspectDone, isEvidenceDone, isFindingsDone]);

  if (!user) return null;

  const onSubmit = async () => {
    await save();
    await inspectorApi.submit(inspection.inspection_id);
    setSubmitted(true);
    setInspection((prev: any) => ({ ...prev, status: 'SUBMITTED' }));
    setStep(7);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#F1F5F9', fontFamily: font.ui }}>
      <GovHeader user={user} onLogout={logout} />
      <InspectionHeader inspection={inspection} fps={fps} step={inspection ? step : 0} />
      <WorkflowBar active={inspection ? step : 0} locked={inspection ? locked : (i: number) => i !== 0} onGo={setStep} />
      {err && <div style={{ margin: `${s(2)} ${s(4)}`, background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(2), borderRadius: 6, fontSize: 12 }}>{err}</div>}

      {/* content */}
      <main>
        {step === 0 && (
          <div style={{ margin: `${s(3)} ${s(4)}` }}>
            <IntelSection title="Inspection intelligence" subtitle="Prioritised shops from delivery, transaction and grievance signals — prioritisation only, never a finding"
              fetch={() => fetchIntel('inspector').then(r => r.insights)}
              emptyWhy="No shop currently crosses the inspection threshold." />
          </div>
        )}
        {step === 0 && <TargetPanel onStart={start} picked={picked} setPicked={setPicked} />}
        {step === 1 && inspection && <TravelPanel fps={fps} arrived={arrived} setArrived={setArrived} />}
        {step === 2 && inspection && <VerifyPanel verification={verification} setVerification={setVerification} locked={inspection.status !== 'DRAFT'} onSave={save} onContinue={() => saveAnd(3)} />}
        {step === 3 && inspection && <InspectPanel checklist={checklist} setChecklist={setChecklist} locked={inspection.status !== 'DRAFT'} onSave={() => saveAnd(4)} />}
        {step === 4 && inspection && <EvidencePanel evidence={evidence} setEvidence={setEvidence} notes={notes} setNotes={setNotes} locked={inspection.status !== 'DRAFT'} onSave={() => saveAnd(5)} inspectionId={inspection.inspection_id} fpsId={inspection.fps_id} />}
        {step === 5 && inspection && <FindingsPanel findings={findings} setFindings={setFindings} locked={inspection.status !== 'DRAFT'} onSave={() => saveAnd(6)} />}
        {step === 6 && inspection && <ReviewPanel inspection={inspection} fps={fps} verification={verification} checklist={checklist} evidence={evidence} findings={findings} onGo={setStep} onSaveDraft={save} />}
        {step === 7 && inspection && <SubmitPanel inspection={inspection} fps={fps} evidence={evidence} findings={findings} onSubmit={onSubmit} submitted={submitted} onHome={() => { setInspection(null); setFps(null); setPicked(null); setStep(0); setSubmitted(false); setArrivedState(false); tryResume(); }} onNext={() => { setInspection(null); setFps(null); setPicked(null); setStep(0); setSubmitted(false); setArrivedState(false); }} />}
        {/* empty states when inspection missing but step >0 — user refreshed without draft */}
        {inspection == null && step > 0 && (
          <div style={{ margin: s(4), background: '#fff', border: `1px solid ${c.line}`, borderRadius: 8, padding: s(4), textAlign: 'center' }}>
            <div style={{ fontWeight: 700 }}>No active inspection</div>
            <div style={{ fontSize: 12, color: c.muted, marginTop: s(1) }}>Start one from TARGET, or resume from a draft.</div>
            <button onClick={() => setStep(0)} style={{ ...btn, marginTop: s(2) }}>Go to TARGET →</button>
          </div>
        )}
      </main>

      <footer style={{ textAlign: 'center', padding: s(3), fontSize: 10, letterSpacing: '0.08em', color: c.muted, fontWeight: 700 }}>
        PDS DemandSYNC · Field Food Inspector Command Center · AI prioritises — Inspector findings decide
      </footer>
    </div>
  );
}
