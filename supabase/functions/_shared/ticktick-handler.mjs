import {createTickTickAdapter,taskSnapshot,validId} from './ticktick-adapter.mjs';
// A future reviewed deployment must deliberately replace these gates.
// Browser input, headers, and OAuth/token possession cannot enable them.
export const DISABLED_TICKTICK_POLICY=Object.freeze({securityApproved:false,readsEnabled:false,writesEnabled:false,ownerUserId:null,projectIds:[],allowedOrigins:[]});
export function createTickTickHandler({authenticate,policy=DISABLED_TICKTICK_POLICY,resolveCredential,operationStore=null,rateLimiter=null,fetchImpl=fetch,clock=()=>new Date().toISOString()}){
 return async request=>{
  const origin=request.headers.get('origin');
  const headers={'Content-Type':'application/json','Cache-Control':'no-store','Vary':'Origin'};
  const response=(status,body)=>new Response(JSON.stringify(body),{status,headers});
  if(origin){if(!policy.allowedOrigins.includes(origin))return response(403,{error:'origin_not_allowed'});headers['Access-Control-Allow-Origin']=origin;headers['Access-Control-Allow-Headers']='authorization, content-type, apikey';headers['Access-Control-Allow-Methods']='POST, OPTIONS';}
  if(request.method==='OPTIONS')return new Response(null,{status:204,headers});
  if(request.method!=='POST')return response(405,{error:'method_not_allowed'});
  const bearer=request.headers.get('authorization')||'';
  if(!/^Bearer [^\s]+$/.test(bearer))return response(401,{error:'unauthorized'});
  let user;try{user=await authenticate(bearer);}catch{return response(401,{error:'unauthorized'});}
  if(!user?.id||user.isAnonymous!==false)return response(401,{error:'unauthorized'});
  if(!policy.securityApproved||!policy.readsEnabled||!policy.ownerUserId||!policy.projectIds.length)return response(503,{error:'ticktick_disabled'});
  if(user.id!==policy.ownerUserId)return response(403,{error:'owner_not_allowed'});
  if(!rateLimiter)return response(503,{error:'rate_limit_store_unavailable'});
  try{if(!await rateLimiter.allow(user.id))return response(429,{error:'rate_limited'});}catch{return response(503,{error:'rate_limit_store_unavailable'});}
  let body;try{const reader=request.body?.getReader();let size=0,raw='';const decoder=new TextDecoder();if(reader)while(true){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>4096){await reader.cancel();return response(413,{error:'request_too_large'});}raw+=decoder.decode(value,{stream:true});}raw+=decoder.decode();body=JSON.parse(raw);}catch{return response(400,{error:'invalid_json'});}
  if(!body||Array.isArray(body)||typeof body!=='object'||Object.keys(body).some(k=>!['action','projectId','taskId','expectedRevision','requestId'].includes(k)))return response(400,{error:'invalid_request'});
  if(!['projects','project','task','complete'].includes(body.action))return response(400,{error:'unsupported_action'}); // No habit writes, creates, deletes or reopen.
  if(body.action!=='projects'&&(!validId(body.projectId)||!policy.projectIds.includes(body.projectId)))return response(403,{error:'project_not_allowed'});
  if(['task','complete'].includes(body.action)&&!validId(body.taskId))return response(400,{error:'invalid_task_id'});
  if(body.action==='complete'){
   if(!policy.writesEnabled)return response(403,{error:'ticktick_writes_disabled'});
   if(!operationStore)return response(503,{error:'durable_operation_store_unavailable'});
   if(!/^[a-f0-9]{64}$/.test(body.expectedRevision||'')||!validId(body.requestId))return response(400,{error:'revision_and_request_id_required'});
  }
  let credential;
  try{credential=await resolveCredential(user.id);}catch{return response(503,{error:'credential_unavailable'});}
  if(!credential?.accessToken||credential.ownerUserId!==user.id||credential.accountVerified!==true)return response(503,{error:'verified_credential_unavailable'});
  const adapter=createTickTickAdapter({accessToken:credential.accessToken,fetchImpl});
  const ref={projectId:body.projectId,taskId:body.taskId};
  if(body.action==='complete'){
   let reservation;
   const operation={userId:user.id,requestId:body.requestId,action:'complete',...ref,expectedRevision:body.expectedRevision};
   try{reservation=await operationStore.reserve(operation);}catch{return response(503,{error:'operation_store_unavailable'});}
   if(reservation.state==='conflict')return response(409,{error:'request_id_conflict'});
   if(reservation.state==='existing')return response(reservation.result?.httpStatus||409,reservation.result?.body||{status:'unconfirmed',reason:'operation_pending_reconciliation'});
   if(reservation.state!=='reserved')return response(503,{error:'operation_store_unavailable'});
   let outcome;
   try{
    const current=await taskSnapshot(await adapter.getTask(ref),ref.projectId,ref.taskId);
    if(current.status===-1)outcome={httpStatus:409,body:{status:'conflict',reason:'canonical_record_abandoned'}};
    else if(current.revision!==body.expectedRevision)outcome={httpStatus:409,body:{status:'conflict',reason:'canonical_record_changed'}};
    else if(current.completed)outcome={httpStatus:200,body:{status:'confirmed',record:current,observedAt:clock(),changed:false}};
    else{
     await adapter.completeTask(ref);
     const observed=await taskSnapshot(await adapter.getTask(ref),ref.projectId,ref.taskId);
     outcome=observed.completed?{httpStatus:200,body:{status:'confirmed',record:observed,observedAt:clock(),changed:true}}:{httpStatus:409,body:{status:'unconfirmed',reason:'canonical_readback_did_not_confirm'}};
    }
   }catch{outcome={httpStatus:409,body:{status:'unconfirmed',reason:'reconcile_before_retry'}};}
   try{await operationStore.finish(operation,outcome);}catch{return response(503,{status:'unconfirmed',reason:'confirmation_not_durably_recorded'});}
   return response(outcome.httpStatus,outcome.body);
  }
  try{
   if(body.action==='projects'){
    const list=await adapter.listProjects();if(!Array.isArray(list))throw Error();
    return response(200,{projects:list.filter(x=>policy.projectIds.includes(x.id)).map(x=>({id:x.id,name:String(x.name||'Untitled')})),coverage:'explicit-project-allowlist',observedAt:clock()});
   }
   if(body.action==='task')return response(200,{record:await taskSnapshot(await adapter.getTask(ref),ref.projectId,ref.taskId),observedAt:clock()});
   const data=await adapter.getProjectData(ref);
   if(data.project?.id!==ref.projectId||!Array.isArray(data.tasks))throw Error();
   const tasks=await Promise.all(data.tasks.map(t=>taskSnapshot(t,ref.projectId,t.id)));
   return response(200,{project:{id:ref.projectId,name:String(data.project.name||'Untitled')},tasks,coverage:'one-allowlisted-project',observedAt:clock()});
  }catch{return response(502,{error:'provider_read_unavailable'});}
 };
}
