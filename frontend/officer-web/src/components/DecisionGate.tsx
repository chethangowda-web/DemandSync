export interface Check { label:string; status:'PASS'|'FAIL'|'WARN'; detail?:string }
export default function DecisionGate({title, checks, action, onAction, disabled}:{title:string, checks:Check[], action:string, onAction:()=>void, disabled?:boolean}){
  const allPass = checks.every(c=>c.status==='PASS');
  return (
    <div style={{border:'2px solid #0f2a44', borderRadius:8, padding:16, background:'#fff'}}>
      <strong>{title}</strong>
      <div style={{marginTop:10}}>
        {checks.map(c=>(
          <div key={c.label} style={{display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid #e2e8f0'}}>
            <span>{c.label}</span>
            <span style={{color: c.status==='PASS'?'#16a34a':c.status==='FAIL'?'#dc2626':'#d97706', fontWeight:700}}>{c.status==='PASS'?'✓ PASS':c.status==='FAIL'?'✗ FAIL':'⚠ '+c.detail}</span>
          </div>
        ))}
      </div>
      <button onClick={onAction} disabled={disabled || !allPass} style={{marginTop:12, width:'100%', padding:'12px', background: allPass?'#0f2a44':'#94a3b8', color:'#fff', border:'none', borderRadius:6, fontWeight:700, cursor: allPass?'pointer':'not-allowed'}}>
        {action}
      </button>
      {!allPass && <div style={{fontSize:12, color:'#dc2626', marginTop:6}}>Resolve BLOCKED checks before authorization — exception panel shows rule_code</div>}
      {allPass && <div style={{fontSize:12, color:'#16a34a', marginTop:6}}>All gates PASS — human authorization required (AI cannot override)</div>}
    </div>
  )
}
