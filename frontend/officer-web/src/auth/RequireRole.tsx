import { Link, Navigate, useLocation } from 'react-router-dom';
import { ReactNode } from 'react';
import { PORTAL_ROLE, useAuth } from './AuthContext';

// Client-side routing guard. It only decides what to *show*; every API call is authorised by the server.
export default function RequireRole({ portal, children }: { portal: string; children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <p style={{ padding: 24 }}>Checking your session…</p>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  if (user.role !== PORTAL_ROLE[portal]) {
    return (
      <div style={{ maxWidth: 520, margin: '64px auto', padding: 24, border: '1px solid #fecaca', background: '#fef2f2', borderRadius: 8 }}>
        <h2 style={{ marginTop: 0 }}>Access restricted</h2>
        <p>Your account does not have permission to access this section.</p>
        <Link to={user.portal}>Go to your portal</Link>
      </div>
    );
  }
  return <>{children}</>;
}
