const CHAIN = ['BENEFICIARY','INTENT','FORECAST','LOCK','ALLOCATION','MANIFEST','VEHICLE','ROUTE','DELIVERY','ePOS','RECONCILIATION','INSPECTION','AUDIT'];
export default function TraceTimeline({active}:{active:string}){
  return (
    <div style={{display:'flex', gap:4, overflowX:'auto', padding:'8px 0'}}>
      {CHAIN.map(n=>(
        <span key={n} style={{padding:'6px 8px', borderRadius:6, fontSize:11, fontWeight: n===active?700:400, background: n===active?'#0f2a44':'#e2e8f0', color: n===active?'#fff':'#334155', whiteSpace:'nowrap'}}>
          {n}
        </span>
      ))}
    </div>
  )
}
