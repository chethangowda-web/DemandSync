import { useAuth } from '../auth/AuthContext';

// Shows only what the API says about the signed-in user. The workflow screens for each role are built in later phases.
export default function PortalHome({ title, next }: { title: string; next: string }) {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div style={{ maxWidth: 820, margin: '32px auto', padding: '0 16px' }}>
      <h1 style={{ fontSize: 22, color: '#0f2a44' }}>{title}</h1>
      <div style={{ background: '#fff', border: '1px solid #cbd5e1', borderRadius: 8, padding: 16 }}>
        <dl style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '6px 12px', margin: 0, fontSize: 14 }}>
          <dt>Signed in as</dt><dd style={{ margin: 0 }}>{user.name} ({user.user_id})</dd>
          <dt>Role</dt><dd style={{ margin: 0 }}>{user.role}</dd>
          <dt>District</dt><dd style={{ margin: 0 }}>{user.district ?? 'Data unavailable'}</dd>
          <dt>Permissions</dt><dd style={{ margin: 0 }}>{user.permissions.join(', ')}</dd>
        </dl>
      </div>
      <p style={{ color: '#475569', fontSize: 13 }}>{next}</p>
    </div>
  );
}
