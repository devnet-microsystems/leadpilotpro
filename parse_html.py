from bs4 import BeautifulSoup
import re

with open('static/index.html.bak', 'r') as f:
    soup_bak = BeautifulSoup(f.read(), 'html.parser')

with open('static/index.html', 'r') as f:
    soup_new = BeautifulSoup(f.read(), 'html.parser')

tabs_html = {}
for tab in soup_bak.find_all('div', class_='tab-content'):
    tabs_html[tab['id']] = str(tab)

for tab in soup_new.find_all('div', class_='tab-content'):
    if tab['id'] not in tabs_html or tab['id'] in ['tab-research-campaigns', 'tab-query-studio', 'tab-companies', 'tab-providers', 'tab-dashboard', 'tab-settings', 'tab-overview']:
        tabs_html[tab['id']] = str(tab)

# We need to rename Outreach Campaigns tab if it clashes with Research Campaigns.
# In index.html.bak it was id="tab-campaigns". In index.html the new ones are tab-research-campaigns.
# So "tab-campaigns" is Outreach Campaigns.

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

# Let's map required tabs to the IDs we found.
# Some might not exist, we just output what we found.
# Ensure all IDs are unique.
required_tabs = [
    'tab-dashboard', 'tab-research-campaigns', 'tab-query-studio', 'tab-companies', 'tab-providers',
    'tab-pending', 'tab-approved', 'tab-rejected', 'tab-campaigns', 'tab-templates', 'tab-queue', 'tab-quick-send', 'tab-archive',
    'tab-settings', 'tab-send-logs', 'tab-research-logs', 'tab-legacy-queries', 'tab-history'
]

combined_tabs_html = ""
for t_id in required_tabs:
    if t_id in tabs_html:
        # Check if tab has active class, only dashboard should have it initially
        tab_str = tabs_html[t_id]
        if t_id == 'tab-dashboard':
            if 'active' not in tab_str.split('>', 1)[0]:
                tab_str = tab_str.replace('class="tab-content"', 'class="tab-content active"', 1)
        else:
            tab_str = tab_str.replace('class="tab-content active"', 'class="tab-content"')
            tab_str = tab_str.replace('class="tab-content  active"', 'class="tab-content"')
        combined_tabs_html += tab_str + "\n"
    else:
        # Create a placeholder if not found
        combined_tabs_html += f'<div id="{t_id}" class="tab-content{" active" if t_id == "tab-dashboard" else ""}"><h2>{t_id}</h2><p>Not found in backup</p></div>\n'

# Build full HTML
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
        /* Make sure tab-content hides correctly */
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
    <script src="/static/app.js"></script>
    <script src="/static/legacy_outreach.js"></script>
    <script src="/static/research.js"></script>
</body>
</html>
"""

with open('static/index.html', 'w') as f:
    f.write(final_html)

print("HTML Merged.")
