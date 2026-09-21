import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ApiError, post, setToken } from '../api/client';
import { useAuth } from '../auth/AuthContext';

const field = { display: 'block', width: '100%', boxSizing: 'border-box', padding: 10, margin: '8px 0' } as const;

export default function ChangePassword() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [error, setError] = useState('');
  if (!user) return <Navigate to="/login" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('');
    try {
      await post('/api/v1/auth/change-password', { current_password: current, new_password: next });
      setToken(null); await refresh(); nav('/login', { replace: true });  // the server revoked this session
    } catch (err) { setError(err instanceof ApiError ? err.message : 'Could not change the password.'); }
  };
  return (
    <form onSubmit={submit} style={{ maxWidth: 380, margin: '80px auto', padding: 28, background: '#fff', border: '1px solid #cbd5e1', borderRadius: 8 }}>
      <h1 style={{ fontSize: 18, color: '#0f2a44' }}>{user.must_change_password ? 'Set a new password to continue' : 'Change password'}</h1>
      <p style={{ fontSize: 12, color: '#475569' }}>At least 10 characters, with letters and digits, not containing your ID. You will be signed out afterwards.</p>
      <input type="password" placeholder="Current password" value={current} onChange={e => setCurrent(e.target.value)} required style={field} />
      <input type="password" placeholder="New password" value={next} onChange={e => setNext(e.target.value)} required style={field} />
      {error && <div role="alert" style={{ color: '#b91c1c', fontSize: 13, margin: '8px 0' }}>{error}</div>}
      <button style={{ width: '100%', padding: 12, background: '#0f2a44', color: '#fff', border: 0, borderRadius: 6 }}>Change password</button>
    </form>
  );
}
