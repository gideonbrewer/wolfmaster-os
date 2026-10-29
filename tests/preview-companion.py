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
 const [wallaceDraft,setWallaceDraft]=useState('');
 useMobileKeyboard();const {tab,navTarget,go,back}=useCompanionNavigation();
 const [draft,setDraft]=useState(()=>newFinanceDraft());const [entries,setEntries]=useState([]);const [currency,setCurrency]=useState('USD');const [year,setYear]=useState(new Date().getFullYear());
 const [todos,setTodos]=useState(scenario==='empty'?[]:[{id:'local-1',title:'Prepare the project review',goal:'Design'},{id:'canonical-1',title:'Confirm launch checklist',goal:'Launch',executiveItemId:'exec-1',canonicalSystem:'ticktick',sourceId:'tt-1',sourceProjectId:'project-1'},{id:'local-2',title:'Protect one hour for deep work',goal:'Personal'}]);
 const [events,setEvents]=useState(scenario==='empty'?[]:[{id:'meeting',date:todayStr(),time:'23:30',title:'Review the next milestone',source:'manual',note:'30m'}]);
 const domains=scenario==='empty'?[]:[{id:'design',label:'Design',tasks:[{id:'notes',title:'Send the review notes',dueDate:todayStr()},{id:'research',title:'Compare the layout options'},{id:'access',title:'Check keyboard access',priority:'urgent'}]},{id:'launch',label:'Launch',tasks:Array.from({length:9},(_,i)=>({id:'follow-'+i,title:'Fixture follow-up '+(i+1)}))}];
 const executive=scenario==='empty'?[]:[{id:'exec-1',sourceSystem:'ticktick',canonicalSystem:'ticktick',sourceId:'tt-1',sourceProjectId:'project-1',project:'Launch',type:'task',status:'active',title:'Confirm launch checklist'},{id:'exec-2',canonicalSystem:'ticktick',sourceId:'tt-2',sourceProjectId:'project-1',type:'waiting',status:'waiting',title:'Await design approval',project:'Design',waitingOn:'Fixture reviewer',reviewDate:todayStr()}];
 const setSafeTodos=next=>setTodos(prev=>WMCompanion.protectList(prev,typeof next==='function'?next(prev):next,executive));
 const shared={wallaceDraft,setWallaceDraft,onNavigate:go,navTarget,onBack:back,todos,setTodos:setSafeTodos,calendarEvents:events,setCalendarEvents:setEvents,weekly:[],tasks:domains,careerTasks:[],comms:[],errands:[],planExtras:{waiting:[]},reviewData:{executive:{items:executive}},calendarStatus:scenario==='stale'?'Google sync failed':'Manual only',calendarSyncedAt:scenario==='stale'?'2026-01-01T00:00:00Z':null};
 return <div className="app-shell companion-shell"><header className="topbar refined comp-fixture-topbar"><span className="comp-fixture-brand">W<span>WolfMaster</span></span><span className="comp-fixture-account" aria-label="Synthetic account">W</span></header><main className="main v3"><CompanionRouteBar tab={tab} onBack={back}/>{tab==='now'?<NowScreen {...shared}/>:tab==='plan'?<CompanionPlanHub {...shared}/>:tab==='projects'?<CompanionProjects {...shared}/>:tab==='finance'?<CompanionFinanceScreen onNavigate={go} draft={draft} setDraft={setDraft} entries={entries} setEntries={setEntries} currency={currency} setCurrency={setCurrency} year={year} setYear={setYear}/>:<div className="comp-destination"><h1>{tab==='career'?'People & relationships':tab==='track'?'Review & habits':tab==='more'?'Build workspace':'Planning tools'}</h1><p className="comp-body-note">Fixture route check. The production app opens the existing full workspace here. This fixture does not load live records or connections.</p><button className="comp-primary-button" onClick={back}>Return to previous view</button></div>}</main><CompanionNav tab={tab} onNavigate={go}/><ToastHost/></div>;
}
ReactDOM.createRoot(document.getElementById('root')).render(<CompanionFixture />);
'''
mount="ReactDOM.createRoot(document.getElementById('root')).render(<App />);"
assert s.count(mount)==1
s=s.replace(mount,fixture)
s=s.replace('</head>', '<style>.comp-fixture-topbar{height:64px!important;min-height:64px!important;padding:12px 20px!important;display:flex!important;align-items:center!important;justify-content:space-between!important}.comp-fixture-brand{display:flex;align-items:center;gap:10px;font-weight:800;color:var(--accent);font-size:22px}.comp-fixture-brand span{font-size:15px;font-weight:650;color:var(--text);letter-spacing:-.3px}.comp-fixture-account{display:grid;place-items:center;width:32px;height:32px;border:1px solid var(--border);border-radius:50%;color:var(--text-mid);font-size:11px}</style></head>',1)
s=s.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="default-src \'self\' data:; script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; style-src \'self\' \'unsafe-inline\'; connect-src \'none\'; form-action \'none\'; font-src \'self\' data:">',1)
for pattern,name in [('https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js','react'),('https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js','react-dom'),('https://unpkg.com/@babel/standalone@7.27.1/babel.min.js','babel')]:
 s=s.replace(pattern, f'libs/{name}.js')
(out/'libs').mkdir(exist_ok=True)
for name in ['react','react-dom','babel']:shutil.copy(libs/f'{name}.js',out/'libs'/f'{name}.js')
s=re.sub(r'<link[^>]+href="https://[^>]+>','',s)
(out/'index.html').write_text(s)
shutil.copytree(root/'assets'/'companion',out/'assets'/'companion',dirs_exist_ok=True)
print('Generated offline fixture:',out)

for width in [320,375,390,430]:
 (out/f"phone-{width}.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><title>WolfMaster phone preview</title><style>body{{margin:0}}iframe{{border:0;width:{width}px;height:844px;display:block}}</style></head><body><iframe title="WolfMaster phone preview" src="/"></iframe></body></html>')
for scenario in ["empty","stale"]:
 (out/f"phone-{scenario}.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><title>WolfMaster {scenario} preview</title><style>body{{margin:0}}iframe{{border:0;width:390px;height:844px;display:block}}</style></head><body><iframe title="WolfMaster phone preview" src="/?scenario={scenario}"></iframe></body></html>')

