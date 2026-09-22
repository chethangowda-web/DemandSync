/**
 * Credentials.
 *
 * The authentication path is unchanged from the original sign-in page: useAuth().login() ->
 * POST /api/v1/auth/officer/login -> GET /api/v1/auth/me, then navigate to the server-supplied
 * portal (or /change-password when the server says the password must be rotated). No credential
 * handling, token storage, or routing decision is reimplemented here.
 *
 * The role picked in the directory above is deliberately not a prop here: it is never sent and never
 * influences the destination, so wiring it through this component would only invite someone to
 * "use" it later. The server's answer is the whole of the decision.
 */
import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { lc, lfont } from './loginTheme';

export default function OfficerLoginForm() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [officerId, setOfficerId] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const me = await login(officerId, password);
      // The server decides the destination -- portal and password-rotation alike.
      nav(me.must_change_password ? '/change-password' : me.portal, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.');
      setBusy(false); // on success the route changes and this component unmounts
    }
  };

  return (
    <form onSubmit={submit} noValidate>
      <div className="ds-field">
        <label htmlFor="ds-officer-id" className="ds-label">Officer ID</label>
        <input
          id="ds-officer-id"
          className="ds-input"
          value={officerId}
          onChange={e => setOfficerId(e.target.value)}
          placeholder="Enter your government officer ID"
          autoComplete="username"
          autoCapitalize="characters"
          spellCheck={false}
          autoFocus
          required
          disabled={busy}
          aria-describedby={error ? 'ds-login-error' : undefined}
          aria-invalid={error ? true : undefined}
        />
      </div>

      <div className="ds-field">
        <label htmlFor="ds-password" className="ds-label">Password</label>
        <div className="ds-input-wrap">
          <input
            id="ds-password"
            className="ds-input ds-input-pw"
            type={reveal ? 'text' : 'password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Enter your password"
            autoComplete="current-password"
            required
            disabled={busy}
            aria-describedby={error ? 'ds-login-error' : undefined}
            aria-invalid={error ? true : undefined}
          />
          <button
            type="button"
            className="ds-reveal"
            onClick={() => setReveal(v => !v)}
            disabled={busy}
            aria-pressed={reveal}
            aria-label={reveal ? 'Hide password' : 'Show password'}
            title={reveal ? 'Hide password' : 'Show password'}
          >
            {reveal ? (
              <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 3l18 18" />
                <path d="M10.6 5.2A9.9 9.9 0 0 1 12 5c5.5 0 9 6 9 6a16 16 0 0 1-3.2 3.9" />
                <path d="M6.2 8.1A16 16 0 0 0 3 11s3.5 6 9 6a9.6 9.6 0 0 0 3.6-.7" />
                <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 11s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z" />
                <circle cx="12" cy="11" r="2.6" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Assertive: a failed sign-in is the one thing on this screen the officer must not miss. */}
      <div aria-live="assertive">
        {error && (
          <p id="ds-login-error" role="alert" className="ds-error">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.7"
              strokeLinecap="round" aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }}>
              <circle cx="12" cy="12" r="9" /><path d="M12 7.5v5" /><path d="M12 16h.01" />
            </svg>
            <span>{error}</span>
          </p>
        )}
      </div>

      <button type="submit" className="ds-submit" disabled={busy}>
        <span>{busy ? 'Verifying credentials…' : 'Secure sign in'}</span>
        {busy ? (
          <span className="ds-spinner" aria-hidden="true" />
        ) : (
          <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.9"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="ds-submit-arrow">
            <path d="M5 12h13" /><path d="m12.5 6 6 6-6 6" />
          </svg>
        )}
      </button>

      <p style={{ font: `500 11px ${lfont.ui}`, color: lc.muted, margin: '14px 0 0', lineHeight: 1.55 }}>
        Beneficiaries do not sign in here — please use the DemandSYNC mobile app.
      </p>
    </form>
  );
}
