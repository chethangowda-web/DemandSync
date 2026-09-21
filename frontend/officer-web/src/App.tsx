import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import RequireRole from './auth/RequireRole';
import Login from './pages/Login';
import ChangePassword from './pages/ChangePassword';
import DSOControlCentre from './pages/DSOControlCentre';
import AdminDataTrust from './pages/AdminDataTrust';
import InspectorPortal from './pages/InspectorPortal';
import FPSPortal from './pages/FPSPortal';
import AuditorPortal from './pages/AuditorPortal';

function Shell() {
  const { user, logout, loading } = useAuth();
  return (
    <>
      <nav style={{ display: 'flex', gap: 12, padding: 10, background: '#0f2a44', color: '#fff', alignItems: 'center' }}>
        <strong>DemandSYNC</strong>
        {user && (
          <>
            <span style={{ opacity: 0.8, fontSize: 13 }}>{user.role}</span>
            <span style={{ marginLeft: 'auto', fontSize: 13 }}>{user.name}</span>
            <Link to="/change-password" style={{ color: '#fff', fontSize: 13 }}>Change password</Link>
            <button onClick={logout} style={{ background: 'transparent', color: '#fff', border: '1px solid #fff', borderRadius: 4, cursor: 'pointer' }}>Sign out</button>
          </>
        )}
      </nav>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/change-password" element={<ChangePassword />} />
        <Route path="/dso" element={<RequireRole portal="/dso"><DSOControlCentre /></RequireRole>} />
        <Route path="/admin" element={<RequireRole portal="/admin"><AdminDataTrust /></RequireRole>} />
        <Route path="/fps" element={<RequireRole portal="/fps"><FPSPortal /></RequireRole>} />
        <Route path="/inspector" element={<RequireRole portal="/inspector"><InspectorPortal /></RequireRole>} />
        <Route path="/auditor" element={<RequireRole portal="/auditor"><AuditorPortal /></RequireRole>} />
        <Route path="*" element={loading ? null : <Navigate to={user ? user.portal : '/login'} replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
      <AuthProvider><Shell /></AuthProvider>
    </BrowserRouter>
  );
}
