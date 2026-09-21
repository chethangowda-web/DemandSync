export default function HashBadge({hash, label}:{hash:string, label:string}){
  return <span style={{fontFamily:'monospace', fontSize:11, background:'#0f2a44', color:'#facc15', padding:'3px 6px', borderRadius:4}}>{label}: {hash?.slice(0,12)}…</span>
}
