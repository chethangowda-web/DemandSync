/**
 * Officer sign-in: a split command-centre screen.
 *
 * Left  -- who this platform is and what it is currently doing, from real endpoints.
 * Right -- the credential card.
 *
 * The already-signed-in redirect is the original page's, unchanged: an authenticated officer never
 * sees this screen, they are sent to their server-assigned portal (or to rotate their password).
 */
import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import CommandCentrePanel from './CommandCentrePanel';
import OfficerAccessCard from './OfficerAccessCard';
import { useHealth, useManifest } from './platform';
import './login.css';

export default function OfficerLoginPage() {
  const { user, loading } = useAuth();
  const health = useHealth();
  const manifest = useManifest();

  if (!loading && user) return <Navigate to={user.must_change_password ? '/change-password' : user.portal} replace />;

  return (
    <main className="ds-login">
      <CommandCentrePanel health={health} manifest={manifest} />
      <OfficerAccessCard />
    </main>
  );
}
