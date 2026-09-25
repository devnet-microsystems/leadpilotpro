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
    const container = document.getElementById('campaigns-list');
    if (!container) return;
    if(campaigns.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted);">No campaigns created yet.</p>';
        return;
    }
    container.innerHTML = '<table><thead><tr><th>#</th><th>Name</th><th>Offer</th><th>ICP</th><th>Status</th><th>Action</th></tr></thead><tbody id="campaigns-tbody"></tbody></table>';
    const tbody = document.getElementById('campaigns-tbody');
    campaigns.forEach(c => {
        const statusColor = c.status === 'RUNNING' ? 'var(--accent)' : c.status === 'DRAFT' ? 'var(--text-muted)' : 'var(--primary)';
        const logButton = (c.status === 'RUNNING' || c.status === 'FAILED' || c.status === 'COMPLETED') ? `<button onclick="viewCampaignLogs(${c.id})" style="background:transparent; border:1px solid var(--border); color:var(--text); padding:0.1rem 0.4rem; font-size:0.7rem; margin-left:0.5rem; border-radius:3px; cursor:pointer;">Logs</button>` : '';
        tbody.innerHTML += `<tr>
            <td>#${c.id}</td>
            <td><strong>${c.name}</strong></td>
            <td>${c.offer_name || '—'}</td>
            <td>${c.icp_name || '—'}</td>
            <td><span style="color:${statusColor}; font-weight:bold;">${c.status}</span>${logButton}</td>
            <td><button onclick="viewCampaignQueries(${c.id})" style="background:var(--accent); font-size:0.75rem;">View Plan</button></td>
        </tr>`;
    });
}

async function openNewCampaignModal() {
    const offerSelect = document.getElementById('new-campaign-offer');
    const icpSelect = document.getElementById('new-campaign-icp');
    
    // Clear and show loading
    offerSelect.innerHTML = '<option value="">Loading...</option>';
    icpSelect.innerHTML = '<option value="">Loading...</option>';
    
    document.getElementById('new-campaign-modal').style.display = 'flex';
    
    try {
        const [offersRes, icpsRes] = await Promise.all([
            fetch('/api/sales_offers'),
            fetch('/api/icps')
        ]);
        
        const offers = await offersRes.json();
        const icps = await icpsRes.json();
        
        offerSelect.innerHTML = '<option value="">-- Select Sales Offer --</option>';
        offers.forEach(o => {
            offerSelect.innerHTML += `<option value="${o.id}">${o.name}</option>`;
        });
        
        icpSelect.innerHTML = '<option value="">-- Select ICP --</option>';
        icps.forEach(i => {
            icpSelect.innerHTML += `<option value="${i.id}">${i.name}</option>`;
        });
    } catch (e) {
        console.error("Error loading dropdowns:", e);
        offerSelect.innerHTML = '<option value="">Error loading offers</option>';
        icpSelect.innerHTML = '<option value="">Error loading ICPs</option>';
    }
}
window.openNewCampaignModal = openNewCampaignModal;

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
    const sel = document.getElementById('qs-campaign-select');
    sel.setAttribute('data-pending-val', campaignId);
    switchTab('query_studio');
}

window.globalLogInterval = null;
window.currentGlobalLogCampaign = null;

window.viewCampaignLogs = function(campaignId) {
    window.currentGlobalLogCampaign = campaignId;
    if (window.globalLogInterval) clearInterval(window.globalLogInterval);
    
    const container = document.getElementById('global-live-logs-container');
    if (container) container.style.display = 'block';
    
    const title = document.getElementById('global-live-logs-title');
    if (title) title.textContent = `Live OSINT Logs (Campaign #${campaignId})`;
    
    const output = document.getElementById('global-live-logs-output');
    if (output) output.textContent = 'Loading logs...';
    
    window.globalLogInterval = setInterval(window.fetchGlobalCampaignLogs, 2000);
    window.fetchGlobalCampaignLogs();
}

window.fetchGlobalCampaignLogs = async function() {
    const campaignId = window.currentGlobalLogCampaign;
    if (!campaignId) return;
    
    try {
        const res = await fetch(`/api/research_campaigns/${campaignId}/logs`);
        if (res.ok) {
            const data = await res.json();
            const output = document.getElementById('global-live-logs-output');
            if (output) {
                const isNearBottom = output.scrollHeight - output.scrollTop - output.clientHeight < 50;
                output.textContent = data.logs || 'Waiting for logs...';
                if (isNearBottom) {
                    output.scrollTop = output.scrollHeight;
                }
            }
            if (data.logs && (data.logs.includes('Process exited with code') || data.logs.includes('Error updating DB'))) {
                if (window.globalLogInterval) {
                    clearInterval(window.globalLogInterval);
                    window.globalLogInterval = null;
                }
            }
        }
    } catch (e) {
        console.error('Failed to fetch global logs', e);
    }
}

async function loadQueryStudioDropdown() {
    const res = await fetch('/api/research_campaigns');
    const campaigns = await res.json();
    const sel = document.getElementById('qs-campaign-select');
    const pendingVal = sel.getAttribute('data-pending-val');
    const currVal = pendingVal || sel.value;
    if (pendingVal) sel.removeAttribute('data-pending-val');
    
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
    if (window.qsLogInterval) {
        clearInterval(window.qsLogInterval);
        window.qsLogInterval = null;
    }
    const logContainer = document.getElementById('qs-live-logs-container');
    if (logContainer) logContainer.style.display = 'none';

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
    
    const maxLeads = document.getElementById('qs-max-leads').value || 150;
    
    if(!confirm("Launch OSINT execution for enabled queries? This will take a while.")) return;
    
    try {
        await fetch(`/api/campaigns/${campaignId}/launch`, { 
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ max_leads: parseInt(maxLeads) })
        });
        showToast("Campaign launched! Monitoring logs...", "success");
        window.startLiveLogMonitoring(campaignId);
    } catch (e) {
        showToast("Error launching campaign: " + e, "error");
    }
}

window.qsLogInterval = null;

window.startLiveLogMonitoring = function(campaignId) {
    if (!campaignId) {
        campaignId = document.getElementById('qs-campaign-select').value;
    }
    if (!campaignId) return;

    if (window.qsLogInterval) clearInterval(window.qsLogInterval);
    const container = document.getElementById('qs-live-logs-container');
    if (container) container.style.display = 'block';
    
    const output = document.getElementById('qs-live-logs-output');
    if (output) output.textContent = 'Starting process...';
    
    window.qsLogInterval = setInterval(() => window.fetchCampaignLogs(campaignId), 2000);
    window.fetchCampaignLogs(campaignId);
}

window.fetchCampaignLogs = async function(campaignId) {
    if (!campaignId) {
        campaignId = document.getElementById('qs-campaign-select').value;
    }
    if (!campaignId) return;
    
    try {
        const res = await fetch(`/api/research_campaigns/${campaignId}/logs`);
        if (res.ok) {
            const data = await res.json();
            const output = document.getElementById('qs-live-logs-output');
            if (output) {
                // Only scroll if we are near the bottom to avoid fighting the user scrolling up
                const isNearBottom = output.scrollHeight - output.scrollTop - output.clientHeight < 50;
                output.textContent = data.logs || 'Waiting for logs...';
                if (isNearBottom) {
                    output.scrollTop = output.scrollHeight;
                }
            }
            
            // If process exited, stop polling
            if (data.logs && (data.logs.includes('Process exited with code') || data.logs.includes('Error updating DB'))) {
                if (window.qsLogInterval) {
                    clearInterval(window.qsLogInterval);
                    window.qsLogInterval = null;
                }
            }
        }
    } catch (e) {
        console.error('Failed to fetch campaign logs', e);
    }
}

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

window.showApproveModal = function(id) {
    if (typeof approveSingle === 'function') {
        approveSingle(id);
    } else {
        alert("Approve functionality not available.");
    }
}

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

window.deleteOutreachCampaign = async function(name) {
    if(!confirm("Delete outreach campaign?")) return;
    await fetch(`/api/campaigns/${encodeURIComponent(name)}`, { method: 'DELETE' });
    loadOutreachCampaigns();
}

window.loadSendCampaigns = async function() {
    const res = await fetch('/api/campaigns');
    const campaigns = await res.json();
    const select = document.getElementById('send-campaign');
    select.innerHTML = '<option value="">Select an Outreach Campaign...</option>';
    campaigns.forEach(c => select.innerHTML += `<option value="${c.name}">${c.name}</option>`);
}

// --- Qualified Leads ---
// Shows pending_review prospects that came from a Research Campaign (research_campaign_id set)
window.loadLeads = async function() {
    const tbody = document.getElementById('leads-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading...</td></tr>';

    const res = await fetch('/api/prospects?status=pending_review');
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Error loading leads.</td></tr>'; return; }
    const data = await res.json();

    const leads = data.filter(p => p.research_campaign_name != null);
    if (leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No qualified leads yet. Launch a Research Campaign to generate leads.</td></tr>';
        return;
    }

    tbody.innerHTML = '';
    leads.forEach(p => {
        const score = p.relevance_score != null ? Math.round(p.relevance_score) : '—';
        const conf = p.email_confidence != null ? (p.email_confidence * 100).toFixed(0) + '%' : '—';
        const scoreColor = score >= 70 ? 'var(--accent)' : score >= 40 ? 'var(--primary)' : 'var(--text-muted)';
        tbody.innerHTML += `<tr>
            <td>${escapeHtml(p.company_name ?? '')}</td>
            <td>${escapeHtml(p.business_email ?? '')}</td>
            <td style="color:var(--text-muted); font-size:0.8rem;">${escapeHtml(p.why_matched ?? '—')}</td>
            <td style="color:var(--text-muted); font-size:0.8rem;">${escapeHtml(p.research_campaign_name ?? '—')}</td>
            <td style="color:${scoreColor}; font-weight:bold;">${score}</td>
            <td>${conf}</td>
            <td>
                <button onclick="switchTab('pending')" style="background:var(--primary); font-size:0.75rem; padding:0.3rem 0.6rem;">Review →</button>
            </td>
        </tr>`;
    });
}

// --- Performance Analytics ---
// Reads /api/analytics (existing backend endpoint) and renders real data only
window.loadAnalytics = async function() {
    const container = document.querySelector('#tab-analytics');
    if (!container) return;

    // Find or create the analytics output area (leave action-bar intact)
    let output = container.querySelector('#analytics-output');
    if (!output) {
        output = document.createElement('div');
        output.id = 'analytics-output';
        container.appendChild(output);
    }
    output.innerHTML = '<p style="color:var(--text-muted);">Loading analytics...</p>';

    const res = await fetch('/api/analytics');
    if (!res.ok) { output.innerHTML = '<p style="color:var(--text-muted);">Could not load analytics.</p>'; return; }
    const data = await res.json();

    const rel = data.relevance || {};
    const camps = data.campaigns || {};
    const total = (rel.high || 0) + (rel.medium || 0) + (rel.low || 0);

    let html = `
        <div class="glass-panel" style="margin-bottom:1rem; padding:1.5rem;">
            <h3 style="margin-bottom:1rem; color:var(--text-muted); font-size:0.9rem; text-transform:uppercase;">Lead Relevance Distribution (${total} total)</h3>
            <div style="display:flex; gap:1rem; flex-wrap:wrap;">
                <div class="stat-card glass-panel" style="flex:1; min-width:120px; text-align:center; padding:1rem;">
                    <div style="color:var(--accent); font-size:2rem; font-weight:700;">${rel.high || 0}</div>
                    <div style="color:var(--text-muted); font-size:0.8rem;">High (≥70)</div>
                </div>
                <div class="stat-card glass-panel" style="flex:1; min-width:120px; text-align:center; padding:1rem;">
                    <div style="color:var(--primary); font-size:2rem; font-weight:700;">${rel.medium || 0}</div>
                    <div style="color:var(--text-muted); font-size:0.8rem;">Medium (40–69)</div>
                </div>
                <div class="stat-card glass-panel" style="flex:1; min-width:120px; text-align:center; padding:1rem;">
                    <div style="color:var(--text-muted); font-size:2rem; font-weight:700;">${rel.low || 0}</div>
                    <div style="color:var(--text-muted); font-size:0.8rem;">Low (&lt;40)</div>
                </div>
            </div>
        </div>`;

    const campEntries = Object.entries(camps);
    if (campEntries.length > 0) {
        html += `<div class="glass-panel" style="padding:1.5rem;">
            <h3 style="margin-bottom:1rem; color:var(--text-muted); font-size:0.9rem; text-transform:uppercase;">Leads per Research Campaign</h3>
            <table><thead><tr><th>Campaign</th><th>Leads Generated</th></tr></thead><tbody>`;
        campEntries.sort((a,b) => b[1] - a[1]).forEach(([name, count]) => {
            html += `<tr><td>${escapeHtml(name)}</td><td style="font-weight:bold;">${count}</td></tr>`;
        });
        html += `</tbody></table></div>`;
    } else {
        html += `<div class="glass-panel" style="padding:1.5rem;"><p style="color:var(--text-muted);">No campaign data yet.</p></div>`;
    }

    output.innerHTML = html;
}