# ruff: noqa: E501
"""Dependency-free management console for routes, thread stacks, and asyncio tasks.

Visual vocabulary reference: https://aws.amazon.com/console/
Diagnostics safety reference:
https://docs.python.org/3/library/sys.html#sys._current_frames
"""

from fastapi.responses import HTMLResponse


def console_response() -> HTMLResponse:
    return HTMLResponse(_DOCUMENT)


_DOCUMENT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mystack Console</title><style>
:root{color-scheme:dark;--ink:#e9ebed;--muted:#9ba7b4;--line:#3b4654;--panel:#161e2d;--nav:#101820;--accent:#f90;--blue:#0972d3}
*{box-sizing:border-box}body{margin:0;background:#0f1720;color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{height:52px;display:flex;align-items:center;gap:22px;padding:0 24px;background:var(--nav);border-bottom:1px solid #293444;box-shadow:0 2px 8px #0008}.brand{font-size:19px;font-weight:700}.brand b{color:var(--accent)}header span:last-child,.lead,.label{color:var(--muted)}
main{max-width:1500px;margin:auto;padding:28px}h1{font-size:24px;margin:0 0 6px}.lead{margin:0 0 24px}.toolbar,.tabs{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
select,input,button{color:var(--ink);background:#202b3a;border:1px solid #536174;border-radius:3px;padding:8px 11px}input{min-width:290px}button{cursor:pointer;background:var(--blue);border-color:#2588dc;font-weight:650}button.secondary{background:#202b3a}button.active{border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:14px;margin:22px 0}.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:17px;box-shadow:0 1px 3px #0008}.label{font-size:12px;text-transform:uppercase}.value{font-size:25px;font-weight:700;margin-top:5px}
.content{margin-top:14px;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}.content-head{display:flex;justify-content:space-between;padding:13px 16px;border-bottom:1px solid var(--line)}pre{margin:0;padding:18px;min-height:360px;max-height:65vh;overflow:auto;white-space:pre-wrap;font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}.ok{color:#7ce38b}.error{color:#ff8b8b}@media(max-width:720px){main{padding:18px}.grid{grid-template-columns:1fr}input{width:100%}}
</style></head><body>
<header><div class="brand"><b>◆</b> Mystack</div><span>Emulation Management Console</span></header><main>
<h1>Runtime diagnostics</h1><p class="lead">Inspect component routes, live Python thread stacks, and asyncio task stacks.</p>
<div class="toolbar"><label>Component <select id="component"></select></label><input id="token" type="password" placeholder="Optional management bearer token"><button id="refresh">Refresh</button><span id="status" class="ok">Ready</span></div>
<div class="grid"><div class="card"><div class="label">Component</div><div class="value" id="componentValue">—</div></div><div class="card"><div class="label">Threads</div><div class="value" id="threadCount">—</div></div><div class="card"><div class="label">Async tasks</div><div class="value" id="taskCount">—</div></div></div>
<div class="tabs"><button class="secondary active" data-view="threads">Thread stacks</button><button class="secondary" data-view="tasks">Asyncio tasks</button><button class="secondary" data-view="routes">Route registry</button></div>
<section class="content"><div class="content-head"><b id="title">Thread stacks</b><span id="timestamp"></span></div><pre id="output">Select Refresh.</pre></section></main>
<script>
const state={view:'threads',threads:null,tasks:null,routes:null},el=id=>document.getElementById(id);
const headers=()=>el('token').value?{Authorization:`Bearer ${el('token').value}`}:{},url=(c,k)=>c==='proxy'?`/_mystack/diagnostics/${k}`:`/_mystack/components/${encodeURIComponent(c)}/diagnostics/${k}`;
async function json(path){const r=await fetch(path,{headers:headers()}),b=await r.json();if(!r.ok)throw new Error(`${r.status}: ${JSON.stringify(b)}`);return b}
function render(){const d=state[state.view];el('title').textContent={threads:'Thread stacks',tasks:'Asyncio tasks',routes:'Route registry'}[state.view];el('output').textContent=d?JSON.stringify(d,null,2):'No data loaded.';el('timestamp').textContent=new Date().toLocaleString()}
async function refresh(){const c=el('component').value;el('status').textContent='Loading…';el('status').className='';try{const[t,a,r]=await Promise.all([json(url(c,'threads')),json(url(c,'tasks')),json('/_mystack/routes')]);state.threads=t;state.tasks=a;state.routes=r;el('componentValue').textContent=c;el('threadCount').textContent=t.thread_count??t.threads?.length??0;el('taskCount').textContent=a.task_count??a.tasks?.length??0;el('status').textContent='Healthy';el('status').className='ok';render()}catch(e){el('status').textContent='Request failed';el('status').className='error';el('output').textContent=String(e)}}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.view=b.dataset.view;render()});el('refresh').onclick=refresh;fetch('/_mystack/components').then(r=>r.json()).then(d=>{d.components.forEach(n=>el('component').add(new Option(n,n)));refresh()});
</script></body></html>"""
