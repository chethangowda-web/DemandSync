import { STAGES } from '../types/workflow';
export default function CycleHeader({cycle, state}:{cycle:string, state:string}){
  return (
    <div style={{border:'2px solid #0f2a44', padding:'16px', background:'#f8fafc', fontFamily:'Inter, system-ui'}}>
      <div style={{display:'flex', justifyContent:'space-between'}}>
        <strong>DemandSYNC | {cycle} CYCLE</strong>
        <span style={{background:'#0f2a44', color:'#fff', padding:'4px 10px', borderRadius:4}}>{state}</span>
      </div>
      <div style={{display:'flex', gap:8, marginTop:12, flexWrap:'wrap'}}>
        {STAGES.map(s=>(
          <span key={s.key} style={{
            padding:'6px 10px', borderRadius:20, fontSize:12, fontWeight:600,
            background: s.status==='ACTIVE' ? '#0f2a44' : s.status==='COMPLETE' ? '#16a34a' : s.status==='BLOCKED' ? '#dc2626' : '#e5e7eb',
            color: s.status==='PENDING' ? '#111' : '#fff',
            border: s.status==='ACTIVE' ? '3px solid #facc15' : 'none'
          }}>
            {s.status==='COMPLETE'?'✓':s.status==='ACTIVE'?'●':s.status==='BLOCKED'?'!':'○'} {s.label}
          </span>
        ))}
      </div>
      <div style={{fontSize:12, color:'#475569', marginTop:8}}>Current stage visually dominant — pulsing border on ACTIVE · Click any stage for evidence drawer</div>
    </div>
  )
}
