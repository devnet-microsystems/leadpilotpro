import re

with open('static/index.html.bak', 'r') as f:
    html_bak = f.read()

with open('static/index.html', 'r') as f:
    html_new = f.read()

# We need to extract the tabs. I will use simple regex for <div id="tab-xxx" class="tab-content...">
def extract_tabs(html_str):
    tabs = {}
    pattern = r'(<div\s+id="tab-[^"]+"\s+class="tab-content[^"]*"\s*>.*?(?:<!-- End Tab -->|</div>\s*<div\s+id="tab-|</div>\s*</main>))'
    # Actually regex for nested div is hard. Let's just use Python string finding.
    
    start_str = '<div id="tab-'
    idx = html_str.find(start_str)
    while idx != -1:
        # find the id
        id_start = idx + 9
        id_end = html_str.find('"', id_start)
        tab_id = "tab-" + html_str[id_start:id_end]
        
        # find the end of this tab by looking for the next '<div id="tab-' or '</main>'
        next_tab = html_str.find(start_str, id_end)
        end_main = html_str.find('</main>', id_end)
        
        if next_tab != -1 and (end_main == -1 or next_tab < end_main):
            end_idx = next_tab
        else:
            end_idx = end_main
            
        tabs[tab_id] = html_str[idx:end_idx].strip()
        idx = next_tab
    return tabs

tabs_bak = extract_tabs(html_bak)
tabs_new = extract_tabs(html_new)

# List of requested tabs
# Pending, Approved, Rejected, Quick Send, Outreach Campaigns, Templates, Sender Queue, Email Archive, SMTP Test, System Logs, Research Logs, Legacy Queries, Query History
# And Research 2.0 tabs: Dashboard, Research Campaigns, Query Studio, Companies, Analytics, Providers

print("Bak tabs:", tabs_bak.keys())
print("New tabs:", tabs_new.keys())
