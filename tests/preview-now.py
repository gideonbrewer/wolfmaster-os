#!/usr/bin/env python3
"""Generate a mock-only NOW preview from production components. No credentials.
Usage: python3 tests/preview-now.py /absolute/output/directory
Serve that directory with python3 -m http.server. Use ?scenario=empty or demo.
The fixture replaces only the App mount and blocks network requests via CSP.
"""
from pathlib import Path
import sys, shutil
source = Path(__file__).resolve().parents[1] / "index.html"
output = Path(sys.argv[1]).resolve()
output.mkdir(parents=True, exist_ok=True)
html = source.read_text()
harness = 'function QAHarness(){\nconst scenario=new URLSearchParams(location.search).get(\'scenario\')||\'populated\';\nconst [todos,setTodos]=useState(scenario===\'empty\'?[]:scenario===\'demo\'?deepClone(TOP3INIT):[{id:\'qa-1\',title:\'Prepare the project review\',goal:\'Work\',note:\'QA fixture only\'},{id:\'qa-2\',title:\'Plan the week\',goal:\'Personal\'}]);\nconst [events,setEvents]=useState(scenario===\'populated\'?[{id:\'qa-event\',date:todayStr(),time:\'23:30\',title:\'QA review block\',source:\'manual\',note:\'30m\'}]:[]);\nconst [habits,setHabits]=useState([]);const [nav,setNav]=useState(\'NOW\');\nreturn <div className="app-shell"><header className="topbar refined"><h1>WolfMaster · isolated QA</h1><span>Mock data only · {nav}</span></header><main className="main v3"><NowScreen todos={todos} setTodos={setTodos} calendarEvents={events} setCalendarEvents={setEvents} habits={habits} setHabits={setHabits} weekly={[]} careerLeads={[]} tasks={scenario===\'empty\'?[]:[{id:\'qa\',label:\'QA\',tasks:[{id:\'due\',title:\'Send the review notes\',dueDate:todayStr()},{id:\'urgent\',title:\'Resolve the launch blocker\',priority:\'urgent\'},{id:\'later\',title:\'Later item\',priority:\'soon\'},{id:\'urgent2\',title:\'Check the final checklist\',priority:\'P1\'},{id:\'urgent3\',title:\'Confirm the handoff\',priority:\'P1\'}]}]} careerTasks={[]} comms={[]} errands={[]} reflect={[]} build={[]} calendarStatus="Manual only" onNavigate={(tab,sub)=>setNav(tab+\' / \'+sub)}/><ToastHost/></main></div>;\n}\nReactDOM.createRoot(document.getElementById(\'root\')).render(<QAHarness />);'
mount = "ReactDOM.createRoot(document.getElementById('root')).render(<App />);"
assert html.count(mount) == 1
html = html.replace(mount, harness).replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="connect-src \'none\'; form-action \'none\'">')
shutil.copytree(source.parent / 'assets' / 'companion', output / 'assets' / 'companion', dirs_exist_ok=True)
(output / 'index.html').write_text(html)
(output / 'mobile.html').write_text('<!doctype html><meta charset="UTF-8"><meta name="viewport" content="width=device-width"><title>WolfMaster 390px QA</title><style>body{margin:0;background:#151515;color:white;font:14px system-ui}iframe{width:390px;height:844px;border:0;display:block;margin:0 auto}p{text-align:center}</style><p>390px viewport · isolated mock data</p><iframe title="WolfMaster mobile QA" src="index.html"></iframe>')
print(f'Generated isolated NOW preview in {output}')
