import re

with open('static/app.js.orig', 'r') as f:
    legacy_code = f.read()

with open('static/app.js', 'r') as f:
    current_code = f.read()

# Remove switchTab from legacy
legacy_lines = legacy_code.split('\n')
out_legacy = []
in_switch = False
for line in legacy_lines:
    if line.startswith('function switchTab('):
        in_switch = True
    if in_switch:
        if line.startswith('}'):
            in_switch = False
        continue
    if line.startswith('window.fetch ='):
        continue
    if line.startswith('const originalFetch'):
        continue
    if 'return res;' in line and 'if (res.status === 401)' in out_legacy[-1] if out_legacy else False:
        out_legacy.pop() # remove previous lines of fetch
        out_legacy.pop()
        continue
        
    out_legacy.append(line)

with open('static/legacy_outreach.js', 'w') as f:
    f.write('\n'.join(out_legacy))

# Extract new research functions from current_code
# Research functions: loadResearchCampaignsTab, createResearchCampaign, loadQueryStudioTab, searchQueries, etc.
# We know they are at the end, or we can just extract them.
research_funcs = []
in_func = False
func_block = []
brace_count = 0

for line in current_code.split('\n'):
    if line.startswith('async function loadAnalyticsDashboard(') or \
       line.startswith('async function loadResearchCampaignsTab(') or \
       line.startswith('async function createResearchCampaign(') or \
       line.startswith('async function loadQueryStudioTab(') or \
       line.startswith('async function searchQueries(') or \
       line.startswith('async function testQueries(') or \
       line.startswith('async function loadCompaniesTab(') or \
       line.startswith('async function searchCompanies(') or \
       line.startswith('async function exportCompanies(') or \
       line.startswith('async function loadProvidersTab(') or \
       line.startswith('async function saveProviderSettings(') or \
       line.startswith('function switchTab(') or \
       line.startswith('async function updateResearchCampaignStatus('):
       in_func = True
       brace_count = 0
       
    if in_func:
        func_block.append(line)
        brace_count += line.count('{')
        brace_count -= line.count('}')
        if brace_count <= 0 and len(func_block) > 0 and '}' in line:
            # function ended
            # Don't include switchTab in research.js
            if not func_block[0].startswith('function switchTab('):
                research_funcs.append('\n'.join(func_block))
            func_block = []
            in_func = False

with open('static/research.js', 'w') as f:
    f.write('\n\n'.join(research_funcs))

app_js_content = """// --- GLOBAL ROUTER & BOOTSTRAP ---
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const res = await originalFetch(...args);
    if (res.status === 401) {
        window.location.href = '/';
    }
    return res;
};

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    
    const targetTab = document.getElementById(tabId);
    if (targetTab) {
        targetTab.classList.add('active');
    }
    
    const navItem = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (navItem) {
        navItem.classList.add('active');
    }

    // Call load functions if they exist in global scope
    if (tabId === 'tab-pending' && typeof loadProspects === 'function') loadProspects('pending_review');
    if (tabId === 'tab-approved' && typeof loadProspects === 'function') loadProspects('approved');
    if (tabId === 'tab-rejected' && typeof loadProspects === 'function') loadProspects('rejected');
    if (tabId === 'tab-campaigns' && typeof loadCampaignsTab === 'function') loadCampaignsTab();
    if (tabId === 'tab-templates' && typeof loadTemplates === 'function') loadTemplates();
    if (tabId === 'tab-archive' && typeof loadArchive === 'function') loadArchive();
    if (tabId === 'tab-settings' && typeof loadSettings === 'function') loadSettings();
    if (tabId === 'tab-history' && typeof loadHistory === 'function') loadHistory();
    if (tabId === 'tab-legacy-queries' && typeof loadQueries === 'function') loadQueries();
    if (tabId === 'tab-queue' && typeof loadQueue === 'function') loadQueue();
    
    // Research
    if (tabId === 'tab-dashboard' && typeof loadAnalyticsDashboard === 'function') loadAnalyticsDashboard();
    if (tabId === 'tab-research-campaigns' && typeof loadResearchCampaignsTab === 'function') loadResearchCampaignsTab();
    if (tabId === 'tab-query-studio' && typeof loadQueryStudioTab === 'function') loadQueryStudioTab();
    if (tabId === 'tab-companies' && typeof loadCompaniesTab === 'function') loadCompaniesTab();
    if (tabId === 'tab-providers' && typeof loadProvidersTab === 'function') loadProvidersTab();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab(item.dataset.tab);
        });
    });

    // Determine initial tab
    const firstNav = document.querySelector('.nav-item');
    if (firstNav) {
        switchTab(firstNav.dataset.tab);
    }
    
    // Run any global inits
    if (typeof loadStatus === 'function') loadStatus();
});
"""

with open('static/app.js', 'w') as f:
    f.write(app_js_content)

print("JS Files generated.")
