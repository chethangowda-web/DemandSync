import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';

const field = { display: 'block', width: '100%', boxSizing: 'border-box', padding: 10, margin: '4px 0 14px', fontSize: 15 } as const;

export default function Login() {
  const { user, login, loading } = useAuth();
  const nav = useNavigate();
  const [officerId, setOfficerId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!loading && user) return <Navigate to={user.must_change_password ? '/change-password' : user.portal} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true);
    try {
      const me = await login(officerId, password);
      nav(me.must_change_password ? '/change-password' : me.portal, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.');
    } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} style={{ maxWidth: 380, margin: '80px auto', padding: 28, background: '#fff', border: '1px solid #cbd5e1', borderRadius: 8 }}>
      <h1 style={{ fontSize: 20, margin: '0 0 4px', color: '#0f2a44' }}>DemandSYNC</h1>
      <p style={{ margin: '0 0 20px', color: '#475569', fontSize: 13 }}>Officer sign-in</p>
      <label style={{ fontSize: 13 }}>Officer ID
        <input value={officerId} onChange={e => setOfficerId(e.target.value)} autoComplete="username" autoFocus required style={field} />
      </label>
      <label style={{ fontSize: 13 }}>Password
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required style={field} />
      </label>
      {error && <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', padding: 10, borderRadius: 6, fontSize: 13, marginBottom: 12 }}>{error}</div>}
      <button disabled={busy} style={{ width: '100%', padding: 12, background: '#0f2a44', color: '#fff', border: 0, borderRadius: 6, fontSize: 15, cursor: 'pointer' }}>
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
      <p style={{ fontSize: 11, color: '#64748b', marginTop: 16 }}>Beneficiaries: please use the DemandSYNC mobile app.</p>
    </form>
  );
}
