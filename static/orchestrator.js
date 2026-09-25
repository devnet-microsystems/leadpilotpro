let currentOrchestratorProduct = null;

async function initOrchestratorTab() {
    try {
        const res = await fetch('/api/products');
        const data = await res.json();
        
        let html = `
            <div style="margin-bottom: 2rem;">
                <label>Select Product to Orchestrate:</label>
                <select id="orchestrator-product-select" style="margin-left: 1rem; padding: 0.5rem; width: 300px; background: rgba(255,255,255,0.05); color: white; border: 1px solid var(--border);" onchange="loadOrchestratorPipeline(this.value)">
                    <option value="">-- Choose a Product --</option>
                    ${data.map(p => `<option value="${p.id}">${p.name}</option>`).join('')}
                </select>
            </div>
            
            <div id="orchestrator-pipeline-container"></div>
        `;
        document.getElementById('orchestrator-root').innerHTML = html;
        
    } catch (e) {
        showToast('Failed to load products', 'error');
    }
}

async function loadOrchestratorPipeline(productId) {
    if (!productId) {
        document.getElementById('orchestrator-pipeline-container').innerHTML = '';
        currentOrchestratorProduct = null;
        return;
    }
    currentOrchestratorProduct = productId;
    
    try {
        const res = await fetch(`/api/orchestrator/pipeline_status?product_id=${productId}`);
        const status = await res.json();
        
        const evidenceRes = await fetch(`/api/orchestrator/evidence?product_id=${productId}`);
        const evidence = await evidenceRes.json();
        
        renderOrchestratorPipeline(status, evidence);
    } catch (e) {
        showToast('Failed to load pipeline status', 'error');
    }
}

function renderOrchestratorPipeline(status, evidence) {
    const container = document.getElementById('orchestrator-pipeline-container');
    
    const pendingEvidence = evidence.filter(e => !e.evidence_reviewed_at);
    const approvedEvidence = evidence.filter(e => e.evidence_reviewed_at);
    
    // Gating Logic
    const canEvaluate = status.discovered > 0;
    const canReview = status.qualified > 0 && pendingEvidence.length > 0;
    const canGenerate = approvedEvidence.length > 0;
    
    let html = `
        <div style="display: flex; flex-direction: column; gap: 2rem;">
            
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(16, 185, 129, 0.1); padding: 1.5rem; border-radius: 8px; border: 1px solid var(--success);">
                <div>
                    <h3 style="color: var(--success); margin: 0 0 0.5rem 0;">✨ AI Auto-Pilot</h3>
                    <p style="margin: 0; color: var(--text-muted);">Fully automated end-to-end OSINT Discovery, AI Qualification, and Strategy Generation.</p>
                </div>
                <button class="btn-success" onclick="runAutoPilot()" style="font-size: 1.1rem; padding: 0.75rem 2rem; box-shadow: 0 4px 15px rgba(16,185,129,0.4);">Engage Auto-Pilot</button>
            </div>
            
            <div id="auto-pilot-log-container" style="display: none; background: #000; color: #0f0; padding: 1rem; border-radius: 8px; font-family: monospace; font-size: 0.9rem; max-height: 300px; overflow-y: auto; white-space: pre-wrap; margin-top: -1rem; margin-bottom: 1rem; border: 1px solid var(--border);">
            </div>

            
            <!-- Step 1: Discovered -->
            <div class="glass-panel" style="border-left: 4px solid var(--primary);">
                <h3>Step 1: Market Discovery</h3>
                <p style="color: var(--text-muted);">Prospects discovered via Research Campaigns matching ICP.</p>
                <div style="font-size: 2rem; margin: 1rem 0;">${status.discovered} Prospects</div>
                <button class="btn" onclick="switchTab('query_studio')">Go to Query Studio</button>
            </div>
            
            <!-- Step 2: Evaluate Fit -->
            <div class="glass-panel" style="border-left: 4px solid ${canEvaluate ? 'var(--accent)' : 'var(--border)'}; opacity: ${canEvaluate ? '1' : '0.5'}">
                <h3>Step 2: AI Fit Evaluation</h3>
                <p style="color: var(--text-muted);">Run the AI qualification agent on discovered prospects.</p>
                <div style="font-size: 1.5rem; margin: 1rem 0;">
                    ${status.qualified} Qualified / ${status.rejected} Rejected
                </div>
                <button class="btn-success" onclick="runFitEvaluation()" ${canEvaluate ? '' : 'disabled'}>Run Evaluation</button>
            </div>
            
            <!-- Step 3: Evidence Review Gate -->
            <div class="glass-panel" style="border-left: 4px solid ${canReview ? '#e67e22' : 'var(--border)'}; opacity: ${status.qualified > 0 ? '1' : '0.5'}">
                <h3>Step 3: Evidence Review Gate</h3>
                <p style="color: var(--text-muted);">Human review of AI qualification evidence. You must approve at least one prospect to proceed to Strategy.</p>
                <div style="font-size: 1.2rem; margin: 1rem 0;">
                    ${pendingEvidence.length} Pending Review / ${approvedEvidence.length} Approved
                </div>
                
                ${pendingEvidence.length > 0 ? `
                <table style="width: 100%; margin-top: 1rem;">
                    <thead>
                        <tr>
                            <th>Company</th>
                            <th>AI Reason</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${pendingEvidence.map(e => `
                            <tr>
                                <td><a href="${e.target_url}" target="_blank" style="color: var(--accent);">${e.company_name}</a></td>
                                <td>${e.reason}</td>
                                <td>
                                    <button class="btn-success" onclick="reviewEvidence(${e.id}, 'APPROVE')" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;">Approve</button>
                                    <button onclick="reviewEvidence(${e.id}, 'REJECT')" style="padding: 0.25rem 0.5rem; font-size: 0.8rem; background: rgba(255,0,0,0.2);">Reject</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                ` : '<p style="color: var(--success);">All evidence reviewed!</p>'}
            </div>
            
            <!-- Step 4: Strategy & Sequence -->
            <div class="glass-panel" style="border-left: 4px solid ${canGenerate ? 'var(--primary)' : 'var(--border)'}; opacity: ${canGenerate ? '1' : '0.5'}">
                <h3>Step 4: Sales Strategy & Sequence</h3>
                <p style="color: var(--text-muted);">Generate personalized outreach strategy based on approved evidence.</p>
                <div style="font-size: 1.5rem; margin: 1rem 0;">
                    ${status.approved} Approved Campaigns
                </div>
                <button class="btn" onclick="switchTab('sales_campaigns')" ${canGenerate ? '' : 'disabled'}>Go to Sales Campaigns</button>
            </div>
            
        </div>
    `;
    
    container.innerHTML = html;
}

async function runFitEvaluation() {
    if (!currentOrchestratorProduct) return;
    showToast("Running Evaluation...", "info");
    try {
        const res = await fetch('/api/orchestrator/evaluate_fit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ product_id: currentOrchestratorProduct })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Evaluation Complete. Qualified: ${data.stats.qualified}`, "success");
            loadOrchestratorPipeline(currentOrchestratorProduct);
        } else {
            showToast(data.detail || "Evaluation failed", "error");
        }
    } catch (e) {
        showToast("Error running evaluation", "error");
    }
}

let autoPilotLogInterval = null;

async function runAutoPilot() {
    if (!currentOrchestratorProduct) return;
    showToast("Engaging Auto-Pilot... Initiating OSINT Market Research", "success");
    try {
        const res = await fetch('/api/orchestrator/auto_pilot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ product_id: currentOrchestratorProduct })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, "success");
            
            // Show log container
            const logContainer = document.getElementById('auto-pilot-log-container');
            logContainer.style.display = 'block';
            logContainer.innerText = "Initializing Auto-Pilot...\n";
            
            if (autoPilotLogInterval) clearInterval(autoPilotLogInterval);
            let lastLogSize = 0;
            
            autoPilotLogInterval = setInterval(async () => {
                try {
                    const logRes = await fetch(`/api/research_campaigns/${data.campaign_id}/logs`);
                    if (logRes.ok) {
                        const logData = await logRes.json();
                        if (logData.logs.length > lastLogSize) {
                            logContainer.innerText = logData.logs;
                            lastLogSize = logData.logs.length;
                            logContainer.scrollTop = logContainer.scrollHeight;
                        }
                    }
                } catch(e) {}
            }, 2000);
            
            setTimeout(() => {
                if (autoPilotLogInterval) clearInterval(autoPilotLogInterval);
                loadOrchestratorPipeline(currentOrchestratorProduct);
            }, 60000); // refresh UI after a while
        } else {
            showToast(data.detail || "Auto-Pilot failed", "error");
        }
    } catch (e) {
        showToast("Error engaging Auto-Pilot", "error");
    }
}

async function reviewEvidence(prospectId, action) {
    if (!currentOrchestratorProduct) return;
    let reason = "";
    if (action === 'REJECT') {
        reason = prompt("Reason for rejection:");
        if (reason === null) return;
    }
    
    try {
        const res = await fetch(`/api/orchestrator/prospect/${prospectId}/review`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action, reason })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Prospect ${action}D`, "success");
            loadOrchestratorPipeline(currentOrchestratorProduct);
        } else {
            showToast(data.detail || "Review failed", "error");
        }
    } catch (e) {
        showToast("Error submitting review", "error");
    }
}
