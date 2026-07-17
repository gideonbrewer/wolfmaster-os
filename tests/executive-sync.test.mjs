import assert from 'node:assert/strict';

const TYPES=['task','project','milestone','waiting','scheduled','decision','guardrail','note'];
const STATUSES=['inbox','next','active','waiting','scheduled','blocked','completed','deferred','archived'];
const CANONICAL=['wolfmaster','notion','calendar','gmail','reminders','external'];
const PACKET_TYPES=['baseline','delta','reconciliation','correction','completion','emergency'];

function norm(v){ return String(v||'').toLowerCase().replace(/[’‘]/g,"'").replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' '); }
function stableHash(v){ const s=typeof v==='string'?v:JSON.stringify(v||{}); let h=2166136261; for(let i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h,16777619); } return (h>>>0).toString(36); }
function packetType(packet){ const t=String(packet?.packetType||packet?.type||'delta').toLowerCase(); return PACKET_TYPES.includes(t)?t:'delta'; }
function packetId(packet){ return String(packet?.packetId||packet?.id||`${packet?.sourceSystem||'manual'}:${packetType(packet)}:${packet?.generatedAt||'today'}:${stableHash({items:packet?.items,today:packet?.today})}`); }
function type(v){ const x=String(v||'task').toLowerCase(); return TYPES.includes(x)?x:'task'; }
function status(v,t){ const x=String(v||'').toLowerCase(); return STATUSES.includes(x)?x:t==='waiting'?'waiting':t==='scheduled'?'scheduled':'inbox'; }
function canonical(v){ const x=String(v||'wolfmaster').toLowerCase(); return CANONICAL.includes(x)?x:'external'; }
function fingerprint(item){ return ['wmexec',norm(item.title),norm(item.domain),norm(item.type),norm(item.projectId||item.project||''),norm(item.owner||'')].filter(Boolean).join('|'); }
function identity(item){ return item.sourceSystem&&item.sourceId?`${item.sourceSystem}:${item.sourceId}`:fingerprint(item); }
function normalize(raw,packet={}){
  const t=type(raw.type);
  const item={title:String(raw.title||'Untitled').trim(),domain:raw.domain||'Personal Systems',type:t,status:status(raw.status,t),priority:String(raw.priority||'P3').toUpperCase(),owner:raw.owner||'Gideon',nextAction:raw.nextAction||'',sourceSystem:String(raw.sourceSystem||packet.sourceSystem||'manual').toLowerCase(),sourceId:raw.sourceId||'',canonicalSystem:canonical(raw.canonicalSystem),actionMode:raw.actionMode||'',estimatedMinutes:raw.estimatedMinutes||'',location:raw.location||'',requiredTools:Array.isArray(raw.requiredTools)?raw.requiredTools:(raw.requiredTools?[raw.requiredTools]:[]),energyLevel:raw.energyLevel||'',focusLevel:raw.focusLevel||'',preferredTimeOfDay:raw.preferredTimeOfDay||'',batchEligible:raw.batchEligible!==undefined?!!raw.batchEligible:true,batchId:raw.batchId||'',preparationNeeded:raw.preparationNeeded||''};
  item.identity=identity(item); item.fingerprint=fingerprint(item); return item;
}
function comparable(item){ const c={...item}; delete c.id; delete c.identity; delete c.fingerprint; return JSON.stringify(c); }
function merge(prev=[],incoming=[]){
  const items=prev.map(x=>({...x,identity:x.identity||identity(x),fingerprint:x.fingerprint||fingerprint(x)}));
  const byId=new Map(items.map((x,i)=>[x.identity,i]));
  const byFp=new Map(items.map((x,i)=>[x.fingerprint,i]));
  const conflicts=[]; const result={created:0,updated:0,skipped:0,conflicted:0};
  incoming.forEach(raw=>{
    const item=normalize(raw,{sourceSystem:'chatgpt'});
    const idx=byId.has(item.identity)?byId.get(item.identity):byFp.get(item.fingerprint);
    if(idx==null){ items.push({...item,id:`i-${items.length}`}); result.created++; return; }
    const current=items[idx];
    if(comparable(current)===comparable(item)){ result.skipped++; return; }
    if(canonical(current.canonicalSystem)!=='wolfmaster'&&canonical(current.canonicalSystem)!==canonical(item.canonicalSystem)){ conflicts.push({current,item}); result.conflicted++; return; }
    items[idx]={...current,...item,id:current.id}; result.updated++;
  });
  return {items,conflicts,result};
}

const packet=[{title:'Finalize the WolfLock V2 survey',domain:'WolfLock',type:'milestone',status:'active',priority:'P1',owner:'Gideon',canonicalSystem:'notion'}];
const first=merge([],packet);
const second=merge(first.items,packet);
assert.equal(first.result.created,1);
assert.equal(second.items.length,1);
assert.equal(second.result.skipped,1);

const conflict=merge(first.items,[{...packet[0],nextAction:'Overwrite from different source',canonicalSystem:'gmail'}]);
assert.equal(conflict.result.conflicted,1);
assert.equal(conflict.items[0].nextAction,'');

const update=merge(first.items,[{...packet[0],nextAction:'Accepted update',canonicalSystem:'notion'}]);
assert.equal(update.result.updated,1);
assert.equal(update.items[0].nextAction,'Accepted update');

const meta=normalize({title:'Call Hanover',actionMode:'call',estimatedMinutes:10,requiredTools:['phone'],energyLevel:'low',focusLevel:'shallow',batchEligible:true});
assert.equal(meta.actionMode,'call');
assert.equal(meta.estimatedMinutes,10);
assert.deepEqual(meta.requiredTools,['phone']);
assert.equal(meta.focusLevel,'shallow');
assert.equal(meta.batchEligible,true);

const deltaPacket={packetType:'delta',packetId:'daily-delta-1',sourceSystem:'chatgpt',items:[{title:'Send Delta receipts'}]};
assert.equal(packetType(deltaPacket),'delta');
assert.equal(packetId(deltaPacket),'daily-delta-1');
assert.equal(packetType({packetType:'seed'}),'delta');
assert.equal(packetId({sourceSystem:'chatgpt',packetType:'completion',generatedAt:'2026-07-17',items:[{title:'Done'}]}),packetId({sourceSystem:'chatgpt',packetType:'completion',generatedAt:'2026-07-17',items:[{title:'Done'}]}));

console.log('executive sync tests passed');
