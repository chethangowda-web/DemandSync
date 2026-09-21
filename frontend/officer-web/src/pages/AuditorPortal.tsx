import TraceTimeline from '../components/TraceTimeline';
export default function AuditorPortal(){
  return (
    <div style={{maxWidth:1280, margin:'0 auto', padding:16}}>
      <h2>Auditor — TRACE → VERIFY → FINDING → SEAL</h2>
      <TraceTimeline active="AUDIT" />
      <div style={{marginTop:10, border:'1px solid #0f2a44', padding:12, borderRadius:6, background:'#f8fafc'}}>
        <strong>Trace: BEN-000421 → INT-0001234 → Forecast 840kg (FPS-0102) → LOCK 2026-01 hash a3f5… → Alloc ALLOC-000123 → Manifest MAN-000007 → Vehicle VEH-0007 → Delivery DEL-000123 (VARIANCE 2%) → ePOS EPOS-0000456 SUCCESS 5kg → Inspection INSP-000089 SEALED → Exceptions 2</strong>
        <div style={{fontSize:11, marginTop:6}}>Click any node — evidence drawer opens with DB row + hash. Full chain 83k rows.</div>
      </div>
      <div style={{marginTop:10, border:'1px solid #f59e0b', background:'#fffbeb', padding:10, borderRadius:6, fontSize:12}}>
        <strong>AI AUDIT INTELLIGENCE — OBSERVATION</strong><br/>Planned vs delivered mismatch repeated at FPS-0102 (4 cycles) — confidence 82% — evidence: 4 deliveries VARIANCE, 2 inspections STOCK_VARIANCE — <em>Auditor makes finding</em>
      </div>
    </div>
  )
}
