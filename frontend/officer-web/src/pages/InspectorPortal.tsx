export default function InspectorPortal(){
  return (
    <div style={{maxWidth:1280, margin:'0 auto', padding:16}}>
      <h2>Field Inspector — 01 SELECT TARGET → 08 SEAL</h2>
      <div style={{border:'1px solid #f59e0b', background:'#fffbeb', padding:10, borderRadius:6, fontSize:12}}>AI PRIORITY: FPS-0102 score 0.87 — stock variance 12%, delivery variance 3 times, grievances 2 — <em>AI prioritizes attention, inspector makes finding</em></div>
      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginTop:12}}>
        <div style={{border:'1px solid #cbd5e1', padding:12, borderRadius:6}}>
          <strong>Select Target</strong>
          <div style={{fontSize:12, marginTop:6}}>400 inspections in dataset — real stock_expected vs observed variance</div>
          <ul style={{fontSize:12}}><li>FPS-0102 — HIGH variance — Inspect first</li><li>FPS-0037 — CAPACITY flagged</li></ul>
        </div>
        <div style={{border:'1px solid #0f2a44', padding:12, borderRadius:6}}>
          <strong>Seal Record</strong>
          <div style={{fontSize:11, marginTop:6}}>SHA256: <code>a7f3…</code> — immutable. Evidence panel shows stock_register_verified, epos_verified.</div>
          <button style={{marginTop:8, padding:'8px 12px', background:'#0f2a44', color:'#fff', border:'none', borderRadius:4}}>SEAL INSPECTION</button>
        </div>
      </div>
    </div>
  )
}
