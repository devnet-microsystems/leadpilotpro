from bs4 import BeautifulSoup

def get_soup(path):
    with open(path, 'r') as f:
        return BeautifulSoup(f.read(), 'html.parser')

soup_bak = get_soup('static/index.html.bak')
# Wait, index.html was already overwritten by me in the previous step.
# Let's get the one from HEAD!
import subprocess
head_html = subprocess.check_output(['git', 'show', 'HEAD:static/index.html']).decode('utf-8')
soup_head = BeautifulSoup(head_html, 'html.parser')

# Get all tabs
tabs = {}
for t in soup_bak.find_all('div', class_='tab-content'):
    tabs[t['id']] = t

for t in soup_head.find_all('div', class_='tab-content'):
    if t['id'] not in tabs or t['id'] in ['tab-research-campaigns', 'tab-query-studio', 'tab-companies', 'tab-providers', 'tab-dashboard', 'tab-overview']:
        tabs[t['id']] = t

# Get all modals or other direct children of body/main that are not tabs/nav/scripts
extras = {}

def extract_extras(soup):
    for el in soup.find_all('div', style=lambda s: s and 'position:fixed' in s.replace(' ', '')):
        if el.has_attr('id'):
            extras[el['id']] = el

extract_extras(soup_bak)
extract_extras(soup_head)

nav_html = """
<nav class="sidebar">
    <div class="logo">
        <h2>LeadPilot Pro</h2>
    </div>

    <div class="nav-section">
        <div class="nav-section-title">RESEARCH 2.0</div>
        <a href="#" class="nav-item active" data-tab="tab-dashboard">Dashboard Analytics</a>
        <a href="#" class="nav-item" data-tab="tab-research-campaigns">Research Campaigns</a>
        <a href="#" class="nav-item" data-tab="tab-query-studio">Query Studio</a>
        <a href="#" class="nav-item" data-tab="tab-companies">Companies</a>
        <a href="#" class="nav-item" data-tab="tab-providers">Providers</a>
    </div>

    <div class="nav-section">
        <div class="nav-section-title">LEGACY OUTREACH</div>
        <a href="#" class="nav-item" data-tab="tab-pending">Pending Review</a>
        <a href="#" class="nav-item" data-tab="tab-approved">Approved Leads</a>
        <a href="#" class="nav-item" data-tab="tab-rejected">Rejected Leads</a>
        <a href="#" class="nav-item" data-tab="tab-campaigns">Outreach Campaigns</a>
        <a href="#" class="nav-item" data-tab="tab-templates">Templates</a>
        <a href="#" class="nav-item" data-tab="tab-queue">Sender Queue</a>
        <a href="#" class="nav-item" data-tab="tab-quick-send">Quick Send</a>
        <a href="#" class="nav-item" data-tab="tab-archive">Email Archive</a>
    </div>

    <div class="nav-section">
        <div class="nav-section-title">SYSTEM</div>
        <a href="#" class="nav-item" data-tab="tab-settings">Settings</a>
        <a href="#" class="nav-item" data-tab="tab-send-logs">Send Logs</a>
        <a href="#" class="nav-item" data-tab="tab-research-logs">Research Logs</a>
        <a href="#" class="nav-item" data-tab="tab-legacy-queries">Legacy Queries</a>
        <a href="#" class="nav-item" data-tab="tab-history">Query History</a>
    </div>
</nav>
"""

required_tabs = [
    'tab-dashboard', 'tab-research-campaigns', 'tab-query-studio', 'tab-companies', 'tab-providers',
    'tab-pending', 'tab-approved', 'tab-rejected', 'tab-campaigns', 'tab-templates', 'tab-queue', 'tab-quick-send', 'tab-archive',
    'tab-settings', 'tab-send-logs', 'tab-research-logs', 'tab-legacy-queries', 'tab-history'
]

combined_tabs_html = ""
for t_id in required_tabs:
    if t_id in tabs:
        t = tabs[t_id]
        if t_id == 'tab-dashboard':
            if 'active' not in t.get('class', []):
                t['class'] = t.get('class', []) + ['active']
        else:
            if 'active' in t.get('class', []):
                t['class'].remove('active')
        combined_tabs_html += str(t) + "\n"
    else:
        combined_tabs_html += f'<div id="{t_id}" class="tab-content{" active" if t_id == "tab-dashboard" else ""}"><h2>{t_id}</h2><p>Not found in backup</p></div>\n'

combined_extras_html = ""
for e_id, e in extras.items():
    combined_extras_html += str(e) + "\n"

final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LeadPilot Pro - Unified OSINT & Outreach</title>
    <link rel="stylesheet" href="/static/style.css">
    <style>
        .nav-section {{ margin-top: 20px; }}
        .nav-section-title {{ color: var(--text-muted); font-size: 0.75rem; font-weight: bold; padding: 0 1rem; margin-bottom: 0.5rem; letter-spacing: 0.05em; text-transform: uppercase; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
    </style>
</head>
<body>
    <div class="layout">
        {nav_html}
        <main class="content">
            {combined_tabs_html}
        </main>
    </div>
    
    {combined_extras_html}
    
    <script src="/static/app.js"></script>
    <script src="/static/legacy_outreach.js"></script>
    <script src="/static/research.js"></script>
</body>
</html>
"""

with open('static/index.html', 'w') as f:
    f.write(final_html)

print("Full HTML Merged.")
