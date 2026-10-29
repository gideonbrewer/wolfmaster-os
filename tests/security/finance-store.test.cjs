const assert=require('node:assert/strict');
const {createClient,createStore,payload}=require('../../assets/companion/finance-store.js');
const owner='11111111-1111-4111-8111-111111111111',other='22222222-2222-4222-8222-222222222222';
const id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const raw={kind:'earnings',date:'2026-01-02',currency:'USD',coverage:'Synthetic work',work:'125'};
const row=(amount=125,revision=1)=>({id,user_id:owner,...payload({...raw,work:amount},'2026-10-29'),revision});
const reply=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
function harness({enabled=true,initial=[],handler,auth={id:owner,is_anonymous:false}}={}){
 let session={user:{id:owner},access_token:'synthetic-token'},rows=initial.map(x=>({...x}));const requests=[];
 const fetchImpl=async(url,options)=>{
  const u=new URL(url);requests.push({u,options});
  assert.equal(u.origin,'https://finance.invalid');assert.equal(options.credentials,'omit');assert.equal(options.cache,'no-store');assert.equal(options.redirect,'error');
  assert.equal(options.headers.Authorization,'Bearer '+session.access_token);
  if(u.pathname==='/auth/v1/user')return reply(auth);
  assert.equal(u.pathname,'/rest/v1/finance_snapshots');assert.equal(u.searchParams.get('user_id'),'eq.'+session.user.id);
  if(handler){const overridden=await handler({u,options,get rows(){return rows;},set rows(value){rows=value;}});if(overridden)return overridden;}
  if(options.method==='GET'){
   let result=rows.filter(x=>x.user_id===session.user.id);
   for(const k of ['id','kind','as_of_date','currency','revision'])if(u.searchParams.has(k))result=result.filter(x=>'eq.'+x[k]===u.searchParams.get(k));
   const offset=Number(u.searchParams.get('offset')||0);return reply(result.slice(offset,offset+Number(u.searchParams.get('limit')||200)));
  }
  const body=JSON.parse(options.body);
  assert(!('revision' in body));assert(!('id' in body));
  if(options.method==='POST'){
   assert.equal(body.user_id,owner);
   if(rows.some(x=>x.user_id===owner&&x.kind===body.kind&&x.as_of_date===body.as_of_date&&x.currency===body.currency))return reply({},409);
   const saved={...body,id,revision:1};rows.push(saved);return reply([saved],201);
  }
  assert.equal(options.method,'PATCH');assert(!('user_id' in body));
  const old=rows.find(x=>'eq.'+x.id===u.searchParams.get('id')&&'eq.'+x.revision===u.searchParams.get('revision'));
  if(!old)return reply([]);
  Object.assign(old,body,{revision:old.revision+1});return reply([{...old}]);
 };
 const client=createClient({enabled,url:'https://finance.invalid',publishableKey:'synthetic-public-key',getSession:()=>session,fetchImpl});
 return {client,store:createStore(client),requests,setSession:value=>{session=value;},get rows(){return rows;}};
}
async function run(){
 const off=harness({enabled:false});await off.store.load();await off.store.save(raw);assert.equal(off.requests.length,0);assert.equal(off.store.getState().status,'disabled');
 for(const auth of [{id:other,is_anonymous:false},{id:owner,is_anonymous:true},{id:owner}]){
  const h=harness({auth});assert.equal(await h.store.load(),false);assert.equal(h.requests.length,1);assert.equal(h.store.getState().loaded,false);assert.equal(await h.store.save(raw),false);
 }
 const h=harness();await h.store.load();const observed=[];h.store.subscribe(s=>observed.push(s.status));
 const saved=await h.store.save(raw);assert.equal(saved.saved,true);assert.equal(saved.revision,1);assert.deepEqual(observed,['saving','saved']);
 assert.equal(h.store.getState().rows.length,1);assert.equal(h.store.getState().rows[0].work,125);
 const updated=await h.store.save({...saved,work:150});assert.equal(updated.revision,2);assert.equal(h.rows[0].work,150);
 const patch=h.requests.findLast(x=>x.options.method==='PATCH');assert.equal(patch.u.searchParams.get('id'),'eq.'+id);assert.equal(patch.u.searchParams.get('revision'),'eq.1');
 // Stale displayed edits cannot silently inherit a newer revision after reload.
 h.rows[0].revision=3;h.rows[0].work=175;await h.store.load();assert.equal(await h.store.save({...updated,work:200}),false);assert.equal(h.store.getState().status,'conflict');assert.equal(h.rows[0].work,175);
 assert.equal(h.store.acceptCurrent(),null,'Must read the conflict before rebasing');
 await h.store.reconcile();assert.equal(h.store.getState().current.work,175);const retained=h.store.acceptCurrent();assert.equal(retained.work,200);assert.equal(retained.revision,3);assert.equal((await h.store.save(retained)).revision,4);
 // A concurrent insert is a conflict, never an unconditional merge-duplicates upsert.
 const duplicate=harness();await duplicate.store.load();duplicate.rows.push(row());await duplicate.store.save({...raw,work:999});assert.equal(duplicate.store.getState().status,'conflict');assert.equal(duplicate.rows[0].work,125);
 // A lost response may have committed: keep draft, block repeat writes, read back.
 let lost=true;const uncertain=harness({handler:async x=>{if(x.options.method==='POST'&&lost){lost=false;x.rows.push(row());throw Error('secret provider details');}}});
 await uncertain.store.load();await uncertain.store.save(raw);assert.equal(uncertain.store.getState().status,'uncertain');assert.equal(uncertain.store.getState().rows.length,0);assert.equal(uncertain.store.getState().pending.raw.coverage,raw.coverage);assert(!uncertain.store.getState().message.includes('secret'));
 const writes=()=>uncertain.requests.filter(x=>x.options.method==='POST').length;await uncertain.store.save(raw);assert.equal(writes(),1);await uncertain.store.reconcile();assert.equal(uncertain.store.getState().status,'saved');assert.equal(writes(),1);
 // No matching record is an explicit review decision, not an automatic retry.
 const absent=harness({handler:async x=>{if(x.options.method==='POST')throw Error('offline');}});await absent.store.load();await absent.store.save(raw);await absent.store.reconcile();assert.equal(absent.store.getState().status,'conflict');assert.equal(absent.store.getState().current,null);assert(absent.store.acceptCurrent());
 // Failed read keeps prior confirmed rows but disables writes until a complete reload.
 let failRead=false;const reads=harness({initial:[row()],handler:async x=>{if(failRead&&x.options.method==='GET')return reply({},503);}});await reads.store.load();failRead=true;await reads.store.load();assert.equal(reads.store.getState().rows.length,1);assert.equal(reads.store.getState().loaded,false);assert.equal(await reads.store.save(raw),false);
 // Table-missing/permission/malformed data never becomes a saved state.
 for(const result of [reply({},404),reply({},403),reply([{...row(),user_id:other}]),reply([{...row(),revision:0}])]){
  const bad=harness({handler:async x=>x.options.method==='POST'?result:undefined});await bad.store.load();await bad.store.save(raw);assert.notEqual(bad.store.getState().status,'saved');assert.equal(bad.store.getState().rows.length,0);
 }
 for(const work of ['1.001','0.000001','10000000000000','Infinity']){const bad=harness();await bad.store.load();const count=bad.requests.length;await bad.store.save({...raw,work});assert.equal(bad.requests.length,count);assert.equal(bad.store.getState().status,'failed');}
 // Server-imposed short pages are paginated until empty, not treated as all history.
 const many=Array.from({length:3},(_,i)=>({...row(),id:`aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa${i}`,as_of_date:`2026-01-0${i+1}`}));
 const paged=harness({initial:many,handler:async x=>{if(x.options.method==='GET'&&x.u.searchParams.has('offset'))return reply(x.rows.slice(Number(x.u.searchParams.get('offset')),Number(x.u.searchParams.get('offset'))+1));}});await paged.store.load();assert.equal(paged.store.getState().rows.length,3);
 // Disposal/account changes suppress late results and abort outstanding requests.
 let release;const pending=harness({handler:async x=>{if(x.options.method==='POST')return new Promise(resolve=>{release=()=>resolve(reply([row()],201));});}});await pending.store.load();const saving=pending.store.save(raw);while(!release)await new Promise(resolve=>setImmediate(resolve));pending.store.dispose();release();assert.equal(await saving,false);assert.deepEqual(pending.store.getState().rows,[]);assert(pending.requests.at(-1).options.signal.aborted);
 let releaseRead;const switched=harness({handler:async x=>{if(x.options.method==='GET')return new Promise(resolve=>{releaseRead=()=>resolve(reply([row()]));});}});const loading=switched.store.load();while(!releaseRead)await new Promise(resolve=>setImmediate(resolve));switched.setSession({user:{id:other},access_token:'different-synthetic-token'});releaseRead();await loading;assert.deepEqual(switched.store.getState().rows,[]);
 console.log('Finance store: disabled zero-network gate, verified owner, insert/CAS update, stale edit/concurrent insert conflicts, explicit rebase, unknown-write readback/no retry, error retention, validation, pagination and account/disposal races passed. Synthetic transport only.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
