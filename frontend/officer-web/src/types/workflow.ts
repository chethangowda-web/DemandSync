export type StageStatus = 'COMPLETE' | 'ACTIVE' | 'BLOCKED' | 'PENDING';
export interface Stage { id:number; key:string; label:string; status:StageStatus; }
export const STAGES: Stage[] = [
  {id:1,key:'MONITOR',label:'01 MONITOR',status:'COMPLETE'},
  {id:2,key:'VALIDATE',label:'02 VALIDATE',status:'COMPLETE'},
  {id:3,key:'LOCK',label:'03 LOCK',status:'ACTIVE'},
  {id:4,key:'ALLOCATE',label:'04 ALLOCATE',status:'PENDING'},
  {id:5,key:'OPTIMIZE',label:'05 OPTIMIZE',status:'PENDING'},
  {id:6,key:'AUTHORIZE',label:'06 AUTHORIZE',status:'PENDING'},
  {id:7,key:'TRACK',label:'07 TRACK',status:'PENDING'},
  {id:8,key:'DELIVER',label:'08 DELIVER',status:'PENDING'},
  {id:9,key:'VERIFY',label:'09 VERIFY',status:'PENDING'},
  {id:10,key:'RECONCILE',label:'10 RECONCILE',status:'PENDING'},
  {id:11,key:'INSPECT',label:'11 INSPECT',status:'PENDING'},
  {id:12,key:'AUDIT',label:'12 AUDIT',status:'PENDING'},
  {id:13,key:'CLOSE',label:'13 CLOSE',status:'PENDING'},
];
export interface AISignal { service:string; prediction:number; confidence:number; reason:string; supporting_data:any; model_version:string; generated_at:string; }
