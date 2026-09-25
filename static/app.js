// --- Custom UI Components ---
window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
};

window.showConfirm = function(message) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content" style="text-align: center;">
                <h3 style="margin-bottom: 1rem;">Confirm Action</h3>
                <p style="margin-bottom: 1.5rem; color: var(--text-muted);">${message}</p>
                <div style="display: flex; gap: 1rem; justify-content: center;">
                    <button id="btn-confirm-no" style="background: rgba(255,255,255,0.1);">Cancel</button>
                    <button id="btn-confirm-yes" class="btn-success">Confirm</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        document.getElementById('btn-confirm-no').onclick = () => {
            overlay.remove();
            resolve(false);
        };
        document.getElementById('btn-confirm-yes').onclick = () => {
            overlay.remove();
            resolve(true);
        };
    });
};

window.showPrompt = function(message, defaultValue = '') {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content">
                <h3 style="margin-bottom: 1rem;">Input Required</h3>
                <p style="margin-bottom: 0.5rem; color: var(--text-muted);">${message}</p>
                <input type="text" id="prompt-input" value="${defaultValue}" style="width: 100%; margin-bottom: 1.5rem;" />
                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                    <button id="btn-prompt-no" style="background: rgba(255,255,255,0.1);">Cancel</button>
                    <button id="btn-prompt-yes" class="btn-success">Submit</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        const input = document.getElementById('prompt-input');
        input.focus();
        
        document.getElementById('btn-prompt-no').onclick = () => {
            overlay.remove();
            resolve(null);
        };
        document.getElementById('btn-prompt-yes').onclick = () => {
            overlay.remove();
            resolve(input.value);
        };
    });
};

window.alert = (msg) => window.showToast(msg, 'warning');

const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const res = await originalFetch(...args);
    if (res.status === 401) {
        window.location.href = '/';
    }
    return res;
};

async function loadStatus() {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('stat-total').innerText = data.total || 0;
    document.getElementById('stat-pending').innerText = data.pending;
    document.getElementById('stat-approved').innerText = data.approved;
    document.getElementById('stat-sent').innerText = data.sent;

    const select = document.getElementById('campaign-select');
    const sendCampaignSelect = document.getElementById('send-campaign');
    const targetCampaignSelect = document.getElementById('target-campaign');
    const csvCampaignSelect = document.getElementById('csv-upload-campaign');
    const manualCampaignSelect = document.getElementById('manual-lead-campaign');
    const quickSendCampaignSelect = document.getElementById('quick-send-campaign-select');
    const contactsCampaignSelect = document.getElementById('contacts-campaign-select');
    
    const currSelect = select ? select.value : '';
    const currSend = sendCampaignSelect ? sendCampaignSelect.value : '';
    const currTarget = targetCampaignSelect ? targetCampaignSelect.value : '';
    const currCsv = csvCampaignSelect ? csvCampaignSelect.value : '';
    const currManual = manualCampaignSelect ? manualCampaignSelect.value : '';
    const currQuickSend = quickSendCampaignSelect ? quickSendCampaignSelect.value : '';
    const currContacts = contactsCampaignSelect ? contactsCampaignSelect.value : '';

    if (select) select.innerHTML = '<option value="">Select campaign...</option>';
    if (sendCampaignSelect) sendCampaignSelect.innerHTML = '<option value="">Select campaign...</option>';
    if (targetCampaignSelect) targetCampaignSelect.innerHTML = '<option value="">Select Target Campaign</option>';
    if (csvCampaignSelect) csvCampaignSelect.innerHTML = '<option value="">Select target campaign...</option>';
    if (manualCampaignSelect) manualCampaignSelect.innerHTML = '<option value="">Select target campaign...</option>';
    if (quickSendCampaignSelect) quickSendCampaignSelect.innerHTML = '<option value="">Select target campaign...</option>';
    if (contactsCampaignSelect) contactsCampaignSelect.innerHTML = '<option value="">Select target campaign...</option>';
    
    data.campaigns.forEach(c => {
        if (select) {
            const opt = document.createElement('option');
            opt.value = c;
            opt.innerText = c;
            select.appendChild(opt);
        }
        
        if (sendCampaignSelect) {
            const optSend = document.createElement('option');
            optSend.value = c;
            optSend.innerText = c;
            sendCampaignSelect.appendChild(optSend);
        }
        
        if (targetCampaignSelect) {
            const optTarget = document.createElement('option');
            optTarget.value = c;
            optTarget.innerText = c;
            targetCampaignSelect.appendChild(optTarget);
        }
        
        if (csvCampaignSelect) {
            const optCsv = document.createElement('option');
            optCsv.value = c;
            optCsv.innerText = c;
            csvCampaignSelect.appendChild(optCsv);
        }
        
        if (manualCampaignSelect) {
            const optManual = document.createElement('option');
            optManual.value = c;
            optManual.innerText = c;
            manualCampaignSelect.appendChild(optManual);
        }

        if (quickSendCampaignSelect) {
            const optQuickSend = document.createElement('option');
            optQuickSend.value = c;
            optQuickSend.innerText = c;
            quickSendCampaignSelect.appendChild(optQuickSend);
        }

        if (contactsCampaignSelect) {
            const optContacts = document.createElement('option');
            optContacts.value = c;
            optContacts.innerText = c;
            contactsCampaignSelect.appendChild(optContacts);
        }
    });

    if (select && currSelect) select.value = currSelect;
    if (sendCampaignSelect && currSend) sendCampaignSelect.value = currSend;
    if (targetCampaignSelect && currTarget) targetCampaignSelect.value = currTarget;
    if (csvCampaignSelect && currCsv) csvCampaignSelect.value = currCsv;
    if (manualCampaignSelect && currManual) manualCampaignSelect.value = currManual;
    if (quickSendCampaignSelect && currQuickSend) quickSendCampaignSelect.value = currQuickSend;
    if (contactsCampaignSelect && currContacts) contactsCampaignSelect.value = currContacts;
}

async function loadTemplates() {
    const res = await fetch('/api/templates');
    const templates = await res.json();
    
    const select = document.getElementById('send-template');
    if(select) select.innerHTML = '<option value="">Select template...</option>';
    
    const sidebar = document.getElementById('template-list-sidebar');
    if(sidebar) sidebar.innerHTML = '';
    
    const campTemplateSelect = document.getElementById('new-campaign-template');
    if(campTemplateSelect) campTemplateSelect.innerHTML = '<option value="">Select template...</option>';
    
    const testTemplateSelect = document.getElementById('test-template');
    if(testTemplateSelect) testTemplateSelect.innerHTML = '<option value="">Select template...</option>';
    
    templates.forEach(t => {
        if(campTemplateSelect) {
            const opt = document.createElement('option');
            opt.value = t;
            opt.innerText = t;
            campTemplateSelect.appendChild(opt);
        }
        
        if(testTemplateSelect) {
            const opt = document.createElement('option');
            opt.value = t;
            opt.innerText = t;
            testTemplateSelect.appendChild(opt);
        }
        
        // Dropdown
        if(select) {
            const opt = document.createElement('option');
            opt.value = t;
            opt.innerText = t;
            select.appendChild(opt);
        }
        
        if(sidebar) {
            // Sidebar button
            const btn = document.createElement('button');
            btn.innerText = t;
            btn.style.background = 'rgba(255,255,255,0.05)';
            btn.style.border = '1px solid var(--border)';
            btn.style.color = 'var(--text)';
            btn.style.textAlign = 'left';
            btn.onclick = () => viewTemplate(t);
            sidebar.appendChild(btn);
        }
    });
}

async function viewTemplate(name) {
    const res = await fetch(`/api/templates/${encodeURIComponent(name)}`);
    if (res.ok) {
        const data = await res.json();
        document.getElementById('active-template-name').value = name;
        document.getElementById('active-template-name').disabled = true;
        document.getElementById('active-template-content').value = data.content;
    } else {
        showToast("Failed to load template", 'info');
    }
}

function newTemplate() {
    document.getElementById('active-template-name').value = "";
    document.getElementById('active-template-name').disabled = false;
    document.getElementById('active-template-content').value = "Subject: Hello from {company_name}\n\nHi {company_name},\n\n...";
    document.getElementById('active-template-name').focus();
}

async function saveActiveTemplate() {
    const name = document.getElementById('active-template-name').value.trim();
    const content = document.getElementById('active-template-content').value;
    if (!name) {
        showToast("Please enter a template name", 'info');
        return;
    }
    
    const res = await fetch(`/api/templates/${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content})
    });
    
    if (res.ok) {
        showToast("Template saved!", 'info');
        loadTemplates();
        document.getElementById('active-template-name').disabled = true;
    } else {
        showToast("Failed to save template", 'info');
    }
}

async function deleteActiveTemplate() {
    const name = document.getElementById('active-template-name').value.trim();
    if (!name) return;
    
    if (!(await showConfirm(`Delete template '${name}'?`))) return;
    
    const res = await fetch(`/api/templates/${encodeURIComponent(name)}`, {
        method: 'DELETE'
    });
    
    if (res.ok) {
        document.getElementById('active-template-name').value = "";
        document.getElementById('active-template-name').disabled = true;
        document.getElementById('active-template-content').value = "";
        loadTemplates();
    } else {
        showToast("Failed to delete template", 'info');
    }
}

async function generateWithAi() {
    if (!document.getElementById('active-template-name').value) {
        showToast("Please create a new template first.", 'info');
        return;
    }
    
    const context = document.getElementById('ai-prompt-input').value.trim();
    if (!context) {
        showToast("Please enter what the email should be about.", 'info');
        return;
    }

    const prevText = document.getElementById('active-template-content').value;
    document.getElementById('active-template-content').value = "Generating with AI... Please wait...";
    document.getElementById('btn-generate-ai').disabled = true;
    
    try {
        const res = await fetch('/api/generate_template', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ context: context })
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            document.getElementById('active-template-content').value = data.content;
        } else {
            showToast(data.detail || "Generation failed.", 'info');
            document.getElementById('active-template-content').value = prevText;
        }
    } catch (e) {
        showToast("Error contacting server.", 'info');
        document.getElementById('active-template-content').value = prevText;
    } finally {
        document.getElementById('btn-generate-ai').disabled = false;
    }
}

async function loadQueries() {
    const res = await fetch('/api/queries');
    const queries = await res.json();
    const tbody = document.getElementById('queries-tbody');
    tbody.innerHTML = '';
    
    if (queries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;">No queries configured.</td></tr>';
        return;
    }

    queries.forEach(q => {
        const tr = document.createElement('tr');
        const escapedQ = escapeHtml(q);
        tr.innerHTML = `
            <td><input type="checkbox" class="query-cb" value="${escapedQ.replace(/"/g, '&quot;')}"></td>
            <td>${escapedQ}</td>
            <td>
                <button style="background:transparent; border:1px solid var(--primary); color:var(--primary); padding:0.25rem 0.5rem; margin-right:0.25rem; font-size:1rem;" title="Edit" onclick="editQuery('${escapedQ.replace(/'/g, "\\'")}')">✏️</button>
                <button style="background:transparent; border:1px solid #ef4444; color:#ef4444; padding:0.25rem 0.5rem; font-size:1rem;" title="Delete" onclick="deleteQuery('${escapedQ.replace(/'/g, "\\'")}')">🗑️</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function addQuery() {
    const query = document.getElementById('new-query').value.trim();
    if (!query) return;
    
    await fetch('/api/queries', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query})
    });
    
    document.getElementById('new-query').value = '';
    loadQueries();
}

async function deleteQuery(query) {
    if (!(await showConfirm(`Delete query: "${query}"?`))) return;
    
    await fetch('/api/queries', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query})
    });
    
    loadQueries();
}

async function editQuery(oldQuery) {
    const newQuery = (await showPrompt("Edit query target:", oldQuery));
    if (!newQuery || newQuery.trim() === oldQuery) return;
    
    await fetch('/api/queries', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({old_query: oldQuery, new_query: newQuery.trim()})
    });
    loadQueries();
}

async function loadQueryHistory() {
    const res = await fetch('/api/query_history');
    const history = await res.json();
    const tbody = document.getElementById('history-tbody');
    tbody.innerHTML = '';
    
    if (history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;">No history recorded yet.</td></tr>';
        return;
    }

    history.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="white-space:nowrap; color:var(--text-muted);">${row.executed_at_utc.substring(0, 19).replace('T', ' ')}</td>
            <td>${escapeHtml(row.query)}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadProspects() {
    let url = '/api/prospects?status=pending_review';
    const dateFrom = document.getElementById('pending-date-from');
    const dateTo = document.getElementById('pending-date-to');
    if (dateFrom && dateFrom.value) url += `&date_from=${dateFrom.value}`;
    if (dateTo && dateTo.value) url += `&date_to=${dateTo.value}`;
    
    const res = await fetch(url);
    const data = await res.json();
    const tbody = document.getElementById('prospects-tbody');
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">No pending prospects found.</td></tr>';
        return;
    }

    data.forEach(p => {
        const tr = document.createElement('tr');
        const safeCompany = p.company_name ? escapeHtml(p.company_name).replace(/'/g, "\\'") : '';
        
        // Format Quality Badges
        let qBadge = `<span class="badge badge-neutral">${p.qualification_status || 'UNKNOWN'}</span>`;
        if (p.qualification_status === 'QUALIFIED') qBadge = `<span class="badge badge-success">QUALIFIED</span>`;
        else if (p.qualification_status === 'UNQUALIFIED') qBadge = `<span class="badge badge-danger">UNQUALIFIED</span>`;
        
        let eBadge = `<span class="badge badge-neutral">${p.email_quality || 'UNKNOWN'}</span>`;
        if (p.email_quality === 'VALID' || p.email_quality === 'LIKELY_VALID') eBadge = `<span class="badge badge-success">${p.email_quality}</span>`;
        else if (p.email_quality === 'ROLE_BASED' || p.email_quality === 'LOW_CONFIDENCE') eBadge = `<span class="badge badge-warning">${p.email_quality}</span>`;
        else if (p.email_quality === 'INVALID' || p.email_quality === 'SUPPRESSED') eBadge = `<span class="badge badge-danger">${p.email_quality}</span>`;

        tr.innerHTML = `
            <td><input type="checkbox" class="prospect-cb" value="${p.id}"></td>
            <td>${p.id}</td>
            <td style="cursor:pointer;" onclick="editCompany(${p.id}, '${safeCompany}')">${escapeHtml(p.company_name ?? '')} <span style="font-size:0.8rem; color:var(--text-muted)">✏️</span></td>
            <td>${p.business_email}</td>
            <td><a href="${p.target_url}" target="_blank" style="color:var(--primary)">Link</a></td>
            <td>${p.relevance_score != null ? p.relevance_score : '-'}</td>
            <td>${eBadge}</td>
            <td>${qBadge}</td>
            <td style="display:flex; gap:0.5rem; justify-content:center;">
                <button style="background:transparent; border:1px solid var(--border); color:var(--text); padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="viewEvidence(${p.id})">View Evidence</button>
                <button style="background:transparent; border:none; color:#ef4444; font-size:1.1rem; padding:0;" title="Reject this email" onclick="rejectSingle(${p.id})">🗑️</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadApproved() {
    let url = '/api/prospects?status=approved';
    const dateFrom = document.getElementById('approved-date-from');
    const dateTo = document.getElementById('approved-date-to');
    if (dateFrom && dateFrom.value) url += `&date_from=${dateFrom.value}`;
    if (dateTo && dateTo.value) url += `&date_to=${dateTo.value}`;
    
    const res = await fetch(url);
    const data = await res.json();
    const tbody = document.getElementById('approved-tbody');
    if(!tbody) return;
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No approved prospects ready to send.</td></tr>';
        return;
    }

    data.forEach(p => {
        const tr = document.createElement('tr');
        const safeCompany = p.company_name ? escapeHtml(p.company_name).replace(/'/g, "\\'") : '';
        const safeCampaign = p.campaign ? escapeHtml(p.campaign).replace(/'/g, "\\'") : '';
        tr.innerHTML = `
            <td>${p.id}</td>
            <td style="cursor:pointer;" onclick="editCompany(${p.id}, '${safeCompany}')">${escapeHtml(p.company_name ?? '')} <span style="font-size:0.8rem; color:var(--text-muted)">✏️</span></td>
            <td>${p.business_email}</td>
            <td style="cursor:pointer;" onclick="editCampaign(${p.id}, '${safeCampaign}')">${escapeHtml(p.campaign ?? '')} <span style="font-size:0.8rem; color:var(--text-muted)">✏️</span></td>
            <td>${p.reason_for_contact || ''}</td>
            <td>
                <button style="background:transparent; border:none; color:#ef4444; font-size:1.1rem;" title="Reject this email" onclick="rejectSingle(${p.id})">🗑️</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function editCampaign(id, currentCampaign) {
    const res = await fetch('/api/status');
    const data = await res.json();
    const campaigns = data.campaigns || [];
    
    // Create a custom modal for the dropdown
    const dialog = document.createElement('dialog');
    dialog.style.padding = '1.5rem';
    dialog.style.borderRadius = '8px';
    dialog.style.border = '1px solid var(--border)';
    dialog.style.background = 'var(--bg-secondary)';
    dialog.style.color = 'var(--text)';
    dialog.style.margin = 'auto';
    dialog.style.position = 'fixed';
    dialog.style.top = '50%';
    dialog.style.left = '50%';
    dialog.style.transform = 'translate(-50%, -50%)';
    
    let optionsHtml = '<option value="">(Create new or leave empty)</option>';
    campaigns.forEach(c => {
        optionsHtml += `<option value="${c}" ${c === currentCampaign ? 'selected' : ''}>${c}</option>`;
    });

    dialog.innerHTML = `
        <h3 style="margin-top:0;">Edit Campaign</h3>
        <select id="edit-campaign-select" style="width:100%; padding:0.5rem; margin-bottom:1rem;">
            ${optionsHtml}
        </select>
        <div style="display:flex; gap:0.5rem; justify-content:flex-end;">
            <button id="btn-edit-cancel" style="background:transparent; border:1px solid var(--border); padding:0.5rem 1rem;">Cancel</button>
            <button id="btn-edit-save" style="background:var(--primary); color:black; padding:0.5rem 1rem;">Save</button>
        </div>
    `;
    
    document.body.appendChild(dialog);
    dialog.showModal();
    
    document.getElementById('btn-edit-cancel').onclick = () => {
        dialog.close();
        dialog.remove();
    };
    
    document.getElementById('btn-edit-save').onclick = async () => {
        const newCampaign = document.getElementById('edit-campaign-select').value;
        if (newCampaign && newCampaign !== currentCampaign) {
            await fetch('/api/prospects/update_campaign', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: id, campaign: newCampaign})
            });
            refreshAll();
        }
        dialog.close();
        dialog.remove();
    };
}

async function editCompany(id, currentName) {
    const newName = (await showPrompt("Edit company name:", currentName));
    if (newName !== null && newName !== currentName) {
        await fetch('/api/prospects/update_company', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id: id, company_name: newName})
        });
        refreshAll();
    }
}

async function loadRejected() {
    const res = await fetch('/api/prospects?status=rejected');
    const data = await res.json();
    const tbody = document.getElementById('rejected-tbody');
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No rejected leads.</td></tr>';
        return;
    }

    data.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${p.id}</td>
            <td>${p.company_name}</td>
            <td>${p.business_email}</td>
            <td><a href="${p.target_url}" target="_blank" style="color:var(--primary)">Link</a></td>
            <td>${p.campaign}</td>
            <td>
                <button style="background:transparent; border:1px solid #10b981; color:#10b981; border-radius:4px; padding:0.25rem 0.5rem; cursor:pointer;" onclick="restoreSingle(${p.id})">Restore</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function restoreSingle(id) {
    await fetch('/api/restore', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id})
    });
    refreshAll();
}

async function rejectSingle(id) {
    if (!(await showConfirm("Are you sure you want to reject this email?"))) return;
    await fetch('/api/reject_selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids: [id]})
    });
    refreshAll();
}

async function rejectSelected() {
    const checkboxes = document.querySelectorAll('.prospect-cb:checked');
    const ids = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (ids.length === 0) {
        showToast("Please select at least one email to reject.", 'info');
        return;
    }
    
    if (!(await showConfirm(`Are you sure you want to reject ${ids.length} emails? They will be permanently hidden.`))) return;
    
    await fetch('/api/reject_selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids})
    });
    
    document.getElementById('selectAllCheckbox').checked = false;
    refreshAll();
}

function toggleSelectAll() {
    const isChecked = document.getElementById('selectAllCheckbox').checked;
    document.querySelectorAll('.prospect-cb').forEach(cb => cb.checked = isChecked);
}

async function loadCampaignsTab() {
    const res = await fetch('/api/campaigns');
    const data = await res.json();
    const tbody = document.getElementById('campaigns-tbody');
    if(!tbody) return;
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No campaigns created yet.</td></tr>';
        return;
    }
    
    data.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${escapeHtml(c.name)}</strong></td>
            <td>${escapeHtml(c.template)}</td>
            <td>${c.created_at_utc.substring(0, 19).replace('T', ' ')}</td>
            <td>
                <button style="background:transparent; border:none; color:#ef4444; font-size:1.1rem; cursor:pointer;" onclick="deleteCampaign('${escapeHtml(c.name)}')">🗑️</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function addCampaign() {
    const name = document.getElementById('new-campaign-name').value.trim();
    const template = document.getElementById('new-campaign-template').value;
    
    if (!name || !template) {
        showToast("Please provide both a name and a template.", 'info');
        return;
    }
    
    const res = await fetch('/api/campaigns', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, template})
    });
    
    if (res.ok) {
        document.getElementById('new-campaign-name').value = '';
        document.getElementById('new-campaign-template').value = '';
        refreshAll();
    } else {
        const err = await res.json();
        showToast(err.detail || "Failed to create campaign", 'info');
    }
}

async function deleteCampaign(name) {
    if (!(await showConfirm(`Delete campaign '${name}'? This won't delete the emails, just the campaign configuration.`))) return;
    await fetch(`/api/campaigns/${encodeURIComponent(name)}`, { method: 'DELETE' });
    refreshAll();
}

async function addManualLead() {
    const email = document.getElementById('manual-lead-email').value;
    const company = document.getElementById('manual-lead-company').value;
    const campaign = document.getElementById('manual-lead-campaign').value;
    
    if (!email || !company) {
        showToast("Please enter both Email and Company Name.", 'info');
        return;
    }
    
    const btn = document.getElementById('btn-manual-add');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Adding...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/prospects/manual_add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email: email, company_name: company, campaign: campaign })
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            document.getElementById('manual-lead-email').value = '';
            document.getElementById('manual-lead-company').value = '';
            loadProspects();
            showToast("Lead added successfully!", 'info');
        } else {
            showToast(`Error: ${data.error || data.detail || 'Unknown error'}`, 'info');
        }
    } catch (err) {
        showToast("Failed to add lead: " + err.message, 'info');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function importCsv() {
    const fileInput = document.getElementById('csv-upload-file');
    const campaign = document.getElementById('csv-upload-campaign').value;
    
    if (!fileInput.files.length) {
        showToast("Please select a CSV file to upload.", 'info');
        return;
    }
    if (!campaign) {
        showToast("Please select a target campaign for these leads.", 'info');
        return;
    }
    
    const file = fileInput.files[0];
    const reader = new FileReader();
    
    reader.onload = async function(e) {
        const csvContent = e.target.result;
        const btn = document.getElementById('btn-import-csv');
        btn.disabled = true;
        btn.textContent = "Importing...";
        
        try {
            const res = await fetch('/api/import_csv', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ campaign: campaign, csv_content: csvContent })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Import complete! Added: ${data.added}, Skipped/Duplicates: ${data.skipped}`, 'info');
                fileInput.value = '';
                loadProspects();
            } else {
                showToast(`Error: ${data.error}`, 'info');
            }
        } catch (err) {
            showToast(`Upload failed: ${err.message || err}\nMake sure the CSV is not too large and has valid UTF-8 encoding.`, 'info');
            console.error("CSV Import Error:", err);
        } finally {
            btn.disabled = false;
            btn.textContent = "Upload & Import";
        }
    };
    reader.readAsText(file);
}

async function approveSelected() {
    const checkboxes = document.querySelectorAll('.prospect-cb:checked');
    const ids = Array.from(checkboxes).map(cb => parseInt(cb.value));
    const targetCampaign = document.getElementById('target-campaign').value.trim();
    
    if (ids.length === 0) {
        showToast("Please select at least one email.", 'info');
        return;
    }
    if (!targetCampaign) {
        showToast("Please select a Target Campaign name.", 'info');
        return;
    }
    
    const reason = (await showPrompt(`Approving ${ids.length} emails for campaign '${targetCampaign}'. Enter reason:`, "Manually selected via Dashboard"));
    if (!reason) return;
    
    await fetch('/api/approve_selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids, campaign: targetCampaign, reason})
    });
    
    document.getElementById('selectAllCheckbox').checked = false;
    document.getElementById('target-campaign').value = "";
    refreshAll();
}

async function loadArchive() {
    let url = '/api/archive?t=' + Date.now();
    const dateFrom = document.getElementById('archive-date-from');
    const dateTo = document.getElementById('archive-date-to');
    if (dateFrom && dateFrom.value) url += `&date_from=${dateFrom.value}`;
    if (dateTo && dateTo.value) url += `&date_to=${dateTo.value}`;
    
    const res = await fetch(url);
    const data = await res.json();
    const tbody = document.getElementById('archive-tbody');
    const countSpan = document.getElementById('archive-count');
    tbody.innerHTML = '';
    
    if (countSpan) countSpan.textContent = `(${data.length} total)`;
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No emails sent yet.</td></tr>';
        return;
    }

    data.forEach(row => {
        const tr = document.createElement('tr');
        
        // We only allow follow-ups for leads that are in 'sent' state (not replied, unsubbed, etc)
        let checkboxHtml = '';
        if (row.prospect_status === 'sent' && row.prospect_id) {
            checkboxHtml = `<input type="checkbox" class="archive-checkbox" value="${row.prospect_id}" onchange="updateArchiveRequeueButton()">`;
        }
        
        let statusHtml = '';
        if (row.prospect_status === 'replied') {
            statusHtml = '<span style="background:#10b981; color:white; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.75rem; font-weight:bold;">Replied</span>';
        } else if (row.prospect_status === 'auto_reply') {
            statusHtml = '<span style="background:#f59e0b; color:white; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.75rem; font-weight:bold;">Auto-Reply</span>';
        } else if (row.prospect_status === 'unsubscribed') {
            statusHtml = '<span style="background:#ef4444; color:white; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.75rem; font-weight:bold;">Unsubscribed</span>';
        } else if (row.prospect_status === 'sent') {
            statusHtml = '<span style="background:rgba(255,255,255,0.2); color:white; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.75rem;">Sent</span>';
        }
        
        let actionHtml = '';
        if (row.prospect_id && row.prospect_status === 'sent') {
            actionHtml = `
                <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
                    <button style="background:transparent; border:1px solid #10b981; color:#10b981; padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="markReplied(${row.prospect_id})">✅ Replied</button>
                    <button style="background:transparent; border:1px solid #ef4444; color:#ef4444; padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="markUnsubscribed(${row.prospect_id})">❌ Unsub</button>
                </div>
            `;
        }

        tr.innerHTML = `
            <td>${checkboxHtml}</td>
            <td style="white-space:nowrap">${row.sent_at_utc.substring(0, 19).replace('T', ' ')}</td>
            <td>${row.business_email}</td>
            <td>${row.campaign}</td>
            <td><div class="archive-text">${escapeHtml(row.message_text)}</div></td>
            <td style="white-space:nowrap">${statusHtml}${actionHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function approveSingle(id) {
    const reason = (await showPrompt("Enter factual reason for approval:", "Identified via OSINT market research"));
    if (!reason) return;
    
    await fetch('/api/approve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id, reason})
    });
    
    refreshAll();
}

async function approveAll() {
    const campaign = document.getElementById('campaign-select').value;
    if (!campaign) {
        showToast("Please select a campaign first!", 'info');
        return;
    }
    
    const reason = (await showPrompt(`Approving all for '${campaign}'. Enter reason:`, "Identified via OSINT market research for LeadPilot Pro"));
    if (!reason) return;
    
    await fetch('/api/approve_all', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({campaign, reason})
    });
    
    refreshAll();
}

function toggleSelectAllQueries() {
    const isChecked = document.getElementById('selectAllQueries').checked;
    document.querySelectorAll('.query-cb').forEach(cb => cb.checked = isChecked);
}

async function startResearch() {
    const checkboxes = document.querySelectorAll('.query-cb:checked');
    const selectedQueries = Array.from(checkboxes).map(cb => cb.value);
    
    if (selectedQueries.length === 0) {
        showToast("Please select at least one query to run.", 'info');
        return;
    }

    if(!(await showConfirm(`Start background OSINT research for ${selectedQueries.length} selected queries? This may take several minutes.`))) return;
    
    const res = await fetch('/api/research', { 
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ queries: selectedQueries })
    });
    const data = await res.json();
    showToast(data.message, 'info');
}

let sendLogPollInterval = null;
let researchLogPollInterval = null;

async function pollSendLogs() {
    try {
        const res = await fetch('/api/send_logs?t=' + Date.now());
        if (!res.ok) return;
        const data = await res.json();
        const terminal = document.getElementById('send-logs-terminal');
        if (terminal && data.logs) {
            terminal.textContent = data.logs;
            terminal.scrollTop = terminal.scrollHeight;
        }
    } catch (e) {
        console.error("Error polling send logs:", e);
    }
}

async function pollResearchLogs() {
    try {
        const res = await fetch('/api/research_logs?t=' + Date.now());
        if (!res.ok) return;
        const data = await res.json();
        const terminal = document.getElementById('research-logs-terminal');
        if (terminal && data.logs) {
            terminal.textContent = data.logs;
            terminal.scrollTop = terminal.scrollHeight;
            
            // Refresh query history to show newly executing queries
            loadQueryHistory();
        }
    } catch (e) {
        console.error("Error polling research logs:", e);
    }
}

function downloadLogs(logType) {
    window.open(`/api/download_log/${logType}`, '_blank');
}

async function sendCampaign() {
    const campaign = document.getElementById('send-campaign').value;
    const limit = parseInt(document.getElementById('send-limit').value);
    const scheduleInput = document.getElementById('send-schedule').value;
    
    if (!campaign || isNaN(limit)) {
        showToast("Please fill in all fields.", 'info');
        return;
    }
    
    let scheduled_at = null;
    let confirmMsg = `Are you sure you want to send up to ${limit} emails for campaign '${campaign}'?`;
    
    if (scheduleInput) {
        // Convert local time to UTC string
        const localDate = new Date(scheduleInput);
        scheduled_at = localDate.toISOString();
        confirmMsg = `Are you sure you want to schedule up to ${limit} emails for campaign '${campaign}' at ${localDate.toLocaleString()}?`;
    }
    
    if(!(await showConfirm(confirmMsg))) return;
    
    const btn = document.getElementById('btn-send-campaign');
    btn.disabled = true;
    
    if (scheduled_at) {
        btn.textContent = "SCHEDULED ⏰";
        document.getElementById('send-logs-terminal').textContent = `Campaign scheduled to start at: ${new Date(scheduleInput).toLocaleString()}\nLogs will appear here once it starts running.`;
    } else {
        btn.textContent = "SENDING IN BACKGROUND...";
        if(sendLogPollInterval) clearInterval(sendLogPollInterval);
        document.getElementById('send-logs-terminal').textContent = "Initializing campaign sending in background...\n";
        sendLogPollInterval = setInterval(pollSendLogs, 2000);
    }
    
    const payload = {campaign, limit};
    if (scheduled_at) payload.scheduled_at = scheduled_at;
    
    const res = await fetch('/api/send', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    if (!res.ok || !data.success) {
        showToast(data.detail || data.message || "Failed to start campaign.", 'info');
        if(sendLogPollInterval) clearInterval(sendLogPollInterval);
        document.getElementById('send-logs-terminal').textContent = "";
        btn.disabled = false;
        btn.textContent = "🚀 SEND CAMPAIGN";
        return;
    }
    
    setTimeout(() => {
        btn.disabled = false;
        btn.textContent = "🚀 SEND CAMPAIGN";
    }, 5000);
}

function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    // Prefisso (^=) e null-check: una voce di menu con onclick piu' lungo non deve far crollare il cambio tab
    const navTab = document.querySelector(`.tab[onclick^="switchTab('${tabId}')"]`);
    if (navTab) navTab.classList.add('active');
    
    document.getElementById('tab-overview').classList.add('hidden');
    document.getElementById('tab-research').classList.add('hidden');
    document.getElementById('tab-sales_campaigns').classList.add('hidden');
    document.getElementById('tab-campaigns').classList.add('hidden');
    document.getElementById('tab-pending').classList.add('hidden');
    document.getElementById('tab-approved').classList.add('hidden');
    document.getElementById('tab-rejected').classList.add('hidden');
    document.getElementById('tab-send').classList.add('hidden');
    document.getElementById('tab-quicksend').classList.add('hidden');
    document.getElementById('tab-templates').classList.add('hidden');
    document.getElementById('tab-archive').classList.add('hidden');
    document.getElementById('tab-settings').classList.add('hidden');
    document.getElementById('tab-research_campaigns').classList.add('hidden');
    document.getElementById('tab-query_studio').classList.add('hidden');
    document.getElementById('tab-leads').classList.add('hidden');
    document.getElementById('tab-companies').classList.add('hidden');
    document.getElementById('tab-analytics').classList.add('hidden');
    document.getElementById('tab-providers').classList.add('hidden');
    const productsTab = document.getElementById('tab-products');
    if (productsTab) productsTab.classList.add('hidden');
    
    const orchestratorTab = document.getElementById('tab-orchestrator');
    if (orchestratorTab) orchestratorTab.style.display = 'none';
    
    document.getElementById(`tab-${tabId}`).classList.remove('hidden');
    
    if (tabId === 'research') {
        fetchLushaCredits();
    }
    if (tabId === 'sales_campaigns' && typeof loadSalesCampaignsTab === 'function') {
        loadSalesCampaignsTab();
    }
    if (tabId === 'orchestrator' && typeof initOrchestratorTab === 'function') {
        if (orchestratorTab) orchestratorTab.style.display = 'block';
        initOrchestratorTab();
    }
    if (tabId === 'quicksend' && typeof loadContactsTab === 'function') {
        loadContactsTab();
    }
    if (tabId === 'products' && typeof initProductsTab === 'function') {
        initProductsTab();
    }
    
    if (sendLogPollInterval) clearInterval(sendLogPollInterval);
    if (researchLogPollInterval) clearInterval(researchLogPollInterval);
    
    if (tabId === 'send') {
        pollSendLogs();
        sendLogPollInterval = setInterval(pollSendLogs, 2000);
    } else if (tabId === 'research') {
        pollResearchLogs();
        researchLogPollInterval = setInterval(pollResearchLogs, 2000);
        loadQueryHistory();
        loadQueries();
    }
    
    if (tabId === 'archive') loadArchive();
    else if (tabId === 'pending') loadProspects();
    else if (tabId === 'approved') loadApproved();
    else if (tabId === 'rejected') loadRejected();
    else if (tabId === 'campaigns') loadCampaignsTab();
    else if (tabId === 'templates') loadTemplates();
    else if (tabId === 'overview') { loadStatus(); loadChart(); }
    else if (tabId === 'research_campaigns') { if (typeof loadCampaignsList === 'function') loadCampaignsList(); }
    else if (tabId === 'query_studio') { if (typeof loadQueryStudioDropdown === 'function') loadQueryStudioDropdown(); }
    else if (tabId === 'companies') { if (typeof loadCompanies === 'function') loadCompanies(); }
    else if (tabId === 'leads') { if (typeof loadLeads === 'function') loadLeads(); }
    else if (tabId === 'analytics') { if (typeof loadAnalytics === 'function') loadAnalytics(); }
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function refreshAll() {
    loadStatus().catch(e => console.error("Error loading status:", e));
    loadProspects().catch(e => console.error("Error loading prospects:", e));
    loadApproved().catch(e => console.error("Error loading approved:", e));
    loadRejected().catch(e => console.error("Error loading rejected:", e));
    loadArchive().catch(e => console.error("Error loading archive:", e));
    loadTemplates().catch(e => console.error("Error loading templates:", e));
    loadCampaignsTab().catch(e => console.error("Error loading campaigns:", e));
    loadQueries().catch(e => {
        console.error("Error loading queries:", e);
        const tbody = document.getElementById('queries-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#ef4444;">Connection error. Please restart the backend server.</td></tr>';
    });
    loadQueryHistory().catch(e => console.error("Error loading history:", e));
    loadSettings().catch(e => console.error("Error loading settings:", e));
    loadChart().catch(e => console.error("Error loading chart:", e));
}

let sentChartInstance = null;
async function loadChart() {
    const res = await fetch('/api/chart_data');
    if (!res.ok) return;
    const data = await res.json();
    
    const ctx = document.getElementById('sentChart').getContext('2d');
    if (sentChartInstance) {
        sentChartInstance.destroy();
    }
    
    sentChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [{
                label: 'Emails Sent',
                data: data.counts,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.2)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#e2e8f0' }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                y: {
                    ticks: { color: '#94a3b8', stepSize: 1 },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    beginAtZero: true
                }
            }
        }
    });
}

// Init
switchTab('overview');
refreshAll();
setInterval(loadStatus, 5000); // Poll status

async function logout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.reload();
}

async function loadSettings() {
    const res = await fetch('/api/settings');
    const data = await res.json();
    document.getElementById('smtp-host').value = data.smtp_host || '';
    document.getElementById('smtp-port').value = data.smtp_port || '';
    document.getElementById('smtp-user').value = data.smtp_user || '';
    document.getElementById('smtp-pass').value = data.smtp_password || '';
    document.getElementById('smtp-from').value = data.smtp_from_email || '';
    if(document.getElementById('imap-host')) document.getElementById('imap-host').value = data.imap_host || '';
    if(document.getElementById('imap-port')) document.getElementById('imap-port').value = data.imap_port || '993';
    document.getElementById('company-name').value = data.company_name || '';
    document.getElementById('company-website').value = data.company_website || '';
    document.getElementById('daily-limit').value = data.daily_limit || '250';
    document.getElementById('delay-min').value = data.delay_minimum || '300';
    document.getElementById('delay-max').value = data.delay_maximum || '900';
    
    document.getElementById('ai-api-key').value = data.ai_api_key || '';
    document.getElementById('ai-base-url').value = data.ai_base_url || 'https://api.openai.com/v1';
    document.getElementById('ai-model').value = data.ai_model || 'gpt-4o';
    
    if (document.getElementById('lusha-api-key')) {
        document.getElementById('lusha-api-key').value = data.lusha_api_key || '';
    }
    
    if (document.getElementById('ddg-enabled')) document.getElementById('ddg-enabled').checked = (data.ddg_enabled !== 'false');
    if (document.getElementById('searxng-enabled')) document.getElementById('searxng-enabled').checked = (data.searxng_enabled !== 'false');
    if (document.getElementById('searxng-url')) document.getElementById('searxng-url').value = data.searxng_url || 'http://localhost:8080';
    if (document.getElementById('brave-enabled')) document.getElementById('brave-enabled').checked = (data.brave_enabled !== 'false');
    if (document.getElementById('brave-api-key')) document.getElementById('brave-api-key').value = data.brave_api_key || '';
    
    // Enable AI generation UI if API key is set
    const aiPromptInput = document.getElementById('ai-prompt-input');
    const btnGenerateAi = document.getElementById('btn-generate-ai');
    if (data.ai_api_key) {
        aiPromptInput.disabled = false;
        btnGenerateAi.disabled = false;
        btnGenerateAi.style.cursor = 'pointer';
        btnGenerateAi.style.opacity = '1';
    } else {
        aiPromptInput.disabled = true;
        btnGenerateAi.disabled = true;
        btnGenerateAi.style.cursor = 'not-allowed';
        btnGenerateAi.style.opacity = '0.5';
    }
}

async function testSmtp(e) {
    e.preventDefault();
    const email = document.getElementById('test-email').value;
    const template = document.getElementById('test-template').value;
    const logBox = document.getElementById('smtp-log');
    const btn = document.getElementById('test-smtp-btn');
    
    btn.disabled = true;
    btn.innerText = "Testing...";
    logBox.innerText = `Sending test email to ${email} using template '${template}'...\n`;
    
    try {
        const res = await fetch('/api/test_smtp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, template})
        });
        
        const data = await res.json();
        logBox.innerText += data.log;
    } catch (err) {
        logBox.innerText += `\nError: ${err}`;
    } finally {
        btn.disabled = false;
        btn.innerText = "Send Test Email";
    }
}

async function saveSettings(e) {
    e.preventDefault();
    const payload = {
        smtp_host: document.getElementById('smtp-host').value,
        smtp_port: document.getElementById('smtp-port').value,
        smtp_user: document.getElementById('smtp-user').value,
        smtp_password: document.getElementById('smtp-pass').value,
        smtp_from_email: document.getElementById('smtp-from').value,
        company_name: document.getElementById('company-name').value,
        company_website: document.getElementById('company-website').value,
        daily_limit: document.getElementById('daily-limit').value,
        delay_minimum: document.getElementById('delay-min').value,
        delay_maximum: document.getElementById('delay-max').value,
        ai_api_key: document.getElementById('ai-api-key').value,
        ai_base_url: document.getElementById('ai-base-url').value,
        ai_model: document.getElementById('ai-model').value,
        lusha_api_key: document.getElementById('lusha-api-key') ? document.getElementById('lusha-api-key').value : "",
        imap_host: document.getElementById('imap-host') ? document.getElementById('imap-host').value : "",
        imap_port: document.getElementById('imap-port') ? document.getElementById('imap-port').value : "993",
        ddg_enabled: document.getElementById('ddg-enabled') && document.getElementById('ddg-enabled').checked ? "true" : "false",
        searxng_enabled: document.getElementById('searxng-enabled') && document.getElementById('searxng-enabled').checked ? "true" : "false",
        searxng_url: document.getElementById('searxng-url') ? document.getElementById('searxng-url').value : "",
        brave_enabled: document.getElementById('brave-enabled') && document.getElementById('brave-enabled').checked ? "true" : "false",
        brave_api_key: document.getElementById('brave-api-key') ? document.getElementById('brave-api-key').value : ""
    };
    
    const res = await fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    
    if (res.ok) showToast("Settings saved successfully", 'info');
    else showToast("Failed to save settings", 'info');
}

async function searchLusha() {
    const domain = document.getElementById('lusha-domain').value;
    const role = document.getElementById('lusha-role').value;
    const limit = document.getElementById('lusha-limit').value;
    
    if (!domain || !role) {
        showToast("Please provide both a Target Domain and a Job Title/Seniority.", 'info');
        return;
    }
    
    const btn = document.getElementById('lusha-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Searching...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/lusha/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                domain: domain,
                role: role,
                limit: parseInt(limit, 10) || 10
            })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(`Lusha Search Complete!\nAdded: ${data.added}\nSkipped (duplicates/no email, 'info'): ${data.skipped}`);
            refreshAll();
        } else {
            showToast("Error: " + (data.detail || "Unknown error", 'info'));
        }
    } catch (e) {
        showToast("Failed to connect to backend", 'info');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function fetchLushaCredits() {
    const badge = document.getElementById('lusha-credits-badge');
    if (!badge) return;
    
    badge.innerHTML = '💳 Lusha Credits: Fetching...';
    try {
        const res = await fetch('/api/lusha/credits');
        const json = await res.json();
        
        if (json.status === 'success' && json.data) {
            // Parse Lusha credits. E.g. usage for current period.
            // Based on Lusha API structure for account/usage, it might have a complex structure.
            // Let's just dump it safely or show 'Available' if we can't parse it deeply.
            // Often there's a field like `credits` or `usage`.
            let text = '💳 Lusha API Active';
            badge.innerHTML = text;
            badge.title = JSON.stringify(json.data, null, 2);
        } else {
            badge.innerHTML = '💳 Lusha Error: ' + (json.message || 'Unknown');
        }
    } catch (e) {
        badge.innerHTML = '💳 Lusha Error';
    }
}

async function prospectLusha() {
    const country = document.getElementById('lusha-adv-country').value;
    const state = document.getElementById('lusha-adv-state').value;
    const industry = document.getElementById('lusha-adv-industry').value;
    const role = document.getElementById('lusha-adv-role').value;
    const limit = document.getElementById('lusha-adv-limit').value;
    
    if (!country && !state && !industry && !role) {
        showToast("Please provide at least one filter for the database prospect.", 'info');
        return;
    }
    
    const btn = document.getElementById('lusha-adv-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Prospecting...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/lusha/prospect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                country: country || null,
                state: state || null,
                industry: industry || null,
                role: role || null,
                limit: parseInt(limit, 10) || 10
            })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(`Lusha Prospecting Complete!\nAdded: ${data.added}\nSkipped (duplicates/no email, 'info'): ${data.skipped}`);
            refreshAll();
        } else {
            showToast("Error: " + (data.detail || "Unknown error", 'info'));
        }
    } catch (e) {
        showToast("Failed to connect to backend", 'info');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}


async function changePassword(e) {
    e.preventDefault();
    const old_password = document.getElementById('old-pass').value;
    const new_password = document.getElementById('new-pass').value;
    
    const res = await fetch('/api/change_password', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({old_password, new_password})
    });
    
    if (res.ok) {
        showToast("Password updated successfully", 'info');
        document.getElementById('password-form').reset();
    } else {
        const data = await res.json();
        showToast(data.detail || "Failed to update password", 'info');
    }
}

async function markReplied(prospectId) {
    if(!(await showConfirm("Segnare questo lead come 'Replied'?"))) return;
    const res = await fetch('/api/prospects/mark_replied', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prospect_id: prospectId})
    });
    if(res.ok) {
        loadArchive();
    } else {
        showToast("Errore durante l'aggiornamento.", 'info');
    }
}

async function markUnsubscribed(prospectId) {
    if(!(await showConfirm("Segnare questo lead come 'Unsubscribed'?"))) return;
    const res = await fetch('/api/prospects/mark_unsubscribed', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prospect_id: prospectId})
    });
    if(res.ok) {
        loadArchive();
    } else {
        showToast("Errore durante l'aggiornamento.", 'info');
    }
}

async function syncImap() {
    const btn = document.getElementById('btn-sync-imap');
    const originalText = btn.innerHTML;
    btn.innerHTML = '🔄 Syncing...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/imap/sync', { method: 'POST' });
        const data = await res.json();
        if(data.success) {
            showToast(data.message, 'info');
            loadArchive();
        } else {
            showToast("Sync Fallito: " + (data.error || "Errore sconosciuto", 'info'));
        }
    } catch(err) {
        showToast("Errore di rete durante il sync.", 'info');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

function toggleAllArchive(source) {
    const checkboxes = document.querySelectorAll('.archive-checkbox');
    checkboxes.forEach(cb => cb.checked = source.checked);
    updateArchiveRequeueButton();
}

function updateArchiveRequeueButton() {
    const anyChecked = document.querySelectorAll('.archive-checkbox:checked').length > 0;
    const btn = document.getElementById('btn-requeue');
    if (btn) btn.style.display = anyChecked ? 'inline-block' : 'none';
}

async function showRequeueModal() {
    const res = await fetch('/api/campaigns');
    const campaigns = await res.json();
    const select = document.getElementById('requeue-campaign-select');
    select.innerHTML = '<option value="">-- Select Campaign --</option>';
    campaigns.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.name;
        select.appendChild(opt);
    });
    document.getElementById('requeue-modal').style.display = 'flex';
}

function closeRequeueModal() {
    document.getElementById('requeue-modal').style.display = 'none';
}

async function executeRequeue(sendNow = false) {
    const select = document.getElementById('requeue-campaign-select');
    const campaignId = select.value;
    
    if (!campaignId) {
        showToast("Please select a campaign for the follow-up.", 'info');
        return;
    }
    
    const campaignName = select.options[select.selectedIndex].text;
    
    const checkboxes = document.querySelectorAll('.archive-checkbox:checked');
    const prospectIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (prospectIds.length === 0) return;
    
    const res = await fetch('/api/prospects/requeue', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ prospect_ids: prospectIds, campaign_id: parseInt(campaignId) })
    });
    
    if (res.ok) {
        if (sendNow) {
            // Trigger background send immediately
            const sendRes = await fetch('/api/send', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ campaign: campaignName, limit: prospectIds.length })
            });
            const sendData = await sendRes.json();
            if (sendRes.ok && sendData.success) {
                showToast("Leads queued and sending started immediately!", 'info');
                closeRequeueModal();
                switchTab('send'); // switch to send tab to see logs
            } else {
                showToast("Queued successfully, but failed to start send: " + (sendData.error || sendData.detail || "Unknown error", 'info'));
                closeRequeueModal();
                loadArchive();
            }
        } else {
            showToast("Leads successfully queued for follow-up!", 'info');
            closeRequeueModal();
            loadArchive();
        }
    } else {
        const data = await res.json();
        showToast("Error: " + (data.error || "Unknown error", 'info'));
    }
}

function exportTableToCSV(tbodyId, filename) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    
    // We will parse the table headers for the current tab
    // To do this reliably, we can go up to the <table> and find the <thead>
    const table = tbody.closest('table');
    let csv = [];
    
    // Extract headers
    const thead = table.querySelector('thead');
    if (thead) {
        const headers = Array.from(thead.querySelectorAll('th')).map(th => {
            // Remove checkboxes if any
            let clone = th.cloneNode(true);
            const input = clone.querySelector('input');
            if(input) input.remove();
            return '"' + clone.textContent.replace(/"/g, '""').trim() + '"';
        });
        // Remove empty headers (e.g. checkbox column)
        const cleanHeaders = headers.filter(h => h !== '""');
        csv.push(cleanHeaders.join(','));
    }
    
    // Extract rows
    const rows = tbody.querySelectorAll('tr');
    rows.forEach(tr => {
        // Skip loading/empty rows
        if (tr.querySelector('td[colspan]')) return;
        
        let rowData = [];
        Array.from(tr.querySelectorAll('td')).forEach(td => {
            // If there's a checkbox, skip it
            if (td.querySelector('input[type="checkbox"]')) return;
            
            // For email content, we might want to get innerText to strip HTML
            let text = td.innerText.replace(/"/g, '""').trim();
            rowData.push('"' + text + '"');
        });
        csv.push(rowData.join(','));
    });
    
    // Download
    const csvFile = new Blob([csv.join('\\n')], { type: 'text/csv' });
    const downloadLink = document.createElement("a");
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = "none";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

async function executeQuickSend() {
    const campaign = document.getElementById('quick-send-campaign-select').value;
    const rawData = document.getElementById('quick-send-data').value;
    
    if (!campaign) {
        showToast("Seleziona una campagna!", 'info');
        return;
    }
    
    if (!rawData.trim()) {
        showToast("Inserisci almeno un lead (email, azienda, 'info')!");
        return;
    }
    
    const lines = rawData.split('\n');
    const leads = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        // Split by comma
        const parts = line.split(',');
        let email = parts[0].trim();
        let company = parts.length > 1 ? parts.slice(1).join(',').trim() : "Unknown Company";
        
        if (email) {
            leads.push({ email, company });
        }
    }
    
    if (leads.length === 0) {
        showToast("Nessun lead valido trovato. Formato atteso: email, azienda", 'info');
        return;
    }
    
    if (!(await showConfirm(`Vuoi importare ${leads.length} leads e avviare immediatamente l'invio per la campagna '${campaign}'?`))) {
        return;
    }
    
    const btn = document.getElementById('btn-quick-send-execute');
    btn.disabled = true;
    btn.textContent = "IMPORTING & SENDING...";
    
    try {
        const res = await fetch('/api/quick_send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ campaign, leads, limit: leads.length })
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            showToast(data.message, 'info');
            document.getElementById('quick-send-data').value = ""; // Clear on success
            // Redirect to send tab to view logs
            switchTab('send');
        } else {
            showToast(data.error || data.detail || "Si è verificato un errore.", 'info');
        }
    } catch (e) {
        showToast("Errore di rete o server.", 'info');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.textContent = "🚀 IMPORT & SEND NOW";
    }
}

window.lastQuickSearchResults = [];

async function runQuickSearch() {
    const query = document.getElementById('quick-search-query').value.trim();
    if (!query) {
        showToast('Please enter a query', 'info');
        return;
    }
    
    const btn = document.getElementById('btn-quick-search');
    btn.disabled = true;
    btn.textContent = 'Searching...';
    
    try {
        const res = await fetch('/api/quick_search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query})
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            window.lastQuickSearchResults = data.leads;
            const tbody = document.getElementById('quick-search-tbody');
            tbody.innerHTML = '';
            data.leads.forEach(lead => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${lead.email}</td>
                    <td>${lead.domain}</td>
                    <td>${lead.relevance_score || lead.email_confidence}</td>
                `;
                tbody.appendChild(tr);
            });
            document.getElementById('quick-search-results').style.display = 'block';
        } else {
            showToast('Search failed: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🔍 Search Now';
    }
}

async function saveQuickSearchToCampaign() {
    if (!window.lastQuickSearchResults || window.lastQuickSearchResults.length === 0) {
        showToast('No leads to save', 'warning');
        return;
    }
    
    // Fetch research campaigns to let user select
    let camps = [];
    try {
        const res = await fetch('/api/research_campaigns');
        if (res.ok) camps = await res.json();
    } catch (e) {}

    if (camps.length === 0) {
        showToast('No Research Campaigns exist. Please create one first.', 'warning');
        return;
    }

    let options = camps.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content">
                <h3 style="margin-bottom: 1rem;">Select Research Campaign</h3>
                <p style="margin-bottom: 0.5rem; color: var(--text-muted);">Where should these ${window.lastQuickSearchResults.length} leads be saved?</p>
                <select id="qs-campaign-select" style="width: 100%; margin-bottom: 1.5rem; padding: 0.5rem;">
                    ${options}
                </select>
                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                    <button id="btn-qs-cancel" style="background: rgba(255,255,255,0.1);">Cancel</button>
                    <button id="btn-qs-save" class="btn-success">Save</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        document.getElementById('btn-qs-cancel').onclick = () => {
            overlay.remove();
            resolve();
        };
        document.getElementById('btn-qs-save').onclick = async () => {
            const select = document.getElementById('qs-campaign-select');
            const campId = parseInt(select.value);
            overlay.remove();
            
            await executeQuickSearchSave(campId);
            resolve();
        };
    });
}

async function saveQuickSearchToOutreach() {
    if (!window.lastQuickSearchResults || window.lastQuickSearchResults.length === 0) {
        showToast('No leads to save', 'warning');
        return;
    }
    const confirmed = await showConfirm(`Save ${window.lastQuickSearchResults.length} leads to Outreach (Pending Review) without a campaign?`);
    if (!confirmed) return;
    
    await executeQuickSearchSave(null);
}

async function executeQuickSearchSave(campaignId) {
    showToast('Saving leads...', 'info');
    try {
        const res = await fetch('/api/quick_search/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                leads: window.lastQuickSearchResults,
                campaign_id: campaignId
            })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Successfully saved ${data.inserted} new leads to pending review!`, 'success');
            document.getElementById('quick-search-results').style.display = 'none';
            window.lastQuickSearchResults = [];
        } else {
            showToast('Save failed: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (e) {
        showToast('Network error while saving', 'error');
    }
}

async function viewEvidence(prospectId) {
    try {
        const res = await fetch(`/api/prospects/${prospectId}/evidence`);
        if (!res.ok) {
            showToast('Failed to load evidence', 'error');
            return;
        }
        const data = await res.json();
        
        const sourcesHtml = data.sources.map(s => `
            <div style="background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 8px; margin-top: 0.5rem; border: 1px solid var(--border);">
                <div style="display:flex; justify-content:space-between; margin-bottom: 0.5rem;">
                    <strong><span style="color:var(--primary)">${s.engine}</span> • ${s.source_type}</strong>
                    <span style="color:var(--text-muted); font-size: 0.875rem;">${s.discovered_at.substring(0, 19).replace('T', ' ')}</span>
                </div>
                <div style="margin-bottom: 0.5rem; font-size: 0.875rem;">
                    <span style="color:var(--text-muted);">Query:</span> ${s.query}
                </div>
                <div style="font-size: 0.875rem; word-break: break-all;">
                    <span style="color:var(--text-muted);">Source:</span> <a href="${s.source_url}" target="_blank" style="color:var(--accent);">${s.source_url}</a>
                </div>
            </div>
        `).join('');

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content" style="max-width: 600px;">
                <h3 style="margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem;">Lead Evidence (ID: ${prospectId})</h3>
                
                <div style="margin-bottom: 1.5rem;">
                    <h4 style="margin-bottom: 0.5rem; color: var(--text-muted);">AI Qualification Reasoning</h4>
                    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 1rem; border-radius: 8px; font-size: 0.9rem; line-height: 1.5;">
                        ${data.why_matched || '<em>No reasoning provided</em>'}
                    </div>
                </div>
                
                <div style="margin-bottom: 1.5rem; max-height: 300px; overflow-y: auto; padding-right: 0.5rem;">
                    <h4 style="margin-bottom: 0.5rem; color: var(--text-muted);">Data Provenance (${data.sources.length} sources)</h4>
                    ${sourcesHtml || '<em>No provenance recorded</em>'}
                </div>

                <div style="display: flex; justify-content: flex-end;">
                    <button id="btn-close-evidence" style="background: var(--primary); padding: 0.5rem 1.5rem;">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        document.getElementById('btn-close-evidence').onclick = () => overlay.remove();
    } catch (e) {
        showToast('Error loading evidence', 'error');
    }
}

// Global System Terminal Polling
setInterval(async () => {
    try {
        const el = document.getElementById('sys-logs-content');
        if (!el || el.style.display === 'none') return;
        const res = await fetch('/api/system_logs');
        if (res.ok) {
            const data = await res.json();
            const wasAtBottom = Math.abs(el.scrollHeight - el.clientHeight - el.scrollTop) < 5;
            el.textContent = data.logs;
            if (wasAtBottom) {
                el.scrollTop = el.scrollHeight;
            }
        }
    } catch(e) {}
}, 2000);
