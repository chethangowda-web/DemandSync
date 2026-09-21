export default function EvidencePanel({title, data}:{title:string, data:any}){
  return (
    <div style={{border:'1px solid #cbd5e1', borderRadius:6, padding:10, background:'#f8fafc'}}>
      <strong style={{fontSize:12}}>{title} — [VIEW SOURCE]</strong>
      <pre style={{fontSize:11, whiteSpace:'pre-wrap', background:'#fff', padding:8, borderRadius:4, marginTop:6}}>{JSON.stringify(data,null,2)}</pre>
      <div style={{fontSize:11, color:'#64748b'}}>Every number traceable to PostgreSQL + dataset CSV row</div>
    </div>
  )
}
