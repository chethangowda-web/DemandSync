import { useEffect, useState } from 'react';
import { api } from '../api/client';
import PortalHome from './PortalHome';

interface Status {
  migrations: string[]; total_rows: number; row_counts: Record<string, number>;
  latest_import: null | {
    import_id: string; dataset: string; version: string; status: string; total_rows: number;
    checksum: string; imported_by: string; imported_at: string; checks_total: number; checks_failed: number;
  };
  cycles: { cycle: string; state: string }[];
}

export default function AdminDataTrust() {
  const [s, setS] = useState<Status | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api<Status>('/api/v1/system/db-status').then(setS).catch(e => setErr(e.message)); }, []);
  const imp = s?.latest_import;
  return (
    <>
      <PortalHome title="System Admin" next="Data trust: live state read from the database." />
      <div style={{ maxWidth: 820, margin: '0 auto 40px', padding: '0 16px', fontSize: 14 }}>
        {err && <div role="alert" style={{ color: '#b91c1c' }}>{err}</div>}
        {!s && !err && <p>Loading…</p>}
        {s && (
          <>
            <h2 style={{ fontSize: 16 }}>Active dataset</h2>
            {imp ? (
              <p>{imp.dataset} v{imp.version} — <strong>{imp.status}</strong> — {imp.total_rows.toLocaleString()} rows — {imp.checks_total - imp.checks_failed}/{imp.checks_total} checks passed<br />
                <small>import {imp.import_id} by {imp.imported_by} at {imp.imported_at} · sha256 {imp.checksum.slice(0, 16)}…</small></p>
            ) : <p>No dataset imported yet.</p>}
            <h2 style={{ fontSize: 16 }}>Migrations</h2>
            <p>{s.migrations.join(', ')}</p>
            <h2 style={{ fontSize: 16 }}>Rows per table</h2>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <tbody>{Object.entries(s.row_counts).map(([t, n]) => (
                <tr key={t} style={{ borderBottom: '1px solid #e2e8f0' }}><td style={{ padding: 4 }}>{t}</td><td style={{ textAlign: 'right' }}>{n.toLocaleString()}</td></tr>
              ))}</tbody>
            </table>
          </>
        )}
      </div>
    </>
  );
}
