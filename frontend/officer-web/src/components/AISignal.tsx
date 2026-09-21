import { AISignal } from '../types/workflow';
export default function AISignalCard({s}:{s:AISignal}){
  return (
    <div style={{border:'1px solid #f59e0b', background:'#fffbeb', borderRadius:8, padding:12}}>
      <div style={{fontSize:11, fontWeight:800, color:'#92400e', letterSpacing:1}}>AI SIGNAL · {s.service.toUpperCase()}</div>
      <div style={{fontWeight:700, marginTop:4}}>{s.reason}</div>
      <div style={{fontSize:13, marginTop:6}}>Prediction: <strong>{s.prediction} kg</strong> · Confidence: <strong>{s.confidence}%</strong></div>
      <details style={{marginTop:8, fontSize:12, background:'#fff', padding:8, borderRadius:4}}>
        <summary>WHY · WHAT DATA · MODEL · TIMESTAMP — [VIEW SOURCE]</summary>
        <div style={{marginTop:6}}>Supporting: <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(s.supporting_data,null,2)}</pre></div>
        <div>Model: {s.model_version} · Generated: {s.generated_at}</div>
        <div style={{color:'#64748b', marginTop:4}}>AI is advisory — officer decides. Never "AI approved".</div>
      </details>
    </div>
  )
}
