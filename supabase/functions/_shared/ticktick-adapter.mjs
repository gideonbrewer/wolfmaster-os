// Server-only TickTick Open API transport. Never import into the browser bundle.
// Official reference: https://developer.ticktick.com/docs/openapi.md (2026-10-29).
const BASE='https://api.ticktick.com/open/v1';
const idPattern=/^[A-Za-z0-9_-]{1,128}$/;
export const validId=value=>typeof value==='string'&&idPattern.test(value);
export class TickTickError extends Error{constructor(code){super(code);this.code=code;}}
export function createTickTickAdapter({accessToken,fetchImpl=fetch}){
 if(typeof accessToken!=='string'||!accessToken.trim())throw new TickTickError('credential_unavailable');
 async function call(path,method='GET'){
  let response;
  try{response=await fetchImpl(BASE+path,{method,headers:{Authorization:'Bearer '+accessToken,Accept:'application/json'},redirect:'error',signal:AbortSignal.timeout(10000)});}catch{throw new TickTickError('provider_outcome_unknown');}
  if(!response.ok)throw new TickTickError(response.status===401||response.status===403?'provider_authorization_failed':response.status===429?'provider_rate_limited':response.status===404?'provider_record_unavailable':'provider_request_failed');
  if(method==='POST')return; // A 200 is only acknowledgement, never completion proof.
  try{return await response.json();}catch{throw new TickTickError('provider_invalid_response');}
 }
 const path=(projectId,taskId)=>{if(!validId(projectId)||!validId(taskId))throw new TickTickError('invalid_record_id');return `/project/${encodeURIComponent(projectId)}/task/${encodeURIComponent(taskId)}`;};
 return {
  listProjects:()=>call('/project'),
  getProjectData:({projectId})=>{if(!validId(projectId))throw new TickTickError('invalid_project_id');return call(`/project/${encodeURIComponent(projectId)}/data`);},
  getTask:({projectId,taskId})=>call(path(projectId,taskId)),
  completeTask:({projectId,taskId})=>call(path(projectId,taskId)+'/complete','POST'),
 };
}
export async function taskSnapshot(raw,projectId,taskId){
 if(!validId(projectId)||!validId(taskId)||!raw||raw.id!==taskId||raw.projectId!==projectId||![-1,0,2].includes(raw.status)||typeof raw.title!=='string')throw new TickTickError('provider_record_mismatch');
 const snapshot={id:raw.id,projectId:raw.projectId,title:raw.title,status:raw.status,completed:raw.status===2,dueDate:raw.dueDate||null,priority:raw.priority??0,modifiedTime:raw.modifiedTime||null};
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(snapshot)));
 return {...snapshot,revision:Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('')};
}
