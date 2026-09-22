import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import RequireRole from './auth/RequireRole';
import Login from './pages/Login';
import ChangePassword from './pages/ChangePassword';
import DsoLayout from './dso/DsoLayout';
import CommandCentre from './dso/pages/CommandCentre';
import DemandIntelligence from './dso/pages/DemandIntelligence';
import AllocationPage from './dso/pages/Allocation';
import OptimizationPage from './dso/pages/Optimization';
import DispatchPage from './dso/pages/Dispatch';
import TrackingPage from './dso/pages/Tracking';
import ReconciliationPage from './dso/pages/Reconciliation';
import ExceptionsPage from './dso/pages/ExceptionsPage';
import AuditPage from './dso/pages/Audit';
import AdminDataTrust from './pages/AdminDataTrust';
import InspectorPortal from './pages/InspectorPortal';
import FPSPortal from './pages/FPSPortal';
import AuditorPortal from './pages/AuditorPortal';

function Shell() {
  const { user, logout, loading } = useAuth();
  const { pathname } = useLocation();
  // The DSO control centre carries its own operations rail and command bar; a second global nav on top
  // of it would just be chrome competing with chrome.
  const ownsItsChrome = pathname.startsWith('/dso');
  return (
    <>
      {!ownsItsChrome && (
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
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/change-password" element={<ChangePassword />} />
        <Route path="/dso" element={<RequireRole portal="/dso"><DsoLayout /></RequireRole>}>
          <Route index element={<CommandCentre />} />
          <Route path="demand" element={<DemandIntelligence />} />
          <Route path="allocation" element={<AllocationPage />} />
          <Route path="optimization" element={<OptimizationPage />} />
          <Route path="dispatch" element={<DispatchPage />} />
          <Route path="tracking" element={<TrackingPage />} />
          <Route path="reconciliation" element={<ReconciliationPage />} />
          <Route path="exceptions" element={<ExceptionsPage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
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
