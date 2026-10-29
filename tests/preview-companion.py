#!/usr/bin/env python3
"""Offline fixture harness using production components; no App auth or persistence.
Usage: python3 tests/preview-companion.py OUTPUT_DIR /tmp/wolfmaster-qa-libs
Pinned React, ReactDOM and Babel files must exist in the second directory.
Never serve this fixture as production; it bypasses auth and uses synthetic data.
"""
from pathlib import Path
import sys, re, shutil
root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]).resolve(); out.mkdir(parents=True,exist_ok=True)
libs=Path(sys.argv[2]).resolve()
s=(root/'index.html').read_text()
fixture=r'''function CompanionFixture(){
 const scenario=new URLSearchParams(location.search).get('scenario')||'populated';
 useMobileKeyboard();const [draft,setDraft]=useState(()=>newFinanceDraft());
 const [tab,setTab]=useState('now');const [entries,setEntries]=useState([]);const [currency,setCurrency]=useState('USD');const [year,setYear]=useState(new Date().getFullYear());
 const [todos,setTodos]=useState(scenario==='empty'?[]:scenario==='demo'?deepClone(TOP3INIT):[{id:'local-1',title:'Prepare the project review',goal:'Design'},{id:'canonical-1',title:'Confirm launch checklist',goal:'Launch',executiveItemId:'exec-1',canonicalSystem:'ticktick',sourceId:'tt-1',sourceProjectId:'project-1'}]);
 const [events,setEvents]=useState(scenario==='empty'?[]:[{id:'meeting',date:todayStr(),time:'23:30',title:'Review the next milestone',source:'manual',note:'30m'}]);
 const domains=scenario==='empty'?[]:[{id:'design',label:'Design',tasks:[{id:'notes',title:'Send the review notes',dueDate:todayStr()},{id:'research',title:'Compare the layout options'},{id:'access',title:'Check keyboard access',priority:'urgent'}]},{id:'launch',label:'Launch',tasks:Array.from({length:9},(_,i)=>({id:'follow-'+i,title:'Fixture follow-up '+(i+1)}))}];
 const executive=scenario==='empty'?[]:[{id:'exec-1',sourceSystem:'ticktick',canonicalSystem:'ticktick',sourceId:'tt-1',sourceProjectId:'project-1',project:'Launch',type:'task',status:'active',title:'Confirm launch checklist'},{id:'exec-2',canonicalSystem:'ticktick',sourceId:'tt-2',sourceProjectId:'project-1',type:'waiting',status:'waiting',title:'Await design approval',project:'Design',waitingOn:'Fixture reviewer',reviewDate:todayStr()}];
 const setSafeTodos=next=>setTodos(prev=>WMCompanion.protectList(prev,typeof next==='function'?next(prev):next,executive));
 return <div className="app-shell"><header className="topbar refined"><h1>WolfMaster · isolated QA</h1><span>Fixtures only · no network</span></header><main className="main v3">{tab==='finance'?<CompanionFinanceScreen draft={draft} setDraft={setDraft} entries={entries} setEntries={setEntries} currency={currency} setCurrency={setCurrency} year={year} setYear={setYear}/>:<NowScreen onNavigate={setTab} todos={todos} setTodos={setSafeTodos} calendarEvents={events} setCalendarEvents={setEvents} weekly={[]} tasks={domains} careerTasks={[]} comms={[]} errands={[]} reviewData={{executive:{items:executive}}} calendarStatus={scenario==='stale'?'Google sync failed':'Manual only'} calendarSyncedAt={scenario==='stale'?'2026-01-01T00:00:00Z':null} financeEntries={entries} financeCurrency={currency} financeYear={year}/>}</main><nav className="tabs fixed-tabs">{[['now','HOME'],['plan','PLAN'],['career','PEOPLE'],['more','BUILD'],['finance','FINANCE'],['track','REVIEW']].map(([id,label],i)=><button key={id} className={'tab '+(tab===id?'active':'')} onClick={()=>setTab(id)}><div className="tab-icon"><Icon name={['home','grid','users','trending','dollar','bars'][i]} size={20}/></div><span>{label}</span></button>)}</nav><ToastHost/></div>;
}
ReactDOM.createRoot(document.getElementById('root')).render(<CompanionFixture />);'''
mount="ReactDOM.createRoot(document.getElementById('root')).render(<App />);"
assert s.count(mount)==1
s=s.replace(mount,fixture)
s=s.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="default-src \'self\' data:; script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; style-src \'self\' \'unsafe-inline\'; connect-src \'none\'; form-action \'none\'; font-src \'self\' data:">',1)
for pattern,name in [('https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js','react'),('https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js','react-dom'),('https://unpkg.com/@babel/standalone@7.27.1/babel.min.js','babel')]:
 s=s.replace(pattern, f'libs/{name}.js')
(out/'libs').mkdir(exist_ok=True)
for name in ['react','react-dom','babel']:shutil.copy(libs/f'{name}.js',out/'libs'/f'{name}.js')
s=re.sub(r'<link[^>]+href="https://[^>]+>','',s)
(out/'index.html').write_text(s)
shutil.copytree(root/'assets'/'companion',out/'assets'/'companion',dirs_exist_ok=True)
print('Generated offline fixture:',out)
