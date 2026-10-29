// Exercise the production form handlers/rendered tree with React hooks simulated in memory.
// No DOM, browser, storage, credentials, network or authenticated data is used.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const Babel=require(process.env.WM_BABEL_PATH||'/tmp/wolfmaster-qa-libs/babel.js');
const WMCompanion=require('../../assets/companion/model.js');
const {createStore}=require('../../assets/companion/finance-store.js');
const html=fs.readFileSync(require('node:path').join(__dirname,'../../index.html'),'utf8');
const source=html.slice(html.indexOf('function CompanionFinanceScreen('),html.indexOf('\nfunction NowScreen('));
const empty=()=>({kind:'earnings',date:'2026-01-02',currency:'USD',coverage:'',...Object.fromEntries([...WMCompanion.fields,'assets','liabilities'].map(k=>[k,'']))});
function form(store){
 let draft=empty(),entries=[],slots=[],cursor=0,currency='USD',year=2026;
 const env={React:{createElement:(type,props,...children)=>({type,props:props||{},children})},WMCompanion,
  useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},
  useRef:()=>({current:null}),newFinanceDraft:empty,financeDraftHasChanges:d=>!!d.coverage||!!d.work,
  todayStr:()=> '2026-10-29',FINANCE_LABELS:{work:'Work income'},FinanceSnapshot:()=>{},NowPanelHead:()=>{},financeFormat:n=>String(n)};
 vm.createContext(env);vm.runInContext(Babel.transform(source,{presets:['react']}).code,env);
 const storage=()=>store?{state:store.getState(),save:x=>store.save(x),reload:()=>store.load(),reconcile:()=>store.reconcile(),acceptCurrent:()=>store.acceptCurrent()}:null;
 const render=()=>{cursor=0;return env.CompanionFinanceScreen({entries:store?store.getState().rows:entries,setEntries:f=>{entries=f(entries);},currency,setCurrency:v=>{currency=v;},year,setYear:v=>{year=v;},draft,setDraft:v=>{draft=typeof v==='function'?v(draft):v;},storage:storage()});};
 const flatten=x=>Array.isArray(x)?x.flatMap(flatten):x&&typeof x==='object'?[x,...flatten(x.children)]:[];
 const nodes=()=>flatten(render());
 const text=x=>Array.isArray(x)?x.map(text).join(' '):x&&typeof x==='object'?text(x.children):String(x??'');
 return {setDraft:v=>{draft=v;},get draft(){return draft;},get entries(){return entries;},text:()=>text(render()),nodes,
  submit:()=>{if(!nodes().find(x=>x.type==='form'))nodes().find(x=>x.type==='button'&&/^(Add snapshot|Continue draft)/.test(text(x))).props.onClick();return nodes().find(x=>x.type==='form').props.onSubmit({preventDefault(){}});},
  button:label=>nodes().find(x=>x.type==='button'&&text(x).replace(/\s+/g,' ').trim()===label),
  unmount(){slots=[];}};
}
async function run(){
 const local=form();local.setDraft({...empty(),coverage:'Synthetic',work:'125'});await local.submit();assert.equal(local.entries.length,1);assert.equal(local.draft.coverage,'');assert(local.text().includes('not saved and will clear on reload'));assert(local.button('Add snapshot ＋'));
 const client={enabled:true,dispose(){},load:async()=>[],find:async()=>null,save:async()=>{throw {code:'request_failed'};}};
 const store=createStore(client);await store.load();const f=form(store);const draft={...empty(),coverage:'Synthetic form',work:'125'};f.setDraft(draft);assert(f.text().includes('Draft not saved'));
 let resolve;client.save=()=>new Promise(r=>{resolve=r;});const pending=f.submit();assert.equal(store.getState().status,'saving');assert(f.button('Saving…').props.disabled);assert(f.button('Cancel draft').props.disabled);assert.equal(f.draft.work,'125');
 resolve({...WMCompanion.validateFinance(draft,'2026-10-29'),id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',revision:1,saved:true});await pending;assert.equal(f.draft.coverage,'');assert(f.text().includes('Saved to your finance account'));assert.equal(store.getState().rows.length,1);
 f.setDraft({...draft,work:'200'});assert(f.text().includes('Draft not saved'));client.save=async()=>{throw {code:'request_failed'};};await f.submit();assert.equal(Number(f.draft.work),200);assert(f.text().includes('Save failed'));assert.equal(store.getState().rows[0].work,125);
 // Status and draft survive a tab's component unmount/remount.
 f.unmount();assert(f.text().includes('Save failed'));assert.equal(Number(f.draft.work),200);
 client.save=async()=>{throw {code:'uncertain'};};await f.submit();assert(f.text().includes('outcome is unknown'));assert(f.button('Cancel draft').props.disabled);assert(f.button('Check saved record'));
 assert.equal(f.button('Keep my draft against this version'),undefined);await store.reconcile();assert(f.button('Keep my draft against this version'));f.button('Keep my draft against this version').props.onClick();assert.equal(Number(f.draft.work),200);assert(!f.button('Save snapshot').props.disabled);
 client.load=async()=>{throw Error('offline');};await store.load();assert(f.button('Save snapshot').props.disabled);assert(f.button('Reload saved snapshots'));assert.equal(Number(f.draft.work),200);
 assert(!f.button('Remove'),'Durable deletion is not offered by this phase');
 console.log('Finance form: honest session/save labels, locked in-flight form, confirmed-only rows, retained failed/conflicted drafts, tab remount, explicit reconciliation, reload gating and no durable-delete action passed.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
