const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const res = await originalFetch(...args);
    if (res.status === 401) {
        window.location.href = '/';
    }
    return res;
};

// ---------------------------------------------------------
// ROUTER & TABS
// ---------------------------------------------------------
function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    
    // Attempt to find the specific tab (handling dropdowns too)
    const tabElement = document.querySelector(`.tab[onclick="switchTab('${tabId}')"]`);
    if(tabElement) tabElement.classList.add('active');

    const allTabs = ['overview', 'campaigns', 'query_studio', 'leads', 'companies', 'analytics', 'providers', 'settings'];
    allTabs.forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        if (el) el.classList.add('hidden');
    });

    const target = document.getElementById(`tab-${tabId}`);
    if (target) target.classList.remove('hidden');

    // Load data based on tab
    if (tabId === 'overview') loadStatus();
    else if (tabId === 'campaigns') loadCampaignsTab();
    else if (tabId === 'query_studio') loadQueryStudioDropdown();
    else if (tabId === 'leads') loadProspects();
    else if (tabId === 'companies') loadCompanies();
    // else if (tabId === 'analytics') loadAnalytics();
    // else if (tabId === 'providers') loadProviders();
    else if (tabId === 'settings') loadSettings();
}

// ---------------------------------------------------------
// DASHBOARD OVERVIEW
// ---------------------------------------------------------
let sentChartInstance = null;

async function loadStatus() {
    try {
        const res = await fetch('/api/dashboard_stats');
        const data = await res.json();
        
        document.getElementById('stat-campaigns').innerText = data.total_campaigns || 0;
        document.getElementById('stat-queries-gen').innerText = data.queries_generated || 0;
        document.getElementById('stat-queries-exec').innerText = data.queries_executed || 0;
        document.getElementById('stat-leads').innerText = data.leads_found || 0;
        document.getElementById('stat-qualified').innerText = data.qualified_leads || 0;
        document.getElementById('stat-yield').innerText = data.qualified_yield || '0%';
        
        loadChart();
    } catch(e) {
        console.error("Error loading dashboard stats", e);
    }
}

async function loadChart() {
    const res = await fetch('/api/chart_data');
    const data = await res.json();
    
    const ctx = document.getElementById('sentChart').getContext('2d');
    if (sentChartInstance) sentChartInstance.destroy();
    
    sentChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates.length ? data.dates : ['No data'],
            datasets: [{
                label: 'Emails Sent',
                data: data.counts.length ? data.counts : [0],
                borderColor: '#10b981',
                tension: 0.1,
                fill: true,
                backgroundColor: 'rgba(16, 185, 129, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#94a3b8' } },
                x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#94a3b8' } }
            },
            plugins: {
                legend: { labels: { color: '#e2e8f0' } }
            }
        }
    });
}

// ---------------------------------------------------------
// CAMPAIGNS TAB
// ---------------------------------------------------------
async function loadCampaignsTab() {
    await loadSalesOffers();
    await loadICPs();
    await loadCampaignsList();
    
    // Also populate modals
    const res = await fetch('/api/sales_offers');
    const offers = await res.json();
    const selOffer = document.getElementById('new-campaign-offer');
    selOffer.innerHTML = '';
    offers.forEach(o => {
        selOffer.innerHTML += `<option value="${o.id}">${o.name}</option>`;
    });

    const res2 = await fetch('/api/icps');
    const icps = await res2.json();
    const selICP = document.getElementById('new-campaign-icp');
    selICP.innerHTML = '';
    icps.forEach(i => {
        selICP.innerHTML += `<option value="${i.id}">${i.name}</option>`;
    });
}

async function loadSalesOffers() {
    const res = await fetch('/api/sales_offers');
    const offers = await res.json();
    const tbody = document.getElementById('offers-tbody');
    tbody.innerHTML = '';
    if(offers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2">No offers found.</td></tr>';
        return;
    }
    offers.forEach(o => {
        tbody.innerHTML += `<tr>
            <td><strong>${o.name}</strong></td>
            <td style="color:var(--text-muted);">${o.description}</td>
        </tr>`;
    });
}

async function createOffer() {
    const name = document.getElementById('new-offer-name').value;
    const desc = document.getElementById('new-offer-desc').value;
    if(!name || !desc) return alert("Fill all fields");
    await fetch('/api/sales_offers', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, description: desc})
    });
    document.getElementById('new-offer-name').value = '';
    document.getElementById('new-offer-desc').value = '';
    loadCampaignsTab();
}

async function loadICPs() {
    const res = await fetch('/api/icps');
    const icps = await res.json();
    const tbody = document.getElementById('icps-tbody');
    tbody.innerHTML = '';
    if(icps.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2">No ICPs found.</td></tr>';
        return;
    }
    icps.forEach(i => {
        tbody.innerHTML += `<tr>
            <td><strong>${i.name}</strong></td>
            <td style="color:var(--text-muted); font-size:0.8rem;">
                Roles: ${i.roles}<br>Ind: ${i.industries}<br>Loc: ${i.locations}
            </td>
        </tr>`;
    });
}

async function createICP() {
    const name = document.getElementById('new-icp-name').value;
    const roles = document.getElementById('new-icp-roles').value;
    const ind = document.getElementById('new-icp-industries').value;
    const loc = document.getElementById('new-icp-locations').value;
    if(!name || !roles || !ind || !loc) return alert("Fill all fields");
    
    await fetch('/api/icps', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, roles, industries: ind, locations: loc})
    });
    
    document.getElementById('new-icp-name').value = '';
    document.getElementById('new-icp-roles').value = '';
    document.getElementById('new-icp-industries').value = '';
    document.getElementById('new-icp-locations').value = '';
    loadCampaignsTab();
}

async function loadCampaignsList() {
    const res = await fetch('/api/research_campaigns');
    const campaigns = await res.json();
    const tbody = document.getElementById('campaigns-tbody');
    tbody.innerHTML = '';
    if(campaigns.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No campaigns created yet.</td></tr>';
        return;
    }
    
    campaigns.forEach(c => {
        tbody.innerHTML += `<tr>
            <td>#${c.id}</td>
            <td><strong>${c.name}</strong></td>
            <td>${c.offer_name}</td>
            <td>${c.icp_name}</td>
            <td><span class="badge ${c.status === 'active' ? 'badge-green' : 'badge-blue'}">${c.status}</span></td>
            <td>
                <button onclick="viewCampaignQueries(${c.id})" style="background:var(--accent); font-size:0.75rem;">View Plan</button>
            </td>
        </tr>`;
    });
}

async function createResearchCampaign() {
    const name = document.getElementById('new-campaign-name-input').value;
    const offer_id = parseInt(document.getElementById('new-campaign-offer').value);
    const icp_id = parseInt(document.getElementById('new-campaign-icp').value);
    
    if(!name || !offer_id || !icp_id) return alert("Fill all fields");
    
    const res = await fetch('/api/research_campaigns', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, offer_id, icp_id})
    });
    const result = await res.json();
    
    // Generate Plan Automatically
    await fetch(`/api/campaigns/${result.id}/generate_plan`, { method: 'POST' });
    
    document.getElementById('new-campaign-modal').style.display='none';
    document.getElementById('new-campaign-name-input').value = '';
    loadCampaignsTab();
}

window.viewCampaignQueries = function(campaignId) {
    switchTab('query_studio');
    const sel = document.getElementById('qs-campaign-select');
    sel.value = campaignId;
    loadQueryStudio();
}

// ---------------------------------------------------------
// QUERY STUDIO
// ---------------------------------------------------------
async function loadQueryStudioDropdown() {
    const res = await fetch('/api/research_campaigns');
    const campaigns = await res.json();
    const sel = document.getElementById('qs-campaign-select');
    const currVal = sel.value;
    
    sel.innerHTML = '<option value="">Select Campaign...</option>';
    campaigns.forEach(c => {
        sel.innerHTML += `<option value="${c.id}">${c.name}</option>`;
    });
    
    if(currVal) {
        sel.value = currVal;
        loadQueryStudio();
    }
}

window.loadQueryStudio = async function() {
    const campaignId = document.getElementById('qs-campaign-select').value;
    const btn = document.getElementById('btn-launch-campaign');
    const tbody = document.getElementById('qs-queries-tbody');
    
    if(!campaignId) {
        btn.disabled = true;
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Select a campaign to view queries.</td></tr>';
        return;
    }
    
    btn.disabled = false;
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Loading queries...</td></tr>';
    
    const res = await fetch(`/api/campaigns/${campaignId}/queries`);
    const queries = await res.json();
    
    tbody.innerHTML = '';
    if(queries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No queries generated for this campaign.</td></tr>';
        return;
    }
    
    queries.forEach(q => {
        // target_key is expected to be ROLE|INDUSTRY|LOCATION
        const parts = (q.target_key || '').split('|');
        const role = parts[0] || '-';
        const ind = parts[1] || '-';
        const loc = parts[2] || '-';
        
        tbody.innerHTML += `<tr>
            <td><input type="checkbox" ${q.is_enabled ? 'checked' : ''} onchange="toggleCampaignQuery(${q.id}, this.checked)"></td>
            <td><span class="badge badge-blue">${q.family}</span></td>
            <td>
                <div style="display:flex; gap:0.5rem; align-items:center;">
                    <input type="text" id="query-input-${q.id}" value="${q.query.replace(/"/g, '&quot;')}" style="flex:1; padding:0.25rem; font-family:monospace; background:transparent; border:1px solid transparent;" onfocus="this.style.border='1px solid var(--primary)'" onblur="updateCampaignQuery(${q.id}, this.value); this.style.border='1px solid transparent'">
                    <span style="font-size:0.75rem; color:var(--text-muted); cursor:help;" title="Click the text to edit">✏️</span>
                </div>
            </td>
            <td style="color:var(--text-muted); font-size:0.8rem;">Role: ${role}<br>Ind: ${ind}<br>Loc: ${loc}</td>
        </tr>`;
    });
}

window.updateCampaignQuery = async function(queryId, newText) {
    if(!newText.trim()) return;
    await fetch(`/api/campaign_queries/${queryId}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ query: newText.trim() })
    });
}

window.toggleCampaignQuery = async function(queryId, isEnabled) {
    await fetch(`/api/campaign_queries/${queryId}/toggle`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ is_enabled: isEnabled ? 1 : 0 })
    });
}

window.launchCampaignQueries = async function() {
    const campaignId = document.getElementById('qs-campaign-select').value;
    if(!campaignId) return;
    
    if(!confirm("Launch OSINT execution for enabled queries? This will take a while.")) return;
    
    try {
        await fetch(`/api/campaigns/${campaignId}/launch`, { method: 'POST' });
        alert("Campaign launched! Check terminal logs to run the backend runner.");
        // We could trigger the backend process here, but LeadPilot usually expects manual or cron triggering.
    } catch (e) {
        alert("Error launching campaign: " + e);
    }
}

// ---------------------------------------------------------
// LEADS TAB
// ---------------------------------------------------------
window.loadProspects = async function() {
    const tbody = document.getElementById('leads-tbody');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Loading...</td></tr>';
    
    try {
        // Just fetch all leads for now or specific status
        const res = await fetch('/api/prospects?status=pending_review');
        if (!res.ok) throw new Error("Failed to load");
        const data = await res.json();
        tbody.innerHTML = '';
        
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No leads found.</td></tr>';
            return;
        }

        data.forEach(p => {
            let scoreBadge = '';
            if (p.relevance_score >= 80) scoreBadge = `<span class="badge badge-green">${p.relevance_score}</span>`;
            else if (p.relevance_score >= 40) scoreBadge = `<span class="badge badge-blue">${p.relevance_score}</span>`;
            else scoreBadge = `<span class="badge badge-red">${p.relevance_score}</span>`;
            
            tbody.innerHTML += `<tr>
                <td>${scoreBadge}</td>
                <td><strong>${p.email}</strong></td>
                <td>${p.first_name || ''} ${p.last_name || ''}<br><span style="font-size:0.8rem; color:var(--text-muted);">${p.role || ''}</span></td>
                <td>${p.role}</td>
                <td>${p.company_name}</td>
                <td style="font-size:0.8rem; color:var(--text-muted); max-width: 300px;">${p.why_matched || '-'}</td>
            </tr>`;
        });
    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:red;">Error loading leads.</td></tr>';
    }
}

// ---------------------------------------------------------
// COMPANIES TAB (ROLLUP)
// ---------------------------------------------------------
window.loadCompanies = async function() {
    const tbody = document.getElementById('companies-tbody');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading...</td></tr>';
    
    try {
        const res = await fetch('/api/companies');
        const data = await res.json();
        
        tbody.innerHTML = '';
        if(data.companies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No companies found.</td></tr>';
            return;
        }
        
        data.companies.forEach(c => {
            const date = c.last_discovered ? c.last_discovered.substring(0, 10) : '-';
            // handle single quotes in company names
            const escapedCompany = c.company_name ? c.company_name.replace(/'/g, "\\'") : '';
            tbody.innerHTML += `<tr>
                <td><strong>${c.company_name}</strong></td>
                <td><a href="http://${c.target_url}" target="_blank" style="color:var(--primary); text-decoration:none;">${c.target_url || '-'}</a></td>
                <td>${c.lead_count}</td>
                <td><span style="color:var(--accent); font-weight:bold;">${c.qualified_leads}</span></td>
                <td>${c.best_score}</td>
                <td style="color:var(--text-muted); font-size:0.85rem;">${date}</td>
                <td><button onclick="viewCompanyDetails('${escapedCompany}', '${c.target_url}')" style="font-size:0.75rem;">View Leads</button></td>
            </tr>`;
        });
    } catch (e) {
        console.error(e);
    }
}

window.viewCompanyDetails = async function(companyName, domain) {
    document.getElementById('modal-company-name').innerText = companyName;
    document.getElementById('modal-company-domain').innerText = domain || '';
    
    const tbody = document.getElementById('modal-company-leads-tbody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Loading...</td></tr>';
    
    document.getElementById('company-detail-modal').style.display = 'flex';
    
    try {
        const res = await fetch(`/api/companies/${encodeURIComponent(companyName)}/leads`);
        const data = await res.json();
        tbody.innerHTML = '';
        
        data.leads.forEach(p => {
            let scoreBadge = '';
            if (p.relevance_score >= 80) scoreBadge = `<span class="badge badge-green">${p.relevance_score}</span>`;
            else if (p.relevance_score >= 40) scoreBadge = `<span class="badge badge-blue">${p.relevance_score}</span>`;
            else scoreBadge = `<span class="badge badge-red">${p.relevance_score}</span>`;
            
            tbody.innerHTML += `<tr>
                <td>${scoreBadge}</td>
                <td><strong>${p.email}</strong></td>
                <td>${p.first_name || ''} ${p.last_name || ''}<br><span style="color:var(--text-muted); font-size:0.8rem;">${p.role || '-'}</span></td>
                <td style="font-size:0.85rem; max-width:300px;">${p.why_matched || '-'}</td>
            </tr>`;
        });
    } catch(e) {
        console.error(e);
    }
}

// ---------------------------------------------------------
// SETTINGS TAB
// ---------------------------------------------------------
async function loadSettings() {
    const res = await fetch('/api/settings');
    const data = await res.json();
    if(data.ai_api_key) document.getElementById('setting-ai-key').value = data.ai_api_key;
}

window.saveSettings = async function() {
    const settings = {
        ai_api_key: document.getElementById('setting-ai-key').value
    };
    await fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(settings)
    });
    alert('Settings saved');
}

window.logout = async function() {
    document.cookie = "session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = '/';
}

// Initialize on load
switchTab('overview');
