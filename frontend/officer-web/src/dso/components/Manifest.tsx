/**
 * Manifest and route presentation.
 *
 * Two honesty rules are enforced visually here:
 *  - Distance is labelled GEODESIC on every surface that shows it. The optimiser uses great-circle
 *    distance because no road-network data exists in this dataset; presenting it as driving distance
 *    would be a lie the officer might act on.
 *  - A sealed manifest is shown as sealed. Once LOCKED the content is immutable at the database level,
 *    and the hash is displayed with its verification result rather than as decoration.
 */
import { useState } from 'react';
import { Manifest, ManifestDetail, dso } from '../api';
import { c, font, kg, label, num, s, toneFor } from '../theme';
import { Badge, Facts, Panel, Table, td, tdMono } from '../ui';

export function GeodesicNote({ inline }: { inline?: boolean }) {
  return (
    <span style={{ fontSize: 10.5, color: c.muted, fontWeight: 600, letterSpacing: '0.05em',
      display: inline ? 'inline' : 'block' }}>
      GEODESIC (STRAIGHT-LINE) DISTANCE — NOT ROAD DISTANCE
    </span>
  );
}

export function ManifestCard({ m, onOpen, actions }:
  { m: Manifest; onOpen?: () => void; actions?: React.ReactNode }) {
  const sealed = ['LOCKED', 'DISPATCHED', 'DELIVERED', 'RECONCILED'].includes(m.manifest_status);
  return (
    <article style={{ border: `1px solid ${c.line}`, borderRadius: 6, background: c.surface, overflow: 'hidden' }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: s(3), padding: `${s(3)} ${s(4)}`,
        borderBottom: `1px solid ${c.line}`, background: c.raised }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ font: `700 13px ${font.mono}`, color: c.ink }}>{m.manifest_id}</div>
          <div style={{ fontSize: 11.5, color: c.muted, marginTop: 2 }}>
            {m.warehouse_id} → vehicle {m.vehicle_id}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: s(2), alignItems: 'center' }}>
          {sealed && <Badge t="ok" title="Immutable at database level once sealed">SEALED</Badge>}
          <Badge t={toneFor(m.manifest_status)}>{m.manifest_status}</Badge>
        </div>
      </header>

      <div style={{ padding: s(4), display: 'flex', flexDirection: 'column', gap: s(3) }}>
        <div style={{ display: 'flex', gap: s(5), flexWrap: 'wrap' }}>
          <div><div style={label}>Load</div><div style={{ font: `600 15px ${font.ui}`, color: c.ink }}>{kg(m.total_kg)}</div></div>
          <div>
            <div style={label}>Route distance</div>
            <div style={{ font: `600 15px ${font.ui}`, color: c.ink }}>{num(m.route_distance_km)} km</div>
          </div>
          <div>
            <div style={label}>Planned duration</div>
            <div style={{ font: `600 15px ${font.ui}`, color: c.ink }}>{num(m.route_duration_min)} min</div>
          </div>
          <div><div style={label}>Constraints</div><div style={{ marginTop: 3 }}><Badge t={toneFor(m.constraint_status)}>{m.constraint_status}</Badge></div></div>
        </div>
        <GeodesicNote />
        {(onOpen || actions) && (
          <div style={{ display: 'flex', gap: s(2), borderTop: `1px solid ${c.line}`, paddingTop: s(3), flexWrap: 'wrap' }}>
            {onOpen && <button onClick={onOpen} style={{ font: `600 12.5px ${font.ui}`, padding: '7px 14px',
              borderRadius: 5, border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.navy, cursor: 'pointer' }}>
              View manifest
            </button>}
            {actions}
          </div>
        )}
      </div>
    </article>
  );
}

/** Full manifest: items, the planned stop sequence, hash verification and the QR that carries it. */
export function ManifestDetailView({ detail }: { detail: ManifestDetail }) {
  const [hash, setHash] = useState<{ sha256_hash: string; hash_verified: boolean } | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const sealed = ['LOCKED', 'DISPATCHED', 'DELIVERED', 'RECONCILED'].includes(detail.manifest_status);

  const run = async (what: string, fn: () => Promise<void>) => {
    setBusy(what); setErr(null);
    try { await fn(); } catch (e: any) { setErr(e?.message || String(e)); } finally { setBusy(null); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: s(4) }}>
      <Facts items={[
        ['Manifest', <span key="m" style={{ fontFamily: font.mono }}>{detail.manifest_id}</span>],
        ['Status', <Badge key="s" t={toneFor(detail.manifest_status)}>{detail.manifest_status}</Badge>],
        ['Warehouse', detail.warehouse_id],
        ['Vehicle', detail.vehicle_id],
        ['Total load', kg(detail.total_kg)],
        ['Stops', String(detail.route.length)],
        ['Distance', <span key="d">{num(detail.route_distance_km)} km <GeodesicNote inline /></span>],
        ['Created by', detail.created_by || '—'],
      ]} />

      {err && <div style={{ background: c.badBg, border: `1px solid ${c.badLine}`, color: c.bad, padding: s(3), borderRadius: 5, fontSize: 12.5 }}>{err}</div>}

      {sealed && (
        <Panel title="Integrity seal">
          <div style={{ display: 'flex', flexDirection: 'column', gap: s(3) }}>
            <div style={{ display: 'flex', gap: s(2), flexWrap: 'wrap' }}>
              <button onClick={() => run('hash', async () => setHash(await dso.lockVerification(detail.manifest_id)))}
                style={{ font: `600 12.5px ${font.ui}`, padding: '7px 14px', borderRadius: 5,
                  border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.navy, cursor: 'pointer' }}>
                {busy === 'hash' ? 'Verifying…' : 'Verify SHA-256'}
              </button>
              <button onClick={() => run('qr', async () => setQr((await dso.qr(detail.manifest_id)).qr_png_base64))}
                style={{ font: `600 12.5px ${font.ui}`, padding: '7px 14px', borderRadius: 5,
                  border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.navy, cursor: 'pointer' }}>
                {busy === 'qr' ? 'Loading…' : 'Show QR'}
              </button>
              <button onClick={() => window.print()} style={{ font: `600 12.5px ${font.ui}`, padding: '7px 14px',
                borderRadius: 5, border: `1px solid ${c.lineStrong}`, background: c.surface, color: c.body, cursor: 'pointer' }}>
                Print
              </button>
            </div>

            {hash && (
              <div style={{ background: hash.hash_verified ? c.okBg : c.badBg,
                border: `1px solid ${hash.hash_verified ? c.okLine : c.badLine}`, borderRadius: 5, padding: s(3) }}>
                <div style={{ ...label, color: hash.hash_verified ? c.ok : c.bad }}>
                  {hash.hash_verified ? 'Hash verified — content unchanged since sealing' : 'HASH MISMATCH — content has changed'}
                </div>
                <div style={{ fontFamily: font.mono, fontSize: 11, color: c.body, marginTop: 6, overflowWrap: 'anywhere' }}>
                  {hash.sha256_hash}
                </div>
              </div>
            )}

            {qr && (
              <div style={{ textAlign: 'center' }}>
                <img src={`data:image/png;base64,${qr}`} alt={`QR code for manifest ${detail.manifest_id}`}
                  style={{ width: 180, height: 180, imageRendering: 'pixelated', border: `1px solid ${c.line}`, borderRadius: 5 }} />
                <div style={{ fontSize: 11, color: c.muted, marginTop: 6 }}>
                  Scanned at the FPS to verify this manifest against its sealed hash.
                </div>
              </div>
            )}
          </div>
        </Panel>
      )}

      <Panel title={`Planned stops (${detail.route.length})`} subtitle={<GeodesicNote inline />} pad={false}>
        <Table head={['#', 'FPS', 'Leg km', 'ETA (min)', 'Status']} maxHeight={280}>
          {detail.route.map(r => (
            <tr key={r.stop_sequence}>
              <td style={tdMono}>{r.stop_sequence}</td>
              <td style={tdMono}>{r.fps_id}</td>
              <td style={td}>{num(r.distance_from_previous_km)}</td>
              <td style={td}>{num(r.eta_minutes)}</td>
              <td style={td}><Badge>{r.route_status}</Badge></td>
            </tr>
          ))}
        </Table>
      </Panel>

      <Panel title={`Line items (${detail.items.length})`} pad={false}>
        <Table head={['Stop', 'FPS', 'Commodity', 'Planned']} maxHeight={280}>
          {detail.items.map(it => (
            <tr key={it.manifest_item_id}>
              <td style={tdMono}>{it.sequence_number}</td>
              <td style={tdMono}>{it.fps_id}</td>
              <td style={td}>{it.commodity}</td>
              <td style={td}>{kg(it.planned_kg)}</td>
            </tr>
          ))}
        </Table>
      </Panel>
    </div>
  );
}
