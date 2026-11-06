import json, csv, os, sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

# NOTE: never call input() here -- this runs unattended under Task Scheduler,
# where a prompt blocks until the scheduler kills the task. Exit non-zero
# instead so refresh_report_auto.bat can log the failure. See fetch_jira.py.

folder = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(folder, 'Jira_latest.csv')

# Load JIRA_URL from .env so ticket keys can be rendered as hyperlinks
env_path = os.path.join(folder, '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
JIRA_BASE = os.environ.get('JIRA_URL', 'https://datavant.atlassian.net').rstrip('/')

if not os.path.exists(csv_path):
    print("ERROR: Jira_latest.csv not found in this folder!")
    sys.exit(1)

rows = []
statuses = Counter()
reporters = Counter()
issue_types = Counter()
priorities = Counter()
month_created = defaultdict(int)
month_resolved = defaultdict(int)

def parse_jira_date(s):
    for fmt in ('%d/%b/%y %I:%M %p', '%d/%b/%y %I:%M%p', '%Y-%m-%dT%H:%M:%S.%f%z'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None

def aware(dt):
    # Legacy CSV exports have no timezone; treat them as UTC so dates can be compared.
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

# Tickets carrying this Jira label are product enhancements: reported in their own section and
# kept out of every defect chart and count.
ENHANCEMENT_LABEL = 'enhancement'
enh_rows = []
spans = []   # (created, resolved, status) per defect, used to rebuild the backlog trend

with open(csv_path, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        created_raw  = row.get('Created','').strip()
        resolved_raw = row.get('Resolved','').strip()
        dt_created  = parse_jira_date(created_raw)
        dt_resolved = parse_jira_date(resolved_raw) if resolved_raw else None
        created_month  = dt_created.strftime('%Y-%m')  if dt_created  else ''
        resolved_month = dt_resolved.strftime('%Y-%m') if dt_resolved else ''
        labels = [l.strip() for l in row.get('Labels','').split(';') if l.strip()]
        rec = {
            'key':            row.get('Issue key','').strip(),
            'summary':        row.get('Summary','').strip(),
            'status':         row.get('Status','').strip(),
            'type':           row.get('Issue Type','').strip(),
            'priority':       row.get('Priority','').strip(),
            'reporter':       row.get('Reporter','').strip(),
            'assignee':       row.get('Assignee','').strip(),
            'created':        created_raw,
            'resolved':       resolved_raw,
            'created_month':  created_month,
            'resolved_month': resolved_month,
            'created_ts':     dt_created.isoformat() if dt_created else '',
            'resolved_ts':    dt_resolved.isoformat() if dt_resolved else '',
            # Issue Theme dropdown (empty until JIRA_THEME_FIELD is set for fetch_jira.py)
            'theme':          row.get('Theme','').strip(),
        }
        if ENHANCEMENT_LABEL in (l.lower() for l in labels):
            enh_rows.append(rec)
            continue
        rows.append(rec)
        spans.append((aware(dt_created), aware(dt_resolved), rec['status']))
        statuses[rec['status']] += 1
        reporters[rec['reporter']] += 1
        issue_types[rec['type']] += 1
        priorities[rec['priority']] += 1
        if created_month:
            month_created[created_month] += 1
        if resolved_month:
            month_resolved[resolved_month] += 1

total = len(rows)
closed_statuses = ['Done', "Won't Do", 'Not a Bug', 'Cannot Reproduce', 'Duplicate']
# Open = anything not closed, so in-flight statuses (Code Review, QA, UAT, In Review...) are never dropped.
open_statuses = [st for st in statuses if st and st not in closed_statuses]
unmapped = [st for st in open_statuses if st not in ('To Do', 'In Progress', 'In Review', 'Code Review', 'QA', 'UAT', 'Blocked')]
if unmapped:
    print(f"NOTE: new open statuses will be grouped under In Progress: {unmapped}")
open_count = sum(statuses[s] for s in open_statuses)
closed_count = sum(statuses[s] for s in closed_statuses)
blocked_count = statuses.get('Blocked', 0)
bug_count = issue_types.get('Bug', 0)
critical_count = priorities.get('Critical', 0)
reporter_count = len([r for r in reporters if r])

top10 = sorted([r for r in rows if r.get('created_ts')], key=lambda r: r['created_ts'], reverse=True)[:10]
top10_json = json.dumps(top10)

top10_resolved = sorted([r for r in rows if r.get('resolved_ts')], key=lambda r: r['resolved_ts'], reverse=True)[:10]
top10_resolved_json = json.dumps(top10_resolved)

# Aging buckets for open issues
today_dt = date.today()
age_buckets = {'<7d': 0, '7–30d': 0, '30–90d': 0, '>90d': 0}
for r in rows:
    if r['status'] in open_statuses and r.get('created_ts'):
        created_d = datetime.fromisoformat(r['created_ts']).date()
        age = (today_dt - created_d).days
        if age < 7:
            age_buckets['<7d'] += 1
        elif age < 30:
            age_buckets['7–30d'] += 1
        elif age < 90:
            age_buckets['30–90d'] += 1
        else:
            age_buckets['>90d'] += 1
age_labels = ['<7d', '7–30d', '30–90d', '>90d']
age_data   = [age_buckets[k] for k in age_labels]
age_colors_js = json.dumps(['#22c55e', '#f59e0b', '#f97316', '#ef4444'])

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

# Build issues by created month — split by current status (open vs closed)
all_months_set    = sorted(month_created.keys())
month_labels_disp = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in all_months_set]
created_open_monthly   = [sum(1 for r in rows if r['created_month']==m and r['status'] in open_statuses)   for m in all_months_set]
created_closed_monthly = [sum(1 for r in rows if r['created_month']==m and r['status'] in closed_statuses) for m in all_months_set]
all_months_js = json.dumps(all_months_set)

# ── Backlog trend: weekly open count rebuilt from created / resolved dates ──────
# A ticket is open at time T if created <= T and (still open now, or resolved after T).
# Weeks start Monday 00:00 UTC. The last week is the current one, cut off at "now", so the final
# open count equals the Open / Active KPI. Created / resolved are the events inside each week.
TREND_WEEKS = 52
now_utc = datetime.now(timezone.utc)
week0 = (now_utc - timedelta(days=now_utc.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
starts = [week0 - timedelta(days=7 * k) for k in range(TREND_WEEKS, -1, -1)]
ends = [min(st + timedelta(days=7), now_utc) for st in starts]
tickets = []
undated = 0
for c, rsv, st in spans:
    if c is None:
        undated += 1
    elif st in open_statuses:
        tickets.append((c, None))
    elif rsv:
        tickets.append((c, rsv))
    else:
        undated += 1   # closed but no resolution date: cannot be placed in time
trend_open = [sum(1 for c, r in tickets if c <= e and (r is None or r > e)) for e in ends]
trend_created = [sum(1 for c, r in tickets if st < c <= e) for st, e in zip(starts, ends)]
trend_resolved = [sum(1 for c, r in tickets if r and st < r <= e) for st, e in zip(starts, ends)]
trend_labels = [f"{st:%b} {st.day} '{st:%y}" for st in starts]
trend_labels[-1] += ' (so far)'
if trend_open[-1] != open_count:
    print(f"WARNING: trend ends at {trend_open[-1]} open but the KPI shows {open_count} (undated tickets: {undated})")

# Is the backlog moving because more tickets close, or fewer open? Compare the last 12 full weeks
# with the 12 before that (the current partial week is left out).
def avg(xs): return sum(xs) / len(xs)
recent, prior = slice(-13, -1), slice(-25, -13)
flow = {
    'created_now': avg(trend_created[recent]), 'created_before': avg(trend_created[prior]),
    'resolved_now': avg(trend_resolved[recent]), 'resolved_before': avg(trend_resolved[prior]),
}
flow = {k: round(v, 1) for k, v in flow.items()}
flow['open_start'], flow['open_end'] = trend_open[-13], trend_open[-1]
fewer_opened = flow['created_before'] - flow['created_now']      # positive = fewer tickets opened than before
more_closed = flow['resolved_now'] - flow['resolved_before']     # positive = more tickets closed than before
if flow['open_end'] < flow['open_start']:
    verdict = ('Backlog is falling mainly because more tickets are being closed' if more_closed > fewer_opened
               else 'Backlog is falling mainly because fewer tickets are being opened')
elif flow['open_end'] > flow['open_start']:
    verdict = ('Backlog is growing mainly because fewer tickets are being closed' if more_closed < fewer_opened
               else 'Backlog is growing mainly because more tickets are being opened')
else:
    verdict = 'Backlog is flat'
trend = {'labels': trend_labels, 'open': trend_open, 'created': trend_created, 'resolved': trend_resolved,
         'flow': flow, 'verdict': verdict + ' (last 12 weeks vs the 12 before).', 'undated': undated}

# Enhancements: open first, newest first
enh_rows.sort(key=lambda r: r['created_ts'], reverse=True)
enh_rows.sort(key=lambda r: r['status'] in closed_statuses)
enh_open = sum(1 for r in enh_rows if r['status'] not in closed_statuses)

NEW_CSS = """
    .card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid #e2e8f0;}
    .card-head h2{margin:0;padding:0;border:0;}
    .tog{display:inline-flex;border:1px solid #e2e8f0;border-radius:20px;overflow:hidden;flex-shrink:0;}
    .tog button{font:inherit;font-size:.72rem;font-weight:600;padding:4px 12px;border:0;background:white;color:#64748b;cursor:pointer;}
    .tog button[aria-pressed="true"]{background:#0052cc;color:white;}
    .tog button:focus-visible{outline:2px solid #0ea5e9;outline-offset:-2px;}
    .sub{font-size:.78rem;color:#64748b;margin:-8px 0 14px;}
    .flow{margin-top:14px;padding:12px 16px;border-radius:10px;background:#f8fafc;font-size:.85rem;color:#334155;}
    .flow b{color:#0052cc;}
    .enh-grid{display:grid;grid-template-columns:minmax(180px,1fr) 3fr;gap:24px;align-items:start;}
    .enh-big{font-size:2.6rem;font-weight:800;color:#8b5cf6;line-height:1;}
    .enh-big small{font-size:.85rem;font-weight:400;color:#64748b;margin-left:6px;}
    .enh-note{font-size:.8rem;color:#64748b;margin-top:10px;}
    @media (max-width:820px){.enh-grid{grid-template-columns:1fr;}}
"""
CHARTS_JS = r"""
// ══ Defect breakdown charts: status / type / priority ══════════════════════════
// To add a chart by Issue Theme later: build a rows list (OPEN_ROWS or DATA), call
// countBy(rows, r => r.theme || 'None'), and draw it like drawType() below.
// r.theme is already filled from the Jira "Theme" column once fetch_jira.py has JIRA_THEME_FIELD.
const STATUS_GROUPS = ['To Do', 'In Progress (incl. In Review)', 'Blocked'];
const STATUS_COLORS = {'To Do':'#3b82f6', 'In Progress (incl. In Review)':'#f97316', 'Blocked':'#ef4444'};
const RESOLVED_COLOR = '#86efac';   // light green for resolved tickets
const statusGroup = st => st==='To Do' ? STATUS_GROUPS[0] : st==='Blocked' ? STATUS_GROUPS[2] : STATUS_GROUPS[1];
const isOpen   = r => OPEN_ST.includes(r.status);
const isClosed = r => CLOSED_ST.includes(r.status);
const OPEN_ROWS = DATA.filter(isOpen);
const countBy = (rows, fn) => rows.reduce((m, r) => { const k = fn(r); m[k] = (m[k] || 0) + 1; return m; }, {});
const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const live = {};
const mode = {status:'open', pri:'open', type:'open'};

function showRows(title, rows){
  cur = rows;
  document.getElementById('mtitle').textContent = title;
  document.getElementById('msearch').value = '';
  sortKey = null;
  render();
  document.getElementById('overlay').classList.add('open');
}
const pointer = (_, __, chart) => { chart.canvas.style.cursor = 'pointer'; };

function drawStatus(){
  const all = mode.status === 'all';
  const counts = countBy(OPEN_ROWS, r => statusGroup(r.status));
  const labels = STATUS_GROUPS.slice(), colors = labels.map(g => STATUS_COLORS[g]);
  const data = labels.map(g => counts[g] || 0);
  if(all){ labels.push('Resolved'); colors.push(RESOLVED_COLOR); data.push(DATA.filter(isClosed).length); }
  document.getElementById('tStatus').textContent = all ? 'All defects by status' : 'Open defects by status';
  if(live.status) live.status.destroy();
  live.status = new Chart('cStatus', {type:'doughnut',
    data:{labels, datasets:[{data, backgroundColor:colors, borderWidth:2, borderColor:'#fff'}]},
    options:{cutout:'60%', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{labels:{boxWidth:12, font:{size:11}}}},
      onClick(_, items){ if(!items.length) return; const g = labels[items[0].index];
        showRows(g, g==='Resolved' ? DATA.filter(isClosed) : OPEN_ROWS.filter(r => statusGroup(r.status)===g)); },
      onHover:pointer}});
}

const TYPE_ORDER  = ['Bug','Story','Task','Epic','Product Feature Request','Spike'];
const TYPE_COLORS = ['#6366f1','#0ea5e9','#f97316','#a855f7','#ec4899','#14b8a6'];
function drawType(){
  const all = mode.type === 'all';
  const pool = all ? DATA : OPEN_ROWS;
  const counts = countBy(pool, r => r.type);
  document.getElementById('tType').textContent = all ? 'All defects by issue type' : 'Open defects by issue type';
  if(live.type) live.type.destroy();
  const labels = TYPE_ORDER.filter(t => counts[t]).concat(Object.keys(counts).filter(t => !TYPE_ORDER.includes(t)));
  const colors = labels.map((_, i) => TYPE_COLORS[i % TYPE_COLORS.length]);
  live.type = new Chart('cType', {type:'bar',
    data:{labels, datasets:[{label:all ? 'Defects' : 'Open defects', data:labels.map(t => counts[t]), backgroundColor:colors, borderRadius:6}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
      scales:{y:{beginAtZero:true, ticks:{precision:0}}},
      onClick(_, items){ if(!items.length) return; const t = labels[items[0].index];
        showRows((all ? 'All ' : 'Open ') + t, pool.filter(r => r.type===t)); },
      onHover:pointer}});
}

const PRIORITIES = ['Critical','High','Medium','Low'];
function drawPriority(){
  const all = mode.pri === 'all';
  const pool = all ? DATA : OPEN_ROWS;
  const extra = Object.keys(countBy(pool, r => r.priority)).filter(p => p && !PRIORITIES.includes(p));
  const labels = PRIORITIES.concat(extra);
  const byPri = (rows) => { const c = countBy(rows, r => r.priority); return labels.map(p => c[p] || 0); };
  const datasets = STATUS_GROUPS.map(g => ({label:g, data:byPri(OPEN_ROWS.filter(r => statusGroup(r.status)===g)),
    backgroundColor:STATUS_COLORS[g], borderWidth:0}));
  if(all) datasets.push({label:'Resolved', data:byPri(DATA.filter(isClosed)), backgroundColor:RESOLVED_COLOR, borderWidth:0});
  document.getElementById('tPri').textContent = all ? 'All defects by priority and status' : 'Open defects by priority and status';
  if(live.pri) live.pri.destroy();
  live.pri = new Chart('cPri', {type:'bar', data:{labels, datasets},
    options:{responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'bottom', labels:{boxWidth:12, font:{size:11}}}},
      scales:{x:{stacked:true}, y:{stacked:true, beginAtZero:true, ticks:{precision:0}}},
      onClick(_, items){ if(!items.length) return;
        const p = labels[items[0].index], g = datasets[items[0].datasetIndex].label;
        showRows(p + ' · ' + g, (g==='Resolved' ? DATA.filter(isClosed) : OPEN_ROWS.filter(r => statusGroup(r.status)===g)).filter(r => r.priority===p)); },
      onHover:pointer}});
}

const redraw = {status:drawStatus, pri:drawPriority, type:drawType};
document.querySelectorAll('.tog button').forEach(b => b.addEventListener('click', () => {
  const k = b.dataset.chart, m = b.dataset.mode;
  mode[k] = m;
  b.parentElement.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  redraw[k]();
}));
drawStatus(); drawType(); drawPriority();

// ══ Backlog trend: open count per week, plus a created-vs-resolved summary line ═══
new Chart('cTrend', {type:'line',
  data:{labels:TREND.labels, datasets:[{label:'Open defects', data:TREND.open, borderColor:'#0052cc',
    backgroundColor:'rgba(0,82,204,.10)', fill:true, tension:.25, pointRadius:2, pointHoverRadius:5}]},
  options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
    scales:{x:{ticks:{maxTicksLimit:13, maxRotation:0}}, y:{beginAtZero:true, ticks:{precision:0}}}}});
(function(){
  const f = TREND.flow, d = (a, b) => { const x = Math.round((a - b) * 10) / 10; return (x > 0 ? '+' : '') + x; };
  document.getElementById('flowText').innerHTML =
    '<b>' + esc(TREND.verdict) + '</b><br>' +
    'Open defects: ' + f.open_start + ' &rarr; ' + f.open_end + ' over the last 12 weeks. ' +
    'Created per week: ' + f.created_now + ' (was ' + f.created_before + ', ' + d(f.created_now, f.created_before) + '). ' +
    'Resolved per week: ' + f.resolved_now + ' (was ' + f.resolved_before + ', ' + d(f.resolved_now, f.resolved_before) + ').' +
    (TREND.undated ? '<br><span style="color:#94a3b8">' + TREND.undated + ' ticket(s) without a usable date are left out of the trend.</span>' : '');
})();

// ══ Enhancements (kept out of every defect chart and count) ════════════════════
(function(){
  const open = ENH.filter(r => !isClosed(r));
  document.getElementById('enhCount').innerHTML = open.length + '<small>open enhancements</small>';
  document.getElementById('enhNote').innerHTML = 'Tickets with the <b>' + esc(ENH_LABEL) + '</b> label. They are not included in the defect counts above.' +
    (ENH.length > open.length ? ' ' + (ENH.length - open.length) + ' already resolved.' : '');
  const el = document.getElementById('enhTable');
  if(!ENH.length){ el.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:24px">No tickets have the &ldquo;' + esc(ENH_LABEL) + '&rdquo; label yet.</p>'; return; }
  const shown = ENH.slice(0, 10);
  let h = '<table class="it"><thead><tr><th>Ticket</th><th>Summary</th><th>Status</th><th>Created</th></tr></thead><tbody>';
  shown.forEach(r => { h += '<tr><td class="ikey">' + keyLink(esc(r.key)) + '</td><td class="isum">' + esc(r.summary) +
    '</td><td><span class="pill ' + sCls(r.status) + '">' + esc(r.status) + '</span></td><td style="white-space:nowrap">' + esc(r.created.slice(0, 10)) + '</td></tr>'; });
  h += '</tbody></table>';
  if(ENH.length > shown.length) h += '<p class="enh-note"><a href="#" onclick="showRows(\'Enhancements\', ENH); return false;">View all ' + ENH.length + '</a></p>';
  el.innerHTML = h;
})();
"""

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
    .it th.sortable{{cursor:pointer;user-select:none;}}
    .it th.sortable:hover{{color:#0ea5e9;}}
    .it th .arr{{display:inline-block;width:12px;margin-left:4px;font-size:.62rem;color:#cbd5e1;}}
    .it th.sorted .arr{{color:#0ea5e9;}}
    .it th{{background:#f8fafc;padding:9px 10px;text-align:left;font-size:.74rem;text-transform:uppercase;letter-spacing:.4px;color:#64748b;border-bottom:2px solid #e2e8f0;white-space:nowrap;}}
    .it td{{padding:9px 10px;border-bottom:1px solid #f1f5f9;vertical-align:top;}}
    .it tr:last-child td{{border-bottom:none;}}
    .it tr:hover td{{background:#f8fafc;}}
    .ikey{{font-weight:700;color:#0052cc;white-space:nowrap;}}
    .ikey a{{color:inherit;text-decoration:none;}}
    .ikey a:hover{{text-decoration:underline;}}
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
    .rank{{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#f1f5f9;color:#64748b;font-size:.75rem;font-weight:700;}}
    .it tr.clickrow:hover td{{background:#eff6ff;cursor:pointer;}}
    .age-pill{{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:20px;font-size:.78rem;font-weight:600;}}
    .age-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px;}}
    .age-box{{border-radius:10px;padding:16px;text-align:center;}}
    .age-box .num{{font-size:2rem;font-weight:800;}}
    .age-box .lbl{{font-size:.75rem;text-transform:uppercase;letter-spacing:.5px;margin-top:4px;}}
{NEW_CSS}  </style>
</head>
<body>

<header>
  <div>
    <h1>Jira Defect Dashboard <span style="font-weight:400;font-size:.95rem;opacity:.85;">&ndash; HEAL, ROIO &amp; ROIN issues reported by the HealthSource Product Support team in the last 12 months</span></h1>
    <p>Generated on {today} &nbsp;|&nbsp; Source: Jira_latest.csv</p>
  </div>
  <div class="badge">{total} Issues</div>
</header>

<p class="clickable-note">&#x1F4CA; Click any card or chart segment to drill into the issues</p>

<div class="kpi-row">
  <div class="kpi" style="--accent:#ef4444" onclick="show('Open / Active','status',OPEN_ST)">
    <div class="num">{open_count}</div><div class="lbl">Open / Active</div><div class="hint">click to view</div>
  </div>
  <div class="kpi" style="--accent:#22c55e" onclick="show('Resolved / Closed','status',CLOSED_ST)">
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
  <div class="kpi" style="--accent:#8b5cf6" onclick="document.getElementById('enhancements').scrollIntoView({{behavior:'smooth'}})">
    <div class="num">{enh_open}</div><div class="lbl">Enhancements</div><div class="hint">not counted above</div>
  </div>
</div>

<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">
  <div class="card">
    <div class="card-head">
      <h2 id="tStatus">Open defects by status</h2>
      <div class="tog" role="group" aria-label="Resolved tickets in status chart">
        <button data-chart="status" data-mode="open" aria-pressed="true">Open only</button>
        <button data-chart="status" data-mode="all" aria-pressed="false">Include resolved</button>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="cStatus"></canvas></div>
  </div>
  <div class="card">
    <div class="card-head">
      <h2 id="tPri">Open defects by priority and status</h2>
      <div class="tog" role="group" aria-label="Resolved tickets in priority chart">
        <button data-chart="pri" data-mode="open" aria-pressed="true">Open only</button>
        <button data-chart="pri" data-mode="all" aria-pressed="false">Include resolved</button>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="cPri"></canvas></div>
  </div>
  <div class="card">
    <div class="card-head">
      <h2 id="tType">Open defects by issue type</h2>
      <div class="tog" role="group" aria-label="Resolved tickets in issue type chart">
        <button data-chart="type" data-mode="open" aria-pressed="true">Open only</button>
        <button data-chart="type" data-mode="all" aria-pressed="false">Include resolved</button>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="cType"></canvas></div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr">
  <div class="card tall">
    <h2>Open defect backlog over time <small style="color:#94a3b8;font-size:.75rem">(weekly, last 12 months)</small></h2>
    <p class="sub">Open and active defects at the end of each week. A falling line means the team is closing the gap.</p>
    <div class="chart-wrap"><canvas id="cTrend"></canvas></div>
    <div class="flow" id="flowText"></div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr">
  <div class="card tall">
    <h2>Issues by Created Month <small style="color:#94a3b8;font-size:.75rem">(click bar to drill in — open vs closed by current status)</small></h2>
    <div class="chart-wrap"><canvas id="cMonthly"></canvas></div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr">
  <div class="card">
    <h2>Open Issue Age Analysis <small style="color:#94a3b8;font-size:.75rem">(click segment to drill in)</small></h2>
    <div class="age-grid">
      <div class="age-box" style="background:#dcfce7;color:#15803d;" id="age0" onclick="showAge('<7d')"><div class="num" id="age0n"></div><div class="lbl">&lt; 7 Days</div></div>
      <div class="age-box" style="background:#fef9c3;color:#92400e;" id="age1" onclick="showAge('7–30d')"><div class="num" id="age1n"></div><div class="lbl">7 – 30 Days</div></div>
      <div class="age-box" style="background:#ffedd5;color:#c2410c;" id="age2" onclick="showAge('30–90d')"><div class="num" id="age2n"></div><div class="lbl">30 – 90 Days</div></div>
      <div class="age-box" style="background:#fee2e2;color:#b91c1c;" id="age3" onclick="showAge('>90d')"><div class="num" id="age3n"></div><div class="lbl">&gt; 90 Days</div></div>
    </div>
    <div class="chart-wrap" style="height:220px;"><canvas id="cAge"></canvas></div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr">
  <div class="card">
    <h2 style="display:flex;justify-content:space-between;align-items:center;">
      Latest 10 Defects &nbsp;<small style="color:#94a3b8;font-size:.75rem;font-weight:400">most recently created</small>
      <button onclick="show('All Issues','all',[])" style="font-size:.75rem;padding:5px 16px;border:1px solid #e2e8f0;border-radius:20px;background:white;color:#0052cc;cursor:pointer;font-weight:600;transition:background .15s;" onmouseover="this.style.background='#eff6ff'" onmouseout="this.style.background='white'">View All</button>
    </h2>
    <div id="top10table"></div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr">
  <div class="card">
    <h2 style="display:flex;justify-content:space-between;align-items:center;">
      Latest 10 Resolved Issues &nbsp;<small style="color:#94a3b8;font-size:.75rem;font-weight:400">most recently resolved</small>
      <button onclick="show('Resolved / Closed','status',['Done',&quot;Won\\'t Do&quot;,'Not a Bug','Cannot Reproduce','Duplicate'])" style="font-size:.75rem;padding:5px 16px;border:1px solid #e2e8f0;border-radius:20px;background:white;color:#22c55e;cursor:pointer;font-weight:600;transition:background .15s;" onmouseover="this.style.background='#f0fdf4'" onmouseout="this.style.background='white'">View All Resolved</button>
    </h2>
    <div id="top10resolvedtable"></div>
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

<div class="grid" style="grid-template-columns:1fr" id="enhancements">
  <div class="card">
    <h2>Enhancements <small style="color:#94a3b8;font-size:.75rem;font-weight:400">separate from the defect charts and counts</small></h2>
    <div class="enh-grid">
      <div><div class="enh-big" id="enhCount"></div><p class="enh-note" id="enhNote"></p></div>
      <div id="enhTable"></div>
    </div>
  </div>
</div>

<footer>Jira_latest.csv &mdash; {total} issues analysed &mdash; Report auto-generated by Claude Code</footer>

<script>
const DATA = {data_json};
const OPEN_ST   = {json.dumps(open_statuses)};
const CLOSED_ST = {json.dumps(closed_statuses)};
const JIRA_BASE = {json.dumps(JIRA_BASE)};
const keyLink = k => `<a href="${{JIRA_BASE}}/browse/${{k}}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${{k}}</a>`;
let cur = [];
const sCls = s => ({{'To Do':'s-todo','Done':'s-done',"Won't Do":'s-wont','In Progress':'s-prog','Blocked':'s-block'}}[s]||'s-other');
const pCls = p => ({{'Critical':'p-critical','High':'p-high','Medium':'p-medium','Low':'p-low'}}[p]||'s-other');

function show(title, field, vals){{
  cur = field==='all' ? DATA
      : field==='reporter' ? DATA.filter(r=>r.reporter===vals[0])
      : (field==='created_month'||field==='resolved_month') ? DATA.filter(r=>vals.includes(r[field]))
      : DATA.filter(r=>vals.includes(r[field]));
  document.getElementById('mtitle').textContent = title;
  document.getElementById('msearch').value = '';
  sortKey = null;
  render();
  document.getElementById('overlay').classList.add('open');
}}
let sortKey = null, sortDir = 1;
const PRI_RANK = {{'Critical':0,'High':1,'Medium':2,'Low':3}};
const COLS = [['key','Key'],['summary','Summary'],['status','Status'],['priority','Priority'],['type','Type'],['reporter','Reporter'],['assignee','Assignee'],['created','Created'],['resolved','Resolved']];
function sortVal(r,k){{
  if(k==='created'||k==='resolved') return r[k+'_ts'] ? Date.parse(r[k+'_ts']) : '';
  if(k==='priority') return r.priority in PRI_RANK ? PRI_RANK[r.priority] : 99;
  if(k==='key'){{ const m=/^(.*?)-([0-9]+)$/.exec(r.key); return m ? [m[1],+m[2]] : [r.key,0]; }}
  return (r[k]||'').toLowerCase();
}}
function cmpRows(a,b){{
  const x=sortVal(a,sortKey), y=sortVal(b,sortKey);
  if(x===''&&y==='') return 0;
  if(x==='') return 1;            // blanks always sink to the bottom
  if(y==='') return -1;
  let c;
  if(Array.isArray(x)) c = x[0].localeCompare(y[0]) || x[1]-y[1];
  else if(typeof x==='number') c = x-y;
  else c = x<y ? -1 : x>y ? 1 : 0;
  return c*sortDir;
}}
function sortBy(k){{
  if(sortKey===k) sortDir = -sortDir;
  else {{ sortKey=k; sortDir = (k==='created'||k==='resolved') ? -1 : 1; }}   // dates: newest first
  render();
}}
function render(){{
  const q = document.getElementById('msearch').value.toLowerCase();
  const rows = q ? cur.filter(r=>[r.key,r.summary,r.reporter,r.assignee,r.priority,r.status,r.type].join(' ').toLowerCase().includes(q)) : cur;
  document.getElementById('mcount').textContent = rows.length + ' issue' + (rows.length!==1?'s':'');
  if(!rows.length){{ document.getElementById('mtable').innerHTML='<p style="color:#94a3b8;text-align:center;padding:32px">No matching issues.</p>'; return; }}
  const sorted = sortKey ? rows.slice().sort(cmpRows) : rows;
  let h='<table class="it"><thead><tr>'+COLS.map(([k,l])=>`<th class="sortable${{k===sortKey?' sorted':''}}" onclick="sortBy('${{k}}')">${{l}}<span class="arr">${{k===sortKey?(sortDir===1?'&#9650;':'&#9660;'):'&#8645;'}}</span></th>`).join('')+'</tr></thead><tbody>';
  sorted.forEach(r=>{{ h+=`<tr><td class="ikey">${{keyLink(r.key)}}</td><td class="isum">${{r.summary}}</td><td><span class="pill ${{sCls(r.status)}}">${{r.status}}</span></td><td><span class="pill ${{pCls(r.priority)}}">${{r.priority}}</span></td><td>${{r.type}}</td><td>${{r.reporter}}</td><td>${{r.assignee||'&mdash;'}}</td><td style="white-space:nowrap">${{r.created}}</td><td style="white-space:nowrap">${{r.resolved||'&mdash;'}}</td></tr>`; }});
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

const TREND = {json.dumps(trend)};
const ENH = {json.dumps(enh_rows)};
const ENH_LABEL = {json.dumps(ENHANCEMENT_LABEL)};
{CHARTS_JS}
new Chart('cRep',{{type:'bar',data:{{labels:{json.dumps(rep_labels)},datasets:[{{label:'Issues',data:{json.dumps(rep_data)},backgroundColor:{rep_colors_js},borderRadius:6}}]}},options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true}},y:{{ticks:{{font:{{size:13}}}}}}}},onClick(_,items){{if(!items.length)return;const n=this.data.labels[items[0].index];show('Reporter: '+n,'reporter',[n]);}},onHover(_,__,chart){{chart.canvas.style.cursor='pointer';}}}}}});

const MONTH_KEYS  = {all_months_js};
const MONTH_DISPS = {json.dumps(month_labels_disp)};
new Chart('cMonthly',{{
  type:'bar',
  data:{{
    labels:MONTH_DISPS,
    datasets:[
      {{label:'Still Open',     data:{json.dumps(created_open_monthly)},   backgroundColor:'rgba(14,165,233,0.8)', borderRadius:4}},
      {{label:'Resolved/Closed',data:{json.dumps(created_closed_monthly)}, backgroundColor:'rgba(34,197,94,0.8)',  borderRadius:4}}
    ]
  }},
  options:{{
    responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'top',labels:{{boxWidth:14,font:{{size:12}}}}}}}},
    scales:{{y:{{beginAtZero:true,ticks:{{stepSize:1}}}},x:{{ticks:{{font:{{size:11}}}}}}}},
    onClick(_,items){{
      if(!items.length) return;
      const idx=items[0].index, dsIdx=items[0].datasetIndex;
      const mkey=MONTH_KEYS[idx], lbl=MONTH_DISPS[idx];
      const stList = dsIdx===0 ? OPEN_ST : CLOSED_ST;
      const label  = dsIdx===0 ? 'Still Open — '+lbl : 'Resolved/Closed — '+lbl;
      cur = DATA.filter(r=>r.created_month===mkey && stList.includes(r.status));
      document.getElementById('mtitle').textContent=label;
      document.getElementById('msearch').value='';
      sortKey = null;
      render();
      document.getElementById('overlay').classList.add('open');
    }},
    onHover(_,__,chart){{chart.canvas.style.cursor='pointer';}}
  }}
}});

// ── Top 10 Latest Defects ──
const TOP10 = {top10_json};
(function(){{
  let h='<table class="it"><thead><tr><th>#</th><th>Key</th><th>Summary</th><th>Status</th><th>Priority</th><th>Reporter</th><th>Assignee</th><th>Created</th></tr></thead><tbody>';
  TOP10.forEach((r,i)=>{{
    h+=`<tr class="clickrow" onclick="show('${{r.key}}','key',['${{r.key}}'])">
      <td><span class="rank">${{i+1}}</span></td>
      <td class="ikey">${{keyLink(r.key)}}</td>
      <td class="isum">${{r.summary}}</td>
      <td><span class="pill ${{sCls(r.status)}}">${{r.status}}</span></td>
      <td><span class="pill ${{pCls(r.priority)}}">${{r.priority}}</span></td>
      <td>${{r.reporter}}</td>
      <td>${{r.assignee||'&mdash;'}}</td>
      <td style="white-space:nowrap">${{r.created}}</td>
    </tr>`;
  }});
  h+='</tbody></table>';
  document.getElementById('top10table').innerHTML=h;
}})();

// ── Top 10 Latest Resolved Issues ──
const TOP10_RESOLVED = {top10_resolved_json};
(function(){{
  if(!TOP10_RESOLVED.length){{
    document.getElementById('top10resolvedtable').innerHTML='<p style="color:#94a3b8;text-align:center;padding:32px">No resolved issues found.</p>';
    return;
  }}
  let h='<table class="it"><thead><tr><th>#</th><th>Key</th><th>Summary</th><th>Status</th><th>Priority</th><th>Reporter</th><th>Assignee</th><th>Resolved</th></tr></thead><tbody>';
  TOP10_RESOLVED.forEach((r,i)=>{{
    h+=`<tr class="clickrow" onclick="show('${{r.key}}','key',['${{r.key}}'])">
      <td><span class="rank">${{i+1}}</span></td>
      <td class="ikey">${{keyLink(r.key)}}</td>
      <td class="isum">${{r.summary}}</td>
      <td><span class="pill ${{sCls(r.status)}}">${{r.status}}</span></td>
      <td><span class="pill ${{pCls(r.priority)}}">${{r.priority}}</span></td>
      <td>${{r.reporter}}</td>
      <td>${{r.assignee||'&mdash;'}}</td>
      <td style="white-space:nowrap">${{r.resolved}}</td>
    </tr>`;
  }});
  h+='</tbody></table>';
  document.getElementById('top10resolvedtable').innerHTML=h;
}})();

// ── Aging Analysis ──
const AGE_DATA = {json.dumps(age_data)};
const AGE_LABELS = {json.dumps(age_labels)};
const AGE_COLORS = {age_colors_js};
const TODAY = new Date(); TODAY.setHours(0,0,0,0);

// Populate mini KPI boxes
AGE_DATA.forEach((v,i)=>{{ document.getElementById('age'+i+'n').textContent=v; }});

new Chart('cAge',{{
  type:'bar',
  data:{{labels:AGE_LABELS,datasets:[{{label:'Open Issues',data:AGE_DATA,backgroundColor:AGE_COLORS,borderRadius:6}}]}},
  options:{{
    responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>ctx.raw+' open issues'}}}}}},
    scales:{{y:{{beginAtZero:true,ticks:{{stepSize:1}}}},x:{{ticks:{{font:{{size:13}}}}}}}},
    onClick(_,items){{if(!items.length)return;showAge(AGE_LABELS[items[0].index]);}},
    onHover(_,__,chart){{chart.canvas.style.cursor='pointer';}}
  }}
}});

function showAge(bucket){{
  const now = new Date(); now.setHours(0,0,0,0);
  const filtered = DATA.filter(r=>{{
    if(!OPEN_ST.includes(r.status)||!r.created_ts) return false;
    const d=new Date(r.created_ts); d.setHours(0,0,0,0);
    const age=Math.floor((now-d)/(1000*60*60*24));
    if(bucket==='<7d')   return age<7;
    if(bucket==='7–30d') return age>=7&&age<30;
    if(bucket==='30–90d')return age>=30&&age<90;
    if(bucket==='>90d')  return age>=90;
    return false;
  }});
  cur=filtered;
  document.getElementById('mtitle').textContent='Open Issues aged '+bucket;
  document.getElementById('msearch').value='';
  sortKey = null;
  render();
  document.getElementById('overlay').classList.add('open');
}}
</script>
</body>
</html>"""

out_path = os.path.join(folder, 'HS CX-Defect.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Report generated: {total} issues processed.")
