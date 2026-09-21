// Real backend client — no mock arrays. Every call hits FastAPI + PostgreSQL.
const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
function authHeader(){ const t=localStorage.getItem('token'); return t?{Authorization:`Bearer ${t}`} : {}; }
export async function api(path:string, opts:RequestInit={}){
  const res = await fetch(`${BASE}${path}`, {headers:{'Content-Type':'application/json', ...authHeader(), ...(opts.headers as any)}, ...opts});
  if(!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}
export const getManifest = (id:string)=> api(`/api/v1/manifests/${id}`);
export const getForecast = (cycle:string, fps:string)=> api(`/api/v1/ai/forecast?cycle=${cycle}&fps_id=${fps}`);
export const getCycle = (cycle:string)=> api(`/api/v1/cycles/${cycle}`);
export const postLock = (cycle:string)=> api(`/api/v1/cycles/${cycle}/choice-window/close`, {method:'POST'});
export const getTelemetry = (vehicle:string)=> api(`/api/v1/telemetry?vehicle_id=${vehicle}`);
// If telemetry missing, UI shows "Live location unavailable" — never fake GPS
