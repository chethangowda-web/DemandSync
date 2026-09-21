import { STAGES } from '../types/workflow';
export default function WorkflowStepper({current}:{current:string}){
  return (
    <div style={{display:'flex', flexDirection:'column', gap:6, borderLeft:'3px solid #0f2a44', paddingLeft:12}}>
      {STAGES.map(s=>{
        const isCurrent = s.key===current;
        return (
          <div key={s.key} style={{display:'flex', alignItems:'center', gap:8, background: isCurrent?'#eff6ff':'transparent', padding:'6px 8px', borderRadius:6, border: isCurrent?'2px solid #0f2a44':'1px solid transparent'}}>
            <div style={{width:10,height:10,borderRadius:'50%', background: s.status==='COMPLETE'?'#16a34a':s.status==='ACTIVE'?'#facc15':s.status==='BLOCKED'?'#dc2626':'#cbd5e1'}}/>
            <span style={{fontWeight: isCurrent?700:400}}>{s.label}</span>
            <span style={{fontSize:11, color:'#64748b'}}>{s.status}</span>
          </div>
        )
      })}
    </div>
  )
}
