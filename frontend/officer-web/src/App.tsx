import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import DSOControlCentre from './pages/DSOControlCentre';
import AdminDataTrust from './pages/AdminDataTrust';
import InspectorPortal from './pages/InspectorPortal';
import FPSPortal from './pages/FPSPortal';
import AuditorPortal from './pages/AuditorPortal';
export default function App(){
  return (
    <BrowserRouter>
      <nav style={{display:'flex', gap:10, padding:10, background:'#0f2a44', color:'#fff'}}>
        <Link to="/" style={{color:'#fff'}}>DSO Control Centre</Link>
        <Link to="/admin" style={{color:'#fff'}}>Admin Data Trust</Link>
        <Link to="/fps" style={{color:'#fff'}}>FPS</Link>
        <Link to="/inspector" style={{color:'#fff'}}>Inspector</Link>
        <Link to="/auditor" style={{color:'#fff'}}>Auditor</Link>
        <span style={{marginLeft:'auto', fontSize:11, opacity:0.8}}>Same FastAPI + PostgreSQL + 83k real rows — no mock arrays</span>
      </nav>
      <Routes>
        <Route path="/" element={<DSOControlCentre/>} />
        <Route path="/admin" element={<AdminDataTrust/>} />
        <Route path="/fps" element={<FPSPortal/>} />
        <Route path="/inspector" element={<InspectorPortal/>} />
        <Route path="/auditor" element={<AuditorPortal/>} />
      </Routes>
      <div style={{textAlign:'center', fontSize:11, color:'#64748b', padding:10, borderTop:'1px solid #e2e8f0', marginTop:20}}>
        DemandSYNC — AI PREDICTS → RULES VALIDATE → OPTIMIZATION ALLOCATES → HUMAN AUTHORIZES → SYSTEM VERIFIES → AUDIT
      </div>
    </BrowserRouter>
  )
}
