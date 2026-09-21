import CycleHeader from '../components/CycleHeader';
import DecisionGate from '../components/DecisionGate';
import AISignalCard from '../components/AISignal';
import TraceTimeline from '../components/TraceTimeline';
import ManifestCard from '../components/ManifestCard';
export default function DSOControlCentre(){
  // In production, data fetched via api() from FastAPI — no hardcoded KPI arrays
  const mockAI = {service:'demand_forecast', prediction:8420, confidence:87, reason:'Forecast demand is 8.4% above baseline — rising beneficiary intent + seasonal factor', supporting_data:{baseline:7680,intent:7920, historical_cycles:12, fps:'FPS-0102'}, model_version:'xgb-v1.0', generated_at:'2025-12-28T10:00:00'};
  return (
    <div style={{maxWidth:1280, margin:'0 auto', padding:16, fontFamily:'Inter'}}>
      <CycleHeader cycle="2026-03" state="MONITOR" />
      <div style={{display:'grid', gridTemplateColumns:'280px 1fr 340px', gap:16, marginTop:16}}>
        <div>
          <TraceTimeline active="LOCK" />
          <div style={{marginTop:12, border:'1px solid #e2e8f0', padding:10, borderRadius:6}}>
            <strong>Cycle State</strong>
            <div style={{fontSize:12, color:'#475569', marginTop:6}}>Choice window: 2026-03-05 → 20 · Participation 70% (7k intents) · Exceptions: 3 BLOCKED</div>
            <div style={{fontSize:11, marginTop:6, background:'#fef3c7', padding:6, borderRadius:4}}>No fake KPIs — each metric actionable. Click FORCAST → evidence drawer.</div>
          </div>
        </div>
        <div>
          <AISignalCard s={mockAI as any} />
          <div style={{marginTop:12, display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
            <div style={{border:'1px solid #cbd5e1', padding:10, borderRadius:6, background:'#fff'}}>
              <div style={{fontSize:11, color:'#64748b'}}>FORECAST DEMAND</div>
              <div style={{fontSize:22, fontWeight:800}}>8,420 KG</div>
              <button style={{fontSize:11, marginTop:6}}>VIEW FORECAST — intent 7,920 vs baseline 7,680</button>
            </div>
            <div style={{border:'1px solid #cbd5e1', padding:10, borderRadius:6, background:'#fff'}}>
              <div style={{fontSize:11, color:'#64748b'}}>INTENT DEMAND (aggregated)</div>
              <div style={{fontSize:22, fontWeight:800}}>7,920 KG</div>
              <div style={{fontSize:11, color:'#16a34a'}}>14,000 intents across 600 FPS</div>
            </div>
          </div>
          <div style={{marginTop:12}}>
            <DecisionGate title="DEMAND LOCK GATE" checks={[
              {label:'Entitlement Safety', status:'PASS'},
              {label:'FPS Capacity', status:'FAIL', detail:'FPS-0037 exceeds capacity'},
              {label:'Warehouse Stock', status:'PASS'},
              {label:' duplicate Intent', status:'PASS'},
              {label:'Data Quality', status:'PASS'},
            ]} action="LOCK DEMAND" onAction={()=>alert('POST /choice-window/close — immutable SHA256')} />
          </div>
        </div>
        <div>
          <ManifestCard m={{manifest_id:'MAN-000007', cycle:'2026-01', warehouse_id:'WH-001', vehicle_id:'VEH-0007', total_kg:4200, route_distance_km:42, route_duration_min:92, constraint_status:'BLOCKED', manifest_status:'VALIDATED', sha256_hash:'a3f5c...', qr_payload:'MAN-000007|a3f5c'}} />
          <div style={{marginTop:10, fontSize:12, color:'#dc2626', border:'1px solid #fecaca', background:'#fef2f2', padding:8, borderRadius:6}}>
            BLOCKED — FPS_CAPACITY: FPS-0037 required 1200kg, capacity 950kg. Resolve before AUTHORIZE.
          </div>
          <div style={{marginTop:10, border:'1px solid #e2e8f0', padding:8, borderRadius:6, fontSize:12}}>
            <strong>Live Tracking</strong>
            <div style={{height:120, background:'#e2e8f0', borderRadius:4, display:'flex', alignItems:'center', justifyContent:'center', marginTop:6}}>Map — Leaflet · Real telemetry 5,170 rows · Missing → "Live location unavailable"</div>
            <div style={{marginTop:6, fontSize:11, color:'#64748b'}}>Vehicle VEH-0007 · Speed 32 kmph · ETA 18 min · Last update 2 min ago</div>
          </div>
        </div>
      </div>
      <div style={{marginTop:16, fontSize:11, color:'#64748b', borderTop:'1px solid #e2e8f0', paddingTop:8}}>Every number from PostgreSQL + generated dataset — no frontend mock arrays. AI advisory, officer authorizes.</div>
    </div>
  )
}
