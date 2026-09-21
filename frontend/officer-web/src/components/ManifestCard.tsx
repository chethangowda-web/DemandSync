export default function ManifestCard({m}:{m:any}){
  return (
    <div style={{border:'2px solid #0f2a44', borderRadius:8, padding:12, background:'#fff'}}>
      <div style={{display:'flex', justifyContent:'space-between'}}>
        <strong>{m.manifest_id}</strong>
        <span style={{background: m.constraint_status==='READY'?'#16a34a':'#dc2626', color:'#fff', padding:'2px 8px', borderRadius:4, fontSize:11}}>{m.constraint_status}</span>
      </div>
      <div style={{fontSize:12, marginTop:6}}>Cycle {m.cycle} · {m.warehouse_id} → {m.vehicle_id} · {m.total_kg} kg · {m.route_distance_km} km · {m.route_duration_min} min</div>
      <div style={{fontSize:11, color:'#475569', marginTop:4}}>SHA256: <code>{m.sha256_hash?.slice(0,16)}...</code> · QR: {m.qr_payload}</div>
      <div style={{fontSize:11, marginTop:4}}>Status: <strong>{m.manifest_status}</strong> {m.manifest_status==='LOCKED' && '🔒 IMMUTABLE'}</div>
    </div>
  )
}
