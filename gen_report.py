import json, csv, os
from collections import Counter
from datetime import date

folder = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(folder, 'Jira_latest.csv')

if not os.path.exists(csv_path):
    print("ERROR: Jira_latest.csv not found in this folder!")
    input("Press Enter to exit...")
    exit(1)

rows = []
statuses = Counter()
reporters = Counter()
issue_types = Counter()
priorities = Counter()

with open(csv_path, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append({
            'key':      row.get('Issue key','').strip(),
            'summary':  row.get('Summary','').strip(),
            'status':   row.get('Status','').strip(),
            'type':     row.get('Issue Type','').strip(),
            'priority': row.get('Priority','').strip(),
            'reporter': row.get('Reporter','').strip(),
            'assignee': row.get('Assignee','').strip(),
            'created':  row.get('Created','').strip(),
        })
        statuses[row.get('Status','').strip()] += 1
        reporters[row.get('Reporter','').strip()] += 1
        issue_types[row.get('Issue Type','').strip()] += 1
        priorities[row.get('Priority','').strip()] += 1

total = len(rows)
open_statuses = ['To Do', 'In Progress', 'Blocked']
closed_statuses = ['Done', "Won't Do", 'Not a Bug', 'Cannot Reproduce', 'Duplicate']
open_count = sum(statuses[s] for s in open_statuses)
closed_count = sum(statuses[s] for s in closed_statuses)
blocked_count = statuses.get('Blocked', 0)
bug_count = issue_types.get('Bug', 0)
critical_count = priorities.get('Critical', 0)
reporter_count = len([r for r in reporters if r])

try:
    today = date.today().strftime('%#d %B %Y')  # Windows
except ValueError:
    today = date.today().strftime('%d %B %Y')

data_json = json.dumps(rows)

# Build reporter bars
reporter_list = reporters.most_common()
rep_labels = [r[0] for r in reporter_list]
rep_data   = [r[1] for r in reporter_list]
rep_colors = ['#0052cc','#0ea5e9','#6366f1','#f97316','#a855f7','#22c55e','#ec4899','#14b8a6','#f59e0b','#ef4444']
rep_colors_js = json.dumps((rep_colors * (len(rep_labels)//len(rep_colors)+1))[:len(rep_labels)])

# Build status chart
status_order = ['To Do','Done',"Won't Do",'In Progress','Blocked','Not a Bug','Cannot Reproduce','Duplicate']
status_labels = [s for s in status_order if statuses.get(s,0)>0] + [s for s in statuses if s not in status_order and statuses[s]>0]
status_data   = [statuses[s] for s in status_labels]
status_bg     = ['#3b82f6','#22c55e','#facc15','#f97316','#ef4444','#94a3b8','#cbd5e1','#e2e8f0']
status_bg_js  = json.dumps((status_bg * (len(status_labels)//len(status_bg)+1))[:len(status_labels)])

# Build type chart
type_order = ['Bug','Story','Task','Epic','Product Feature Request','Spike']
type_labels = [t for t in type_order if issue_types.get(t,0)>0] + [t for t in issue_types if t not in type_order and issue_types[t]>0]
type_data   = [issue_types[t] for t in type_labels]
type_bg     = ['#6366f1','#0ea5e9','#f97316','#a855f7','#ec4899','#14b8a6']
type_bg_js  = json.dumps((type_bg * (len(type_labels)//len(type_bg)+1))[:len(type_labels)])

# Build priority chart
pri_order = ['Medium','High','Critical','Low']
pri_labels = [p for p in pri_order if priorities.get(p,0)>0] + [p for p in priorities if p not in pri_order and priorities[p]>0]
pri_data   = [priorities[p] for p in pri_labels]
pri_bg     = ['#facc15','#f97316','#ef4444','#86efac']
pri_bg_js  = json.dumps((pri_bg * (len(pri_labels)//len(pri_bg)+1))[:len(pri_labels)])

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Jira Defect Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;color:#1e293b;padding:24px;}}
    header{{background:linear-gradient(135deg,#0052cc,#0ea5e9);color:white;border-radius:12px;padding:28px 32px;margin-bottom:28px;display:flex;justify-content:space-between;align-items:center;}}
    header h1{{font-size:1.8rem;font-weight:700;}}
    header p{{opacity:.85;margin-top:4px;font-size:.95rem;}}
    .badge{{background:rgba(255,255,255,.2);padding:8px 18px;border-radius:20px;font-size:1.4rem;font-weight:700;}}
    .kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:16px;margin-bottom:28px;}}
    .kpi{{background:white;border-radius:10px;padding:20px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.08);border-top:4px solid var(--accent);cursor:pointer;transition:transform .15s,box-shadow .15s;}}
    .kpi:hover{{transform:translateY(-3px);box-shadow:0 6px 18px rgba(0,0,0,.14);}}
    .kpi .num{{font-size:2.2rem;font-weight:800;color:var(--accent);}}
    .kpi .lbl{{font-size:.82rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.5px;}}
    .kpi .hint{{font-size:.68rem;color:#94a3b8;margin-top:5px;}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:22px;margin-bottom:28px;}}
    .card{{background:white;border-radius:12px;padding:22px 24px;box-shadow:0 1px 4px rgba(0,0,0,.08);}}
    .card h2{{font-size:1rem;font-weight:600;color:#334155;margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid #e2e8f0;}}
    .chart-wrap{{position:relative;height:280px;}}
    .card.tall .chart-wrap{{height:380px;}}
    .clickable-note{{font-size:.72rem;color:#94a3b8;text-align:center;margin-bottom:20px;}}
    #overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:flex-start;justify-content:center;padding:40px 16px;overflow-y:auto;}}
    #overlay.open{{display:flex;}}
    #modal{{background:white;border-radius:14px;width:100%;max-width:980px;box-shadow:0 20px 60px rgba(0,0,0,.25);overflow:hidden;margin:auto;}}
    #mhead{{background:linear-gradient(135deg,#0052cc,#0ea5e9);color:white;padding:18px 24px;display:flex;justify-content:space-between;align-items:center;}}
    #mtitle{{font-size:1.1rem;font-weight:700;}}
    #mcount{{font-size:.85rem;opacity:.85;margin-top:2px;}}
    #mclose{{background:rgba(255,255,255,.2);border:none;color:white;font-size:1.3rem;width:34px;height:34px;border-radius:50%;cursor:pointer;line-height:1;}}
    #mclose:hover{{background:rgba(255,255,255,.35);}}
    #mbody{{padding:20px 24px;max-height:65vh;overflow-y:auto;}}
    #msearch{{width:100%;padding:9px 14px;border:1px solid #e2e8f0;border-radius:8px;font-size:.9rem;margin-bottom:16px;outline:none;}}
    #msearch:focus{{border-color:#0ea5e9;box-shadow:0 0 0 3px rgba(14,165,233,.15);}}
    .it{{width:100%;border-collapse:collapse;font-size:.84rem;}}
    .it th{{background:#f8fafc;padding:9px 10px;text-align:left;font-size:.74rem;text-transform:uppercase;letter-spacing:.4px;color:#64748b;border-bottom:2px solid #e2e8f0;white-space:nowrap;}}
    .it td{{padding:9px 10px;border-bottom:1px solid #f1f5f9;vertical-align:top;}}
    .it tr:last-child td{{border-bottom:none;}}
    .it tr:hover td{{background:#f8fafc;}}
    .ikey{{font-weight:700;color:#0052cc;white-space:nowrap;}}
    .isum{{max-width:320px;}}
    .pill{{display:inline-block;padding:2px 9px;border-radius:10px;font-size:.72rem;font-weight:600;white-space:nowrap;}}
    .s-todo{{background:#dbeafe;color:#1d4ed8;}}
    .s-done{{background:#dcfce7;color:#15803d;}}
    .s-wont{{background:#fef9c3;color:#92400e;}}
    .s-prog{{background:#fde68a;color:#b45309;}}
    .s-block{{background:#fee2e2;color:#b91c1c;}}
    .s-other{{background:#f1f5f9;color:#475569;}}
    .p-critical{{background:#fee2e2;color:#b91c1c;}}
    .p-high{{background:#ffedd5;color:#c2410c;}}
    .p-medium{{background:#fef9c3;color:#92400e;}}
    .p-low{{background:#dcfce7;color:#15803d;}}
    footer{{text-align:center;color:#94a3b8;font-size:.8rem;margin-top:16px;}}
  </style>
</head>
<body>

<header>
  <div>
    <h1>Jira Defect Dashboard</h1>
    <p>Generated on {today} &nbsp;|&nbsp; Source: Jira_latest.csv</p>
  </div>
  <div class="badge">{total} Issues</div>
</header>

<p class="clickable-note">&#x1F4CA; Click any card or chart segment to drill into the issues</p>

<div class="kpi-row">
  <div class="kpi" style="--accent:#ef4444" onclick="show('Open / Active','status',['To Do','In Progress','Blocked'])">
    <div class="num">{open_count}</div><div class="lbl">Open / Active</div><div class="hint">click to view</div>
  </div>
  <div class="kpi" style="--accent:#22c55e" onclick="show('Resolved / Closed','status',['Done','Won\\'t Do','Not a Bug','Cannot Reproduce','Duplicate'])">
    <div class="num">{closed_count}</div><div class="lbl">Resolved / Closed</div><div class="hint">click to view</div>
  </div>
  <div class="kpi" style="--accent:#f97316" onclick="show('Blocked Issues','status',['Blocked'])">
    <div class="num">{blocked_count}</div><div class="lbl">Blocked</div><div class="hint">click to view</div>
  </div>
  <div class="kpi" style="--accent:#6366f1" onclick="show('Bugs','type',['Bug'])">
    <div class="num">{bug_count}</div><div class="lbl">Bugs</div><div class="hint">click to view</div>
  </div>
  <div class="kpi" style="--accent:#0ea5e9" onclick="show('Critical Priority','priority',['Critical'])">
    <div class="num">{critical_count}</div><div class="lbl">Critical Priority</div><div class="hint">click to view</div>
  </div>
  <div class="kpi" style="--accent:#8b5cf6" onclick="show('All Issues','all',[])">
    <div class="num">{reporter_count}</div><div class="lbl">Reporters</div><div class="hint">view all issues</div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Issue Status Breakdown <small style="color:#94a3b8;font-size:.75rem">(click segment)</small></h2>
    <div class="chart-wrap"><canvas id="cStatus"></canvas></div>
  </div>
  <div class="card">
    <h2>Open vs Resolved <small style="color:#94a3b8;font-size:.75rem">(click segment)</small></h2>
    <div class="chart-wrap"><canvas id="cOpen"></canvas></div>
  </div>
  <div class="card">
    <h2>Issue Type Distribution <small style="color:#94a3b8;font-size:.75rem">(click bar)</small></h2>
    <div class="chart-wrap"><canvas id="cType"></canvas></div>
  </div>
  <div class="card">
    <h2>Priority Distribution <small style="color:#94a3b8;font-size:.75rem">(click bar)</small></h2>
    <div class="chart-wrap"><canvas id="cPri"></canvas></div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr">
  <div class="card tall">
    <h2>Issues by Reporter <small style="color:#94a3b8;font-size:.75rem">(click bar)</small></h2>
    <div class="chart-wrap"><canvas id="cRep"></canvas></div>
  </div>
</div>

<div id="overlay" onclick="if(event.target===this)closeModal()">
  <div id="modal">
    <div id="mhead">
      <div><div id="mtitle"></div><div id="mcount"></div></div>
      <button id="mclose" onclick="closeModal()">&#x2715;</button>
    </div>
    <div id="mbody">
      <input id="msearch" type="text" placeholder="Search within results..." oninput="render()"/>
      <div id="mtable"></div>
    </div>
  </div>
</div>

<footer>Jira_latest.csv &mdash; {total} issues analysed &mdash; Report auto-generated by Claude Code</footer>

<script>
const DATA = {data_json};
let cur = [];
const sCls = s => ({{'To Do':'s-todo','Done':'s-done',"Won't Do":'s-wont','In Progress':'s-prog','Blocked':'s-block'}}[s]||'s-other');
const pCls = p => ({{'Critical':'p-critical','High':'p-high','Medium':'p-medium','Low':'p-low'}}[p]||'s-other');

function show(title, field, vals){{
  cur = field==='all' ? DATA : field==='reporter' ? DATA.filter(r=>r.reporter===vals[0]) : DATA.filter(r=>vals.includes(r[field]));
  document.getElementById('mtitle').textContent = title;
  document.getElementById('msearch').value = '';
  render();
  document.getElementById('overlay').classList.add('open');
}}
function render(){{
  const q = document.getElementById('msearch').value.toLowerCase();
  const rows = q ? cur.filter(r=>[r.key,r.summary,r.reporter,r.assignee,r.priority,r.status,r.type].join(' ').toLowerCase().includes(q)) : cur;
  document.getElementById('mcount').textContent = rows.length + ' issue' + (rows.length!==1?'s':'');
  if(!rows.length){{ document.getElementById('mtable').innerHTML='<p style="color:#94a3b8;text-align:center;padding:32px">No matching issues.</p>'; return; }}
  let h='<table class="it"><thead><tr><th>Key</th><th>Summary</th><th>Status</th><th>Priority</th><th>Type</th><th>Reporter</th><th>Assignee</th><th>Created</th></tr></thead><tbody>';
  rows.forEach(r=>{{ h+=`<tr><td class="ikey">${{r.key}}</td><td class="isum">${{r.summary}}</td><td><span class="pill ${{sCls(r.status)}}">${{r.status}}</span></td><td><span class="pill ${{pCls(r.priority)}}">${{r.priority}}</span></td><td>${{r.type}}</td><td>${{r.reporter}}</td><td>${{r.assignee||'&mdash;'}}</td><td style="white-space:nowrap">${{r.created}}</td></tr>`; }});
  h+='</tbody></table>';
  document.getElementById('mtable').innerHTML = h;
}}
function closeModal(){{ document.getElementById('overlay').classList.remove('open'); }}
document.addEventListener('keydown',e=>{{ if(e.key==='Escape') closeModal(); }});

Chart.defaults.font.family="'Segoe UI',Arial,sans-serif";
Chart.defaults.plugins.legend.position='right';
function handler(field, map){{
  return {{
    onClick(_,items){{ if(!items.length) return; const lbl=this.data.labels[items[0].index]; const vals=map?map[lbl]:[lbl]; show(lbl,field,vals); }},
    onHover(_,__,chart){{ chart.canvas.style.cursor='pointer'; }}
  }};
}}

new Chart('cStatus',{{type:'doughnut',data:{{labels:{json.dumps(status_labels)},datasets:[{{data:{json.dumps(status_data)},backgroundColor:{status_bg_js},borderWidth:2,borderColor:'#fff'}}]}},options:{{cutout:'60%',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{boxWidth:12,font:{{size:11}}}}}}}}, ...handler('status')}}}});
new Chart('cOpen',{{type:'doughnut',data:{{labels:['Open / Active','Resolved / Closed'],datasets:[{{data:[{open_count},{closed_count}],backgroundColor:['#ef4444','#22c55e'],borderWidth:2,borderColor:'#fff'}}]}},options:{{cutout:'65%',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{boxWidth:14,font:{{size:12}}}}}}}}, ...handler('status',{{'Open / Active':['To Do','In Progress','Blocked'],'Resolved / Closed':['Done',"Won't Do",'Not a Bug','Cannot Reproduce','Duplicate']}})}}}});
new Chart('cType',{{type:'bar',data:{{labels:{json.dumps(type_labels)},datasets:[{{label:'Count',data:{json.dumps(type_data)},backgroundColor:{type_bg_js},borderRadius:6}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true}}}}, ...handler('type')}}}});
new Chart('cPri',{{type:'bar',data:{{labels:{json.dumps(pri_labels)},datasets:[{{label:'Count',data:{json.dumps(pri_data)},backgroundColor:{pri_bg_js},borderRadius:6}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true}}}}, ...handler('priority')}}}});
new Chart('cRep',{{type:'bar',data:{{labels:{json.dumps(rep_labels)},datasets:[{{label:'Issues',data:{json.dumps(rep_data)},backgroundColor:{rep_colors_js},borderRadius:6}}]}},options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true}},y:{{ticks:{{font:{{size:13}}}}}}}},onClick(_,items){{if(!items.length)return;const n=this.data.labels[items[0].index];show('Reporter: '+n,'reporter',[n]);}},onHover(_,__,chart){{chart.canvas.style.cursor='pointer';}}}}}});
</script>
</body>
</html>"""

out_path = os.path.join(folder, 'jira_latest_report.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Report generated: {total} issues processed.")
