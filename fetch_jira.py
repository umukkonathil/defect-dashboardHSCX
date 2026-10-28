import os, csv, json, sys, time, urllib.request, urllib.parse, urllib.error, base64

# NOTE: never call input() in this script. It runs unattended under Task
# Scheduler, where there is no console -- a prompt blocks on stdin until the
# scheduler kills the task (exit 0xC000013A), which looks like "never ran".
# Fail loudly with a non-zero exit instead so the wrapper .bat can log it.

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

JIRA_URL   = os.environ.get('JIRA_URL', '').rstrip('/')
JIRA_EMAIL = os.environ.get('JIRA_EMAIL', '')
JIRA_TOKEN = os.environ.get('JIRA_TOKEN', '')

if not JIRA_TOKEN:
    print("ERROR: JIRA_TOKEN not set. Add it to the .env file.")
    sys.exit(1)

# ── JQL Filter ─────────────────────────────────────────────────────────────
# Kept out of the repo on purpose (it names projects and people): set JIRA_JQL in .env
# locally, or in the DEFECT_DASHBOARD secret on GitHub.
JQL = os.environ.get('JIRA_JQL', '').strip()
if not JQL:
    print("ERROR: JIRA_JQL not set. Add the search filter to the .env file / GitHub secret.")
    sys.exit(1)

# ── API Setup ──────────────────────────────────────────────────────────────
FIELDS  = 'summary,status,issuetype,priority,reporter,assignee,created,resolutiondate'
API     = f"{JIRA_URL}/rest/api/3/search/jql"
CREDS   = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
HEADERS = {
    'Authorization': f'Basic {CREDS}',
    'Accept':        'application/json',
}

def jira_get(next_page_token=None, batch=100):
    params = {
        'jql':        JQL,
        'maxResults': batch,
        'fields':     FIELDS,
    }
    if next_page_token:
        params['nextPageToken'] = next_page_token
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

# ── Retry policy ────────────────────────────────────────────────────────────
# Transient failures are common when this runs right after the laptop wakes:
# the task fires before the network stack is up and DNS fails outright.
MAX_ATTEMPTS = 5          # per page
BACKOFF_BASE = 10         # seconds, doubling: 10, 20, 40, 80
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def fetch_page(next_page_token):
    """One page of results, retried on transient errors. Exits non-zero if all
    attempts fail, so the caller sees a real failure rather than a hang."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        last = attempt == MAX_ATTEMPTS
        try:
            return jira_get(next_page_token)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            if e.code not in TRANSIENT_HTTP or last:
                # 401/403/400 will never succeed on retry -- fail immediately.
                print(f"ERROR {e.code}: {body}")
                sys.exit(1)
            reason = f"HTTP {e.code}"
        except Exception as e:
            if last:
                print(f"ERROR: gave up after {MAX_ATTEMPTS} attempts - {e}")
                sys.exit(1)
            reason = f"{type(e).__name__}: {e}"

        wait = BACKOFF_BASE * 2 ** (attempt - 1)
        print(f"  {reason} - attempt {attempt}/{MAX_ATTEMPTS} failed, retrying in {wait}s...")
        sys.stdout.flush()   # wrapper redirects to a log file
        time.sleep(wait)


# ── Fetch all pages ─────────────────────────────────────────────────────────
issues          = []
next_page_token = None
print("Fetching issues from Jira...")
while True:
    data = fetch_page(next_page_token)

    issues         += data.get('issues', [])
    next_page_token = data.get('nextPageToken')
    print(f"  {len(issues)} issues fetched so far...")
    if data.get('isLast', True) or not next_page_token:
        break

# ── Sanity guard ────────────────────────────────────────────────────────────
# A bad or expired token does NOT necessarily give a 401 -- Jira can answer 200
# with an empty result set. Without this guard that writes a header-only CSV,
# gen_report.py builds an empty dashboard, and the .bat commits and pushes it,
# silently replacing a working dashboard with a blank one. Keep the old CSV.
if not issues:
    print("ERROR: Jira returned 0 issues - refusing to overwrite Jira_latest.csv.")
    print("       Check JIRA_TOKEN in .env; an expired token can return 200 with no results.")
    sys.exit(1)

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
