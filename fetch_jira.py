import os, csv, json, urllib.request, urllib.parse, base64

# ── Load .env ──────────────────────────────────────────────────────────────
folder   = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(folder, '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

JIRA_URL   = os.environ.get('JIRA_URL', 'https://datavant.atlassian.net').rstrip('/')
JIRA_EMAIL = os.environ.get('JIRA_EMAIL', 'usha.mukkonathil@datavant.com')
JIRA_TOKEN = os.environ.get('JIRA_TOKEN', '')

if not JIRA_TOKEN:
    print("ERROR: JIRA_TOKEN not set. Add it to the .env file.")
    input("Press Enter to exit...")
    exit(1)

# ── JQL Filter ─────────────────────────────────────────────────────────────
JQL = (
    'created >= -400d '
    'and spaceJira IN (HealthSource,"ROI Operations") '
    'AND reporter in ('
    '712020:2e29551d-b655-4750-a692-251520ee4fa9,'
    '712020:111f29bf-9083-4bd1-b7d4-c17316d2f629,'
    '712020:72958af4-0bec-4287-b6fb-c453b007f1f6,'
    '712020:0d0931ed-5ebb-4cd3-82d3-37787c6fa74c,'
    '712020:d3cf2c8f-8b24-4711-97bf-da1bfd65094d,'
    '712020:978137f2-007d-4588-94b6-b3c05c33ab85,'
    '712020:48d35342-b2cd-476c-beda-a66342a97913,'
    '712020:6c2cff0f-d349-4985-9a4f-8c726499438c'
    ')'
)

# ── API Setup ──────────────────────────────────────────────────────────────
FIELDS  = 'summary,status,issuetype,priority,reporter,assignee,created,resolutiondate'
API     = f"{JIRA_URL}/rest/api/3/search"
CREDS   = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
HEADERS = {
    'Authorization': f'Basic {CREDS}',
    'Accept':        'application/json',
}

def jira_get(start, batch=100):
    params = urllib.parse.urlencode({
        'jql':        JQL,
        'startAt':    start,
        'maxResults': batch,
        'fields':     FIELDS,
    })
    req = urllib.request.Request(f"{API}?{params}", headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

# ── Fetch all pages ─────────────────────────────────────────────────────────
issues = []
start  = 0
print("Fetching issues from Jira...")
while True:
    try:
        data = jira_get(start)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR {e.code}: {body}")
        input("Press Enter to exit...")
        exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        input("Press Enter to exit...")
        exit(1)

    issues += data['issues']
    total   = data['total']
    start  += len(data['issues'])
    print(f"  {start} / {total} issues fetched...")
    if start >= total:
        break

# ── Write CSV ───────────────────────────────────────────────────────────────
csv_path = os.path.join(folder, 'Jira_latest.csv')
COLS = ['Issue key', 'Summary', 'Status', 'Issue Type', 'Priority',
        'Reporter', 'Assignee', 'Created', 'Resolved']

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for issue in issues:
        flds = issue.get('fields', {})
        w.writerow({
            'Issue key':  issue['key'],
            'Summary':    flds.get('summary') or '',
            'Status':     (flds.get('status')     or {}).get('name', ''),
            'Issue Type': (flds.get('issuetype')  or {}).get('name', ''),
            'Priority':   (flds.get('priority')   or {}).get('name', ''),
            'Reporter':   (flds.get('reporter')   or {}).get('displayName', ''),
            'Assignee':   (flds.get('assignee')   or {}).get('displayName', ''),
            'Created':    flds.get('created', '') or '',
            'Resolved':   flds.get('resolutiondate', '') or '',
        })

print(f"Done! {len(issues)} issues saved to Jira_latest.csv")
