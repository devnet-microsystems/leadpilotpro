import re

with open('static/app.js.orig', 'r') as f:
    orig_js = f.read()

with open('static/app.js', 'r') as f:
    current_js = f.read()

with open('static/index.html.bak', 'r') as f:
    orig_html = f.read()

with open('static/index.html', 'r') as f:
    current_html = f.read()

# 1. build app.js (Router + Bootstrap)
# It needs window.fetch override
# switchTab function
# DOMContentLoaded listener to attach click events to nav-item
# fetch /api/status loop (maybe in legacy_outreach?) Actually loadStatus updates stats, maybe keep it in legacy_outreach.
# Let's write a clean app.js

app_js_content = """
// --- GLOBAL ROUTER & BOOTSTRAP ---
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

# 2. Extract research functions from current_js
# Let's find functions that are strictly for research.
# We will use simple regex or split by known functions.
