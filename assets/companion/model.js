/* Pure projection contracts. No network, storage, credentials or live adapters. */
(function(root){
  const closed = x => x.done || x.archived || ['completed','closed','archived','deferred'].includes(String(x.status||'').toLowerCase());
  const title = x => x.title || x.text || 'Untitled';
  function sourceRef(item, executive=[]){
    const original=item.executiveItemId ? executive.find(x=>String(x.id)===String(item.executiveItemId)) : null;
    const record=original||item;
    const provider=String(record.sourceSystem||'').toLowerCase();
    const system=provider==='ticktick'?'ticktick':String(record.canonicalSystem||provider||'').toLowerCase();
    const external=!!item.executiveItemId || (!!system && !['wolfmaster','manual','local'].includes(system));
    return {system:system|| (external?'external':'wolfmaster'), id:String(record.sourceId||''), projectId:String(record.sourceProjectId||record.projectId||''), external, resolved:!item.executiveItemId||!!original};
  }
  // Block all record edits to imported projections. A focus-list removal is local
  // attention management; it is never a canonical deletion or completion.
  function protectList(previous,next,executive=[]){
    return next.map(row=>{const old=previous.find(x=>String(x.id)===String(row.id));return old&&sourceRef(old,executive).external ? old : row;});
  }
  function taskProjection({todos=[],weekly=[],tasks=[],careerTasks=[],errands=[],executive=[]}){
    const entries=[]; const seen=new Set();
    const add=(item,project,origin)=>{
      const ref=sourceRef(item,executive);
      const canonical=item.executiveItemId?executive.find(x=>String(x.id)===String(item.executiveItemId)):null;
      const row=canonical?{...item,...canonical,title:title(canonical),done:closed(canonical)}:item;
      if(closed(row)) return;
      const key=ref.external&&ref.id?`${ref.system}:${ref.projectId}:${ref.id}`:item.executiveItemId?`exec:${item.executiveItemId}`:`${origin}:${item.id}`;
      if(seen.has(key)) return; seen.add(key);
      entries.push({...row,key,project:row.projectName||row.project||row.domain||project||'Unassigned',source:ref.external?`${ref.system} · imported copy`:'WolfMaster · local record',ref});
    };
    // Canonical projections first so Daily 3 copies cannot mask completion/status.
    executive.filter(x=>['task','milestone','waiting'].includes(x.type)).forEach(x=>add(x,x.domain,'executive'));
    tasks.forEach(d=>(d.tasks||[]).forEach(t=>add(t,d.label,'task:'+d.id)));
    careerTasks.forEach(d=>(d.tasks||[]).forEach(t=>add(t,d.label,'career:'+d.id)));
    todos.forEach(t=>add(t,t.goal,'daily')); weekly.forEach(t=>add(t,t.goal,'weekly')); errands.forEach(t=>add(t,t.category||'Errands','errand'));
    return entries;
  }
  function freshness(syncedAt,status,now=Date.now()){
    const stamp=Date.parse(syncedAt); const age=now-stamp;
    if(!Number.isFinite(stamp)||age<0) return {state:'unavailable',label:'Freshness unknown',asOf:null};
    const stale=age>60*60*1000 || /failed|error|disconnected/i.test(status||'');
    return {state:stale?'stale':'current',label:stale?'Stale snapshot':'Recent snapshot',asOf:syncedAt};
  }
  // Future server adapter contract. Production never enables this gate.
  // Success requires read-after-write of the same canonical ID and value.
  async function completeCanonical({item,completed,adapter,access,requestId}){
    const ref=sourceRef(item);
    if(!access?.authorized || !access?.connectionVerified || !access?.securityApproved || !access?.liveMutationsEnabled) return {status:'blocked',reason:'Canonical task connection and authorized writes are not verified.'};
    if(ref.system!=='ticktick'||!ref.id||!ref.projectId||!adapter||!requestId) return {status:'blocked',reason:'A TickTick record, project ID, adapter and request ID are required.'};
    try{
      await adapter.setCompleted({id:ref.id,projectId:ref.projectId,completed,requestId});
      const observed=await adapter.getTask({id:ref.id,projectId:ref.projectId});
      if(String(observed?.id)!==ref.id||String(observed?.projectId)!==ref.projectId||observed?.completed!==completed) return {status:'unconfirmed',reason:'Write was not confirmed by canonical read-back.'};
      return {status:'confirmed',record:observed,observedAt:new Date().toISOString()};
    }catch{return {status:'unconfirmed',reason:'Request failed or outcome is uncertain. Reconcile before retrying.'};}
  }
  const fields=['work','consulting','miningRevenue','miningExpenses','realized','unrealized'];
  const validDate=v=>/^\d{4}-\d{2}-\d{2}$/.test(String(v))&&!Number.isNaN(Date.parse(v+'T12:00:00Z'))&&new Date(v+'T12:00:00Z').toISOString().slice(0,10)===v;
  function amount(v){if(v===null||v===undefined||String(v).trim()==='')return null;const n=Number(v);return Number.isFinite(n)&&Math.abs(n)<=Number.MAX_SAFE_INTEGER/100?n:NaN;}
  function validateFinance(raw,today){
    if(!validDate(raw.date)||raw.date>today) throw new Error('Choose a valid as-of date that is not in the future.');
    if(!['USD','EUR','GBP','CAD'].includes(raw.currency))throw new Error('Choose a supported currency. Currencies are never combined.');
    if(!String(raw.coverage||'').trim())throw new Error('Describe the income sources or accounts covered.');
    const keys=raw.kind==='worth'?['assets','liabilities']:fields;
    const result={kind:raw.kind==='worth'?'worth':'earnings',date:raw.date,currency:raw.currency,coverage:String(raw.coverage).trim(),source:'manual',periodStart:raw.date.slice(0,4)+'-01-01'};
    keys.forEach(k=>{result[k]=amount(raw[k]);if(Number.isNaN(result[k]))throw new Error('Amounts must be finite numbers.');if(!['realized','unrealized','consulting'].includes(k)&&result[k]!==null&&result[k]<0)throw new Error('Use nonnegative values for revenue, expenses, work income and balances.');});
    if(raw.kind==='worth'&&keys.some(k=>result[k]===null))throw new Error('Enter both total assets and total liabilities, including an explicit 0 when appropriate.');
    if(raw.kind!=='worth'&&keys.every(k=>result[k]===null))throw new Error('Enter at least one YTD amount. Leave unknown categories blank.');
    return result;
  }
  function earningsValue(row){
    if(!row)return null;
    const mining=row.miningRevenue!==null&&row.miningExpenses!==null?row.miningRevenue-row.miningExpenses:null;
    const values=[row.work,row.consulting,mining,row.realized].filter(x=>typeof x==='number'&&Number.isFinite(x));
    return values.length?values.reduce((a,b)=>a+b,0):null;
  }
  function financeModel(rows=[],currency='USD',year=new Date().getFullYear()){
    const selected=rows.filter(x=>x.currency===currency&&x.date.startsWith(String(year)+'-')).sort((a,b)=>a.date.localeCompare(b.date));
    const earnings=selected.filter(x=>x.kind==='earnings');const worth=selected.filter(x=>x.kind==='worth');
    const latest=earnings.at(-1)||null, wealth=worth.at(-1)||null;
    return {currency,year,latest,wealth,ytd:earningsValue(latest),netWorth:wealth?wealth.assets-wealth.liabilities:null,unrealized:latest?.unrealized??null,mining:latest&&latest.miningRevenue!==null&&latest.miningExpenses!==null?latest.miningRevenue-latest.miningExpenses:null,earningsTrend:earnings.filter(x=>earningsValue(x)!==null).map(x=>({date:x.date,value:earningsValue(x),coverage:x.coverage,signature:fields.filter(k=>x[k]!==null).join('|')})),worthTrend:worth.map(x=>({date:x.date,value:x.assets-x.liabilities,coverage:x.coverage}))};
  }
  function upsertFinance(rows,row){return [...rows.filter(x=>!(x.kind===row.kind&&x.date===row.date&&x.currency===row.currency)),row];}
  function comparableTrend(points){return points.length>=2&&points.every(x=>x.coverage===points[0].coverage&&x.signature===points[0].signature);}
  function companionRoute(tab,sub=null){
    const allowed=['now','plan','projects','finance','career','more','track','plan-tools','finance-legacy'];
    if(!allowed.includes(tab))return {tab:'now',sub:null};
    if(tab==='track'&&sub==='money')return {tab:'finance',sub:null};
    if(tab==='plan'&&['calendar','tasks','horizons','routines'].includes(sub))tab='plan-tools';
    return {tab,sub:typeof sub==='string'?sub:null};
  }
  const primaryTab=tab=>['career','more','track'].includes(tab)?'projects':tab==='plan-tools'?'plan':tab==='finance-legacy'?'finance':tab;
  function companionHandoff({priorities=[],next=null,urgent=[],waiting=[],calendarFreshness={label:'Freshness unknown'}}){
    // Explicit allowlist: finance records, legacy snapshots, credentials and chat history never enter this handoff.
    return ['Wallace — help me choose a realistic next step.',
      'This is a manual handoff from my saved WolfMaster records, not live TickTick/Notion data or synced chat context.',
      '', 'Today’s priorities:',...(priorities.length?priorities.slice(0,3).map((x,i)=>`${i+1}. ${title(x)}${closed(x)?' (completed)':''}`):['No priorities selected.']),
      '',next?`Next saved commitment: ${next.time||next.rawTime||''} — ${title(next)}`:'No upcoming timed commitment in the available snapshot; availability is unknown.',
      `Calendar: ${calendarFreshness.label}.`,
      '',`Attention: ${urgent.length} urgent flags; ${waiting.length} waiting-on records.`,
      ...urgent.slice(0,3).map(x=>`- ${title(x)} (${x.reason||'flagged in saved records'})`),
      '', 'Ask me about missing context before making assumptions. Finance entries are not included.'].join('\n');
  }
  const api={closed,sourceRef,protectList,taskProjection,freshness,completeCanonical,fields,validDate,validateFinance,financeModel,upsertFinance,comparableTrend,companionRoute,primaryTab,companionHandoff};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.WMCompanion=api;
})(typeof globalThis!=='undefined'?globalThis:this);
