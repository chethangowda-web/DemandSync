export default function FPSPortal(){
  return (
    <div style={{maxWidth:1280, margin:'0 auto', padding:16}}>
      <h2>FPS Dealer — RECEIVE → VERIFY → INVENTORY → ePOS → RECONCILE</h2>
      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:10, marginTop:10}}>
        <div style={{border:'1px solid #cbd5e1', padding:10, borderRadius:6}}>Manifest MAN-000001 — 1,200kg rice — Verify QR <code>MAN|hash</code> — Status LOCKED 🔒</div>
        <div style={{border:'1px solid #f59e0b', background:'#fffbeb', padding:10, borderRadius:6, fontSize:12}}><strong>AI STOCK RISK</strong><br/>Projected stockout in ~9 days at current distribution rate.</div>
        <div style={{border:'1px solid #cbd5e1', padding:10, borderRadius:6, fontSize:12}}><strong>Delivery Variance</strong><br/>Planned 1200 vs Received 1188 — VARIANCE 1% — Pattern requires review (neutral).</div>
      </div>
      <div style={{marginTop:12, border:'1px solid #e2e8f0', padding:10, borderRadius:6, fontSize:12}}>ePOS: beneficiary BEN-000102 — entitlement 20kg — remaining 8kg — dispense 5kg — SUCCESS — receipt RCTxxxxxx — never exceeds entitlement</div>
    </div>
  )
}
