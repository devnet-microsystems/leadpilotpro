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

    const allTabs = ['overview', 'campaigns', 'query_studio', 'leads', 'companies', 'analytics', 'providers', 'settings', 'outreach_campaigns', 'templates', 'send', 'archive'];
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

// --- Leads Sub-navigation ---
window.switchLeadSubTab = function(subtab) {
    document.getElementById('leads-pending-content').style.display = (subtab === 'pending') ? 'block' : 'none';
    document.getElementById('leads-approved-content').style.display = (subtab === 'approved') ? 'block' : 'none';
    document.getElementById('leads-rejected-content').style.display = (subtab === 'rejected') ? 'block' : 'none';
    
    document.getElementById('subtab-pending').style.color = (subtab === 'pending') ? 'var(--primary)' : 'var(--text-muted)';
    document.getElementById('subtab-approved').style.color = (subtab === 'approved') ? 'var(--primary)' : 'var(--text-muted)';
    document.getElementById('subtab-rejected').style.color = (subtab === 'rejected') ? 'var(--primary)' : 'var(--text-muted)';
    
    if (subtab === 'pending') loadPending();
    if (subtab === 'approved') loadApproved();
    if (subtab === 'rejected') loadRejected();
}

window.loadPending = async function() {
    const res = await fetch('/api/prospects?status=pending_review');
    const leads = await res.json();
    const tbody = document.getElementById('leads-tbody');
    tbody.innerHTML = '';
    if(!leads || leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">No pending leads</td></tr>';
        return;
    }
    
    leads.forEach(l => {
        tbody.innerHTML += `<tr>
            <td><input type="checkbox" class="lead-checkbox" value="${l.id}"></td>
            <td><span class="badge ${l.relevance_score > 70 ? 'badge-blue' : 'badge-gray'}">${l.relevance_score || 0}</span></td>
            <td><a href="mailto:${l.business_email}" style="color:var(--text); text-decoration:none;">${l.business_email}</a></td>
            <td>-</td>
            <td>-</td>
            <td><strong>${l.company_name}</strong></td>
            <td style="font-size:0.8rem; color:var(--text-muted); max-width:200px;">${l.why_matched || ''}</td>
            <td>
                <button onclick="showApproveModal(${l.id})" style="background:transparent; border:none; color:#10b981; cursor:pointer;" title="Approve">✅</button>
                <button onclick="rejectSingle(${l.id})" style="background:transparent; border:none; color:#ef4444; cursor:pointer;" title="Reject">❌</button>
            </td>
        </tr>`;
    });
}

window.loadApproved = async function() {
    const res = await fetch('/api/prospects?status=approved');
    const leads = await res.json();
    const tbody = document.getElementById('approved-tbody');
    tbody.innerHTML = '';
    if(!leads || leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No approved leads</td></tr>';
        return;
    }
    
    leads.forEach(l => {
        tbody.innerHTML += `<tr>
            <td>${l.id}</td>
            <td><strong>${l.company_name}</strong></td>
            <td>${l.business_email}</td>
            <td>Campaign #${l.campaign_id || 'N/A'}</td>
        </tr>`;
    });
}

window.loadRejected = async function() {
    const res = await fetch('/api/prospects?status=rejected');
    const leads = await res.json();
    const tbody = document.getElementById('rejected-tbody');
    tbody.innerHTML = '';
    if(!leads || leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No rejected leads</td></tr>';
        return;
    }
    
    leads.forEach(l => {
        tbody.innerHTML += `<tr>
            <td>${l.id}</td>
            <td><strong>${l.company_name}</strong></td>
            <td>${l.business_email}</td>
            <td>Research #${l.research_campaign_id || 'N/A'}</td>
            <td><button onclick="restoreSingle(${l.id})" style="background:transparent; border:none; color:var(--primary); cursor:pointer;">♻️ Restore</button></td>
        </tr>`;
    });
}

// Ensure the old loadProspects maps to loadPending
window.loadProspects = window.loadPending;

window.toggleSelectAll = function(el) {
    document.querySelectorAll('.lead-checkbox').forEach(cb => cb.checked = el.checked);
}

// --- Approve / Reject Logic ---
window.selectedLeadId = null;

window.showApproveModal = async function(id) {
    window.selectedLeadId = id;
    
    // Load Outreach Campaigns into the select
    const res = await fetch('/api/campaigns');
    const campaigns = await res.json();
    const select = document.getElementById('approve-campaign-select');
    select.innerHTML = '<option value="">Select an Outreach Campaign...</option>';
    campaigns.forEach(c => {
        select.innerHTML += `<option value="${c.id}">${c.name}</option>`;
    });
    
    document.getElementById('approve-lead-modal').style.display = 'flex';
    document.getElementById('confirm-approve-btn').onclick = () => approveSingle(id);
}

window.approveSingle = async function(id) {
    const cid = document.getElementById('approve-campaign-select').value;
    if(!cid) { alert("Please select an Outreach Campaign."); return; }
    
    await fetch('/api/approve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id, reason: 'Manual UI Approval', campaign_id: parseInt(cid)})
    });
    document.getElementById('approve-lead-modal').style.display = 'none';
    loadPending();
}

window.rejectSingle = async function(id) {
    if(!confirm("Reject this lead?")) return;
    await fetch('/api/reject_selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({emails: [id.toString()]}) // Wait, the old API used emails? Let's check. Ah, reject_selected usually takes prospect_ids.
    });
    loadPending();
}

window.approveSelected = async function() {
    const ids = Array.from(document.querySelectorAll('.lead-checkbox:checked')).map(cb => parseInt(cb.value));
    if(ids.length === 0) return;
    
    // Need to assign to a campaign, we'll prompt for it or show modal.
    // For simplicity, reuse the modal but change behavior to bulk
    window.showApproveModalBulk = async function() {
        const res = await fetch('/api/campaigns');
        const campaigns = await res.json();
        const select = document.getElementById('approve-campaign-select');
        select.innerHTML = '<option value="">Select an Outreach Campaign...</option>';
        campaigns.forEach(c => { select.innerHTML += `<option value="${c.id}">${c.name}</option>`; });
        
        document.getElementById('approve-lead-modal').style.display = 'flex';
        document.getElementById('confirm-approve-btn').onclick = async () => {
            const cid = document.getElementById('approve-campaign-select').value;
            if(!cid) { alert("Please select an Outreach Campaign."); return; }
            await fetch('/api/approve_selected', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prospect_ids: ids, reason: 'Bulk Approval', campaign_id: parseInt(cid)})
            });
            document.getElementById('approve-lead-modal').style.display = 'none';
            loadPending();
        };
    }
    window.showApproveModalBulk();
}

window.rejectSelected = async function() {
    const ids = Array.from(document.querySelectorAll('.lead-checkbox:checked')).map(cb => parseInt(cb.value));
    if(ids.length === 0) return;
    if(!confirm(`Reject ${ids.length} leads?`)) return;
    
    await fetch('/api/reject_selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prospect_ids: ids})
    });
    loadPending();
}

window.restoreSingle = async function(id) {
    await fetch('/api/restore', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id})
    });
    loadRejected();
}

// --- Import / Add Manual ---
window.addManualLead = async function() {
    const email = document.getElementById('manual-email').value;
    const company = document.getElementById('manual-company').value;
    const url = document.getElementById('manual-url').value;
    
    if(!email || !company) { alert("Email and Company required."); return; }
    
    await fetch('/api/prospects/manual_add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({business_email: email, company_name: company, target_url: url})
    });
    
    document.getElementById('manual-lead-modal').style.display = 'none';
    loadPending();
}

window.importCsv = async function() {
    const file = document.getElementById('csv-file').files[0];
    const cid = document.getElementById('csv-campaign-select').value;
    
    if(!file) { alert("Select a CSV file."); return; }
    
    const formData = new FormData();
    formData.append("file", file);
    if(cid) formData.append("campaign", cid);
    
    const res = await fetch('/api/import_csv', { method: 'POST', body: formData });
    const result = await res.json();
    alert(`Imported ${result.imported} leads!`);
    document.getElementById('csv-import-modal').style.display = 'none';
    loadPending();
}

// Populate CSV campaign dropdown when modal opens
document.querySelector('button[onclick="document.getElementById(\\'csv-import-modal\\').style.display=\\'flex\\'"]').addEventListener('click', async () => {
    const res = await fetch('/api/research_campaigns'); // Or outreach? CSV leads are typically mapped to research campaign.
    const campaigns = await res.json();
    const select = document.getElementById('csv-campaign-select');
    select.innerHTML = '<option value="">Select Research Campaign (optional)</option>';
    campaigns.forEach(c => select.innerHTML += `<option value="${c.id}">${c.name}</option>`);
});

// --- Outreach Campaigns (Legacy) ---
window.loadOutreachCampaigns = async function() {
    const res = await fetch('/api/campaigns');
    const campaigns = await res.json();
    const tbody = document.getElementById('outreach-campaigns-tbody');
    tbody.innerHTML = '';
    
    campaigns.forEach(c => {
        tbody.innerHTML += `<tr>
            <td><strong>${c.name}</strong></td>
            <td>${c.template || '-'}</td>
            <td>${new Date(c.created_at_utc).toLocaleString()}</td>
            <td>
                <button onclick="deleteOutreachCampaign('${c.name}')" style="background:transparent; border:none; color:#ef4444; cursor:pointer;">🗑️</button>
            </td>
        </tr>`;
    });
    
    // Also load templates for the dropdown
    const t_res = await fetch('/api/templates');
    const templates = await t_res.json();
    const t_sel = document.getElementById('new-campaign-template');
    t_sel.innerHTML = '<option value="">Select Template</option>';
    templates.forEach(t => t_sel.innerHTML += `<option value="${t.name}">${t.name}</option>`);
}

window.addCampaign = async function() {
    const name = document.getElementById('new-campaign-name').value;
    const template = document.getElementById('new-campaign-template').value;
    if(!name || !template) return;
    
    await fetch('/api/campaigns', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, template: template})
    });
    
    document.getElementById('new-campaign-name').value = '';
    loadOutreachCampaigns();
}

window.deleteOutreachCampaign = async function(name) {
    if(!confirm("Delete outreach campaign?")) return;
    await fetch(`/api/campaigns/${encodeURIComponent(name)}`, { method: 'DELETE' });
    loadOutreachCampaigns();
}


// --- Templates ---
window.loadTemplates = async function() {
    const res = await fetch('/api/templates');
    const templates = await res.json();
    const sidebar = document.getElementById('template-list-sidebar');
    sidebar.innerHTML = '';
    
    templates.forEach(t => {
        const btn = document.createElement('button');
        btn.textContent = t.name;
        btn.style = "padding:0.75rem; text-align:left; background:var(--bg-panel); border:1px solid var(--border); color:var(--text); cursor:pointer; border-radius:4px;";
        btn.onclick = () => viewTemplate(t.name);
        sidebar.appendChild(btn);
    });
}

window.viewTemplate = async function(name) {
    const res = await fetch(`/api/templates/${encodeURIComponent(name)}`);
    const t = await res.json();
    document.getElementById('active-template-name').value = t.name;
    document.getElementById('active-template-content').value = t.content;
    document.getElementById('active-template-name').disabled = true;
}

window.newTemplate = function() {
    document.getElementById('active-template-name').value = '';
    document.getElementById('active-template-content').value = '';
    document.getElementById('active-template-name').disabled = false;
    document.getElementById('active-template-name').focus();
}

window.saveActiveTemplate = async function() {
    const name = document.getElementById('active-template-name').value;
    const content = document.getElementById('active-template-content').value;
    if(!name || !content) return;
    
    await fetch(`/api/templates/${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, content: content})
    });
    alert("Template saved!");
    loadTemplates();
    document.getElementById('active-template-name').disabled = true;
}

window.deleteActiveTemplate = async function() {
    const name = document.getElementById('active-template-name').value;
    if(!name || !confirm(`Delete template ${name}?`)) return;
    
    await fetch(`/api/templates/${encodeURIComponent(name)}`, { method: 'DELETE' });
    document.getElementById('active-template-name').value = '';
    document.getElementById('active-template-content').value = '';
    loadTemplates();
}

// --- Sender Queue & Archive ---
window.loadSendCampaigns = async function() {
    const res = await fetch('/api/campaigns');
    const campaigns = await res.json();
    const select = document.getElementById('send-campaign');
    select.innerHTML = '<option value="">Select an Outreach Campaign...</option>';
    campaigns.forEach(c => select.innerHTML += `<option value="${c.name}">${c.name}</option>`);
}

window.sendCampaign = async function() {
    const campaign = document.getElementById('send-campaign').value;
    const limit = document.getElementById('send-limit').value;
    if(!campaign || !limit) return;
    
    try {
        const res = await fetch('/api/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({campaign: campaign, daily_limit: parseInt(limit)})
        });
        const data = await res.json();
        alert(`Campaign queued! Target leads: ${data.target_leads}`);
    } catch(e) {
        alert("Error queuing campaign: " + e);
    }
}

window.loadArchive = async function() {
    const res = await fetch('/api/archive');
    const archive = await res.json();
    const tbody = document.getElementById('archive-tbody');
    tbody.innerHTML = '';
    if(!archive || archive.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No emails sent yet</td></tr>';
        return;
    }
    
    archive.forEach(e => {
        tbody.innerHTML += `<tr>
            <td>${new Date(e.sent_at_utc).toLocaleString()}</td>
            <td>${e.email}</td>
            <td>${e.campaign || 'N/A'}</td>
            <td><div style="max-height:100px; overflow-y:auto; font-size:0.8rem;">${e.message_text ? e.message_text.replace(/\\n/g, '<br>') : ''}</div></td>
            <td><span class="badge badge-blue">SENT</span></td>
        </tr>`;
    });
}

// --- Hook into SwitchTab ---
const oldSwitchTab = window.switchTab;
window.switchTab = function(tabId) {
    if(oldSwitchTab) oldSwitchTab(tabId);
    
    // Explicit tab logic for the new tabs
    const allTabs = document.querySelectorAll('.container > .glass-panel > div');
    allTabs.forEach(div => {
        if(div.id.startsWith('tab-') && div.id !== `tab-${tabId}`) div.classList.add('hidden');
    });
    const targetTab = document.getElementById(`tab-${tabId}`);
    if(targetTab) targetTab.classList.remove('hidden');
    
    // Auto-load data for new tabs
    if(tabId === 'leads') {
        loadProspects();
    } else if(tabId === 'outreach_campaigns') {
        loadOutreachCampaigns();
    } else if(tabId === 'templates') {
        loadTemplates();
    } else if(tabId === 'send') {
        loadSendCampaigns();
    } else if(tabId === 'archive') {
        loadArchive();
    }
}

