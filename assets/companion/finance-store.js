/* Dedicated owner-scoped finance storage. No legacy storage, exports, AI or telemetry. */
(function(root){
  'use strict';
  const model=typeof module==='object'&&module.exports?require('./model.js'):root.WMCompanion;
  const fields={work:'work',consulting:'consulting',miningRevenue:'mining_revenue',miningExpenses:'mining_expenses',realized:'realized',unrealized:'unrealized',assets:'assets',liabilities:'liabilities'};
  const columns='id,user_id,kind,as_of_date,currency,coverage,source,schema_version,revision,created_at,updated_at,'+Object.values(fields).join(',');
  const uuid=x=>typeof x==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(x);
  const key=x=>[x.kind,x.date,x.currency].join(':');
  class FinanceError extends Error{constructor(code){super(code);this.code=code;}}
  function payload(raw,today){
    if(!['earnings','worth'].includes(raw.kind))throw new FinanceError('invalid');
    const clean=model.validateFinance(raw,today);
    if(clean.date<'1900-01-01'||clean.coverage.length>500)throw new FinanceError('invalid');
    const result={kind:clean.kind,as_of_date:clean.date,currency:clean.currency,coverage:clean.coverage,source:'manual',schema_version:1};
    for(const [ui,db] of Object.entries(fields)){
      const n=clean[ui]??null;
      // Reject precision loss instead of silently rounding money before persistence.
      if(n!==null&&(Math.abs(n)>9999999999999.99||!Number.isFinite(n)||Number(n.toFixed(2))!==n))throw new FinanceError('invalid');
      result[db]=n;
    }
    return result;
  }
  function decode(row,owner){
    if(!row||!uuid(row.id)||row.user_id!==owner||row.source!=='manual'||row.schema_version!==1||!Number.isSafeInteger(Number(row.revision))||Number(row.revision)<1)throw new FinanceError('invalid_response');
    const raw={kind:row.kind,date:row.as_of_date,currency:row.currency,coverage:row.coverage};
    for(const [ui,db] of Object.entries(fields)){
      if(row[db]!==null&&typeof row[db]!=='number'&&typeof row[db]!=='string')throw new FinanceError('invalid_response');
      raw[ui]=row[db]===null?null:Number(row[db]);
    }
    const normalized=payload(raw,new Date().toISOString().slice(0,10));
    for(const [ui,db] of Object.entries(fields))if(raw[ui]!==normalized[db])throw new FinanceError('invalid_response');
    return {...model.validateFinance(raw,new Date().toISOString().slice(0,10)),id:row.id,revision:Number(row.revision),saved:true};
  }
  function matches(row,body){return row&&row.kind===body.kind&&row.date===body.as_of_date&&row.currency===body.currency&&row.coverage===body.coverage&&Object.entries(fields).every(([ui,db])=>(row[ui]??null)===body[db]);}
  function createClient({enabled=false,url,publishableKey,getSession,fetchImpl=root.fetch,timeoutMs=15000}){
    let disposed=false;
    const controllers=new Set();
    function context(){
      if(!enabled)throw new FinanceError('disabled');
      if(disposed)throw new FinanceError('session_changed');
      const session=getSession?.();
      if(!uuid(session?.user?.id)||!session?.access_token)throw new FinanceError('auth');
      const base=new URL(url);
      if(base.protocol!=='https:'||base.username||base.password||base.search||base.hash||base.pathname!=='/')throw new FinanceError('configuration');
      return {owner:session.user.id,token:session.access_token,base:base.origin};
    }
    function assertCurrent(ctx){const now=context();if(now.owner!==ctx.owner||now.token!==ctx.token)throw new FinanceError('session_changed');}
    async function request(ctx,path,{method='GET',body}={}){
      assertCurrent(ctx);
      const ac=new AbortController();controllers.add(ac);const timer=setTimeout(()=>ac.abort(),timeoutMs);
      try{
        const response=await fetchImpl(ctx.base+path,{method,signal:ac.signal,redirect:'error',cache:'no-store',credentials:'omit',headers:{apikey:publishableKey,Authorization:'Bearer '+ctx.token,'Content-Type':'application/json',Prefer:'return=representation'},...(body?{body:JSON.stringify(body)}:{})});
        assertCurrent(ctx);
        if(!response.ok){
          if(response.status===409)throw new FinanceError('conflict');
          if(response.status===401||response.status===403)throw new FinanceError('auth');
          if(response.status>=500&&method!=='GET')throw new FinanceError('uncertain');
          throw new FinanceError('request_failed');
        }
        const data=await response.json();assertCurrent(ctx);return data;
      }catch(error){
        if(error instanceof FinanceError)throw error;
        throw new FinanceError(method==='GET'?'read_failed':'uncertain');
      }finally{clearTimeout(timer);controllers.delete(ac);}
    }
    async function verified(){
      const ctx=context();const user=await request(ctx,'/auth/v1/user');
      if(user?.id!==ctx.owner||user.is_anonymous!==false)throw new FinanceError('auth');
      return ctx;
    }
    function query(ctx,extra={}){return '/rest/v1/finance_snapshots?'+new URLSearchParams({select:columns,user_id:'eq.'+ctx.owner,...extra});}
    async function find(raw){
      const ctx=await verified();const rows=await request(ctx,query(ctx,{kind:'eq.'+raw.kind,as_of_date:'eq.'+raw.date,currency:'eq.'+raw.currency,limit:'2'}));
      if(!Array.isArray(rows)||rows.length>1)throw new FinanceError('invalid_response');
      return rows.length?decode(rows[0],ctx.owner):null;
    }
    return {
      enabled:enabled===true,
      dispose(){disposed=true;controllers.forEach(c=>c.abort());controllers.clear();},
      async load(){
        const ctx=await verified();let result=[];
        // Offset pagination avoids treating the server's first result page as all history.
        for(let offset=0;offset<10000;){
          const rows=await request(ctx,query(ctx,{order:'id.asc',offset:String(offset),limit:'200'}));
          if(!Array.isArray(rows))throw new FinanceError('invalid_response');
          if(!rows.length)return result;
          const batch=rows.map(row=>decode(row,ctx.owner));
          if(batch.some(row=>result.some(old=>old.id===row.id||key(old)===key(row))))throw new FinanceError('read_failed');
          result=result.concat(batch);offset+=rows.length;
        }
        throw new FinanceError('too_many_rows');
      },
      find,
      async save(raw,baseline){
        const body=payload(raw,new Date().toISOString().slice(0,10));
        const ctx=await verified();
        if(baseline&&(!uuid(baseline.id)||!Number.isSafeInteger(baseline.revision)||baseline.revision<1||key(raw)!==key(baseline)))throw new FinanceError('conflict');
        const result=await request(ctx,query(ctx,baseline?{id:'eq.'+baseline.id,revision:'eq.'+baseline.revision}:{}),{method:baseline?'PATCH':'POST',body:baseline?body:{...body,user_id:ctx.owner}});
        if(!Array.isArray(result)||result.length!==1)throw new FinanceError(baseline&&Array.isArray(result)&&result.length===0?'conflict':'uncertain');
        let saved;try{saved=decode(result[0],ctx.owner);}catch{throw new FinanceError('uncertain');}
        if(!matches(saved,body)||saved.revision!==(baseline?baseline.revision+1:1)||(baseline&&saved.id!==baseline.id))throw new FinanceError('uncertain');
        return saved;
      }
    };
  }
  const messages={disabled:'Session only · not uploaded or saved.',loading:'Loading saved finance snapshots…',ready:'Saved snapshots loaded. New changes require Save.',saving:'Saving… keep this tab open.',saved:'Saved to your finance account.',failed:'Save failed. Your draft is still here; nothing is marked saved.',conflict:'Another saved version exists. Review it before replacing anything. Your draft is still here.',uncertain:'Save outcome is unknown. Your draft is still here. Check the saved record before trying again.'};
  function createStore(client){
    let state={status:client.enabled?'loading':'disabled',rows:[],pending:null,current:null,reviewed:false,loaded:false,message:client.enabled?messages.loading:messages.disabled};
    let disposed=false,busy=false;const listeners=new Set();
    const emit=patch=>{if(disposed)return;state={...state,...patch};listeners.forEach(fn=>fn(state));};
    const status=(name,extra={})=>emit({status:name,message:messages[name],...extra});
    const remember=row=>model.upsertFinance(state.rows,row);
    return {
      getState:()=>state,
      subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},
      dispose(){disposed=true;client.dispose();listeners.clear();state={status:'disabled',rows:[],pending:null,current:null,loaded:false,message:messages.disabled};},
      async load(){
        if(!client.enabled||disposed||busy||state.pending)return false;
        busy=true;status('loading');
        try{const rows=await client.load();if(disposed)return false;status('ready',{rows,loaded:true,current:null});return true;}
        catch{status('failed',{loaded:false,message:'Could not load saved finance snapshots. Your draft is still here. Reload saved snapshots before saving.'});return false;}
        finally{busy=false;}
      },
      async save(raw){
        if(!client.enabled||disposed||busy||!state.loaded||state.pending)return false;
        let body;try{body=payload(raw,new Date().toISOString().slice(0,10));}catch{status('failed',{message:'Check the date, coverage and amounts. Use at most two decimal places within the supported range. Your draft is still here.'});return false;}
        const existing=state.rows.find(row=>key(row)===key(raw));
        // A draft made from an older displayed revision must not inherit a newer revision silently.
        const baseline=raw.id?{...raw,id:raw.id,revision:raw.revision}:existing;
        const pending={raw:{...raw},body,baseline:baseline?{...baseline}:null};
        busy=true;status('saving',{pending,current:null,reviewed:false});
        try{const row=await client.save(raw,baseline);if(disposed)return false;status('saved',{rows:remember(row),pending:null});return row;}
        catch(error){
          if(error.code==='conflict')status('conflict');
          else if(['uncertain','session_changed'].includes(error.code))status('uncertain');
          else status('failed',{pending:null});
          return false;
        }finally{busy=false;}
      },
      async reconcile(){
        if(disposed||busy||!state.pending)return false;
        busy=true;const pending=state.pending;
        try{
          const row=await client.find(pending.raw);if(disposed)return false;
          const expected=pending.baseline?pending.baseline.revision+1:1;
          if(row&&matches(row,pending.body)&&row.revision>=expected&&(!pending.baseline||row.id===pending.baseline.id)){
            status('saved',{rows:remember(row),pending:null,current:null,message:'Saved values confirmed by a fresh account read. Your draft remains available.'});return row;
          }
          status('conflict',{current:row,reviewed:true,message:row?messages.conflict:'No matching saved snapshot was found. Review this result, then explicitly allow a new save.'});return false;
        }catch{emit({message:'Could not check the saved record. Your draft and unresolved outcome remain; no write was retried.'});return false;}
        finally{busy=false;}
      },
      // Explicit user decision after a read: retain the local draft but rebase it on the observed revision.
      acceptCurrent(){
        if(disposed||busy||state.status!=='conflict'||!state.pending||!state.reviewed)return null;
        const draft={...state.pending.raw};delete draft.id;delete draft.revision;delete draft.saved;
        if(state.current)Object.assign(draft,{id:state.current.id,revision:state.current.revision});
        const rows=state.rows.filter(row=>key(row)!==key(draft));if(state.current)rows.push(state.current);
        status('ready',{rows,pending:null,current:null,message:'Draft retained against the reviewed version. Press Save to submit it.'});return draft;
      }
    };
  }
  const api={createClient,createStore,key,payload,FinanceError};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.WMFinance=api;
})(typeof globalThis!=='undefined'?globalThis:this);
