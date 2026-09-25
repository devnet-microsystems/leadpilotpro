let currentOrchestratorProduct = null;
let autoPilotLogInterval = null;
let autoPilotStatusInterval = null;

function orchEl(id) {
    return document.getElementById(id);
}

function orchEscape(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function orchStatusLabel(status) {
    const map = {
        DRAFT: 'Ready to configure',
        READY: 'Ready',
        ANALYZING: 'Analyzing product…',
        RUNNING: 'Research running…',
        COMPLETED: 'Research complete',
        FAILED: 'Research failed'
    };
    return map[status] || status || 'Not started';
}

function orchNotify(message, type = 'info') {
    if (typeof showToast === 'function') showToast(message, type);
    else console.log(message);
}

async function initOrchestratorTab() {
    if (autoPilotLogInterval) {
        clearInterval(autoPilotLogInterval);
        autoPilotLogInterval = null;
    }
    if (autoPilotStatusInterval) {
        clearInterval(autoPilotStatusInterval);
        autoPilotStatusInterval = null;
    }

    try {
        const res = await fetch('/api/products');
        if (!res.ok) throw new Error('Could not load products');
        const products = await res.json();
        renderFindCustomersStart(Array.isArray(products) ? products : []);
    } catch (e) {
        console.error(e);
        orchNotify('Could not load products', 'error');
    }
}

function renderFindCustomersStart(products) {
    const root = orchEl('orchestrator-root');
    if (!root) return;

    const readyCount = products.filter(p => p.status === 'READY').length;

    if (!products.length) {
        root.innerHTML = `
            <div class="fc-empty glass-panel">
                <div class="fc-step-number">1</div>
                <h3>Start with something you sell</h3>
                <p>LeadPilot needs a product description, website, text, or PDF before it can define the target market.</p>
                <button class="btn-success" onclick="switchTab('products')">Add Product →</button>
            </div>`;
        return;
    }

    root.innerHTML = `
        <div class="fc-shell">
            <div class="fc-intro">
                <div>
                    <span class="eyebrow">Find Customers</span>
                    <h2>Turn one product into a qualified customer pipeline.</h2>
                    <p>LeadPilot analyzes the product, builds the target profile, discovers companies, evaluates fit, and stops before outreach until you review what was found.</p>
                </div>
                <div class="fc-intro-badge">${readyCount} ready product${readyCount === 1 ? '' : 's'}</div>
            </div>

            <section class="fc-panel">
                <div class="fc-panel-head">
                    <div>
                        <span class="fc-step">01</span>
                        <h3>Choose your product</h3>
                        <p>Select the analyzed product you want to find customers for.</p>
                    </div>
                    <button class="btn-secondary" onclick="switchTab('products')">Manage Products</button>
                </div>

                <div class="fc-product-grid">
                    ${products.map(p => `
                        <button class="fc-product-card ${p.status === 'READY' ? '' : 'is-disabled'}" onclick="loadOrchestratorPipeline(${Number(p.id)})">
                            <div class="fc-product-card-top">
                                <strong>${orchEscape(p.name)}</strong>
                                <span class="fc-status ${String(p.status || '').toLowerCase()}">${orchEscape(p.status)}</span>
                            </div>
                            <span class="fc-product-card-copy">${orchEscape(orchStatusLabel(p.status))}</span>
                            ${p.status !== 'READY' ? '<span class="fc-product-card-action">Open product setup →</span>' : '<span class="fc-product-card-action">Use this product →</span>'}
                        </button>
                    `).join('')}
                </div>
            </section>

            <div id="fc-selected-pipeline"></div>

            <section class="fc-how-it-works">
                <div><strong>What LeadPilot does</strong><span>Analyze product → build ICP → search multiple sources → verify evidence → prepare outreach</span></div>
                <div><strong>What it does not do</strong><span>No email is sent by Find Customers. Sending stays behind the existing approval gate.</span></div>
            </section>
        </div>`;
}

async function loadOrchestratorPipeline(productId) {
    const id = Number(productId);
    if (!id) return;

    currentOrchestratorProduct = id;
    const container = orchEl('fc-selected-pipeline') || orchEl('orchestrator-pipeline-container');
    if (!container) return;

    container.innerHTML = `
        <section class="fc-panel fc-loading">
            <div class="fc-spinner"></div>
            <div><strong>Loading the customer-finding pipeline…</strong><p>Reading product readiness and previous research results.</p></div>
        </section>`;

    try {
        const [productsRes, statusRes, evidenceRes] = await Promise.all([
            fetch('/api/products'),
            fetch(`/api/orchestrator/pipeline_status?product_id=${encodeURIComponent(id)}`),
            fetch(`/api/orchestrator/evidence?product_id=${encodeURIComponent(id)}`)
        ]);

        const products = productsRes.ok ? await productsRes.json() : [];
        const product = Array.isArray(products) ? products.find(p => Number(p.id) === id) : null;
        const status = statusRes.ok ? await statusRes.json() : {
            discovered: 0, qualified: 0, rejected: 0, approved: 0,
            campaign_status: null, campaign_id: null
        };
        const evidence = evidenceRes.ok ? await evidenceRes.json() : [];

        renderFindCustomersPipeline(product, status, Array.isArray(evidence) ? evidence : []);
    } catch (e) {
        console.error(e);
        container.innerHTML = '<section class="fc-panel"><strong>Could not load this pipeline.</strong><p>Please open Technical Logs for details.</p></section>';
    }
}

function renderFindCustomersPipeline(product, status, evidence) {
    const container = orchEl('fc-selected-pipeline') || orchEl('orchestrator-pipeline-container');
    if (!container) return;

    if (!product) {
        container.innerHTML = '<section class="fc-panel"><strong>Product not found.</strong></section>';
        return;
    }

    const ready = product.status === 'READY';
    const running = status.campaign_status === 'RUNNING';
    const failed = status.campaign_status === 'FAILED';
    const complete = status.campaign_status === 'COMPLETED';
    const pendingEvidence = evidence.filter(e => !e.evidence_reviewed_at);
    const reviewedEvidence = evidence.filter(e => e.evidence_reviewed_at);

    container.innerHTML = `
        <section class="fc-panel fc-run-panel">
            <div class="fc-panel-head">
                <div>
                    <span class="fc-step">02</span>
                    <h3>Set the search budget</h3>
                    <p>The relevance gate remains fixed at 40/100. Choose how many leads the research engine may collect before stopping.</p>
                </div>
                <div class="fc-budget">
                    <label for="fc-max-leads">Maximum leads</label>
                    <select id="fc-max-leads" ${running ? 'disabled' : ''}>
                        <option value="50">50 — focused</option>
                        <option value="150" selected>150 — recommended</option>
                        <option value="300">300 — broad</option>
                        <option value="500">500 — very broad</option>
                    </select>
                </div>
            </div>

            <div class="fc-explain-grid">
                <div><strong>Target market</strong><span>Derived from the analyzed product profile.</span></div>
                <div><strong>Sources</strong><span>Automatic routing across enabled search providers.</span></div>
                <div><strong>Qualification</strong><span>Evidence + email quality + relevance gate remain enforced.</span></div>
            </div>

            <div class="fc-action-row">
                <button class="btn-success fc-main-action" onclick="runAutoPilot()" ${!ready || running ? 'disabled' : ''}>
                    ${running ? 'Research in progress…' : (complete ? 'Run Research Again' : 'Find Customers')}
                </button>
                ${!ready ? '<button class="btn-secondary" onclick="switchTab(\'products\')">Finish Product Analysis →</button>' : ''}
                ${status.campaign_id ? '<span class="fc-run-state">' + orchEscape(orchStatusLabel(status.campaign_status)) + '</span>' : '<span class="fc-run-state">No research run yet</span>'}
            </div>

            <div id="auto-pilot-log-container" class="fc-log" style="display:none;"></div>
        </section>

        <section class="fc-panel">
            <div class="fc-panel-head compact">
                <div>
                    <span class="fc-step">03</span>
                    <h3>Research results</h3>
                    <p>These counters update from the same database used by Research and Outreach.</p>
                </div>
            </div>
            <div class="fc-metrics">
                <div><span>Companies / prospects discovered</span><strong>${Number(status.discovered || 0)}</strong></div>
                <div><span>Product-fit qualified</span><strong>${Number(status.qualified || 0)}</strong></div>
                <div><span>Rejected / unqualified</span><strong>${Number(status.rejected || 0)}</strong></div>
                <div><span>Approved sales campaigns</span><strong>${Number(status.approved || 0)}</strong></div>
            </div>
        </section>

        ${status.qualified > 0 ? `
        <section class="fc-panel">
            <div class="fc-panel-head compact">
                <div>
                    <span class="fc-step">04</span>
                    <h3>Evidence review</h3>
                    <p>Review why the engine considers each prospect a fit before building the sales sequence.</p>
                </div>
                <div class="fc-review-count">${pendingEvidence.length} pending · ${reviewedEvidence.length} reviewed</div>
            </div>
            ${pendingEvidence.length ? `
                <div class="fc-evidence-list">
                    ${pendingEvidence.slice(0, 12).map(e => `
                        <div class="fc-evidence-row">
                            <div>
                                <strong>${orchEscape(e.company_name)}</strong>
                                <p>${orchEscape(e.reason || 'No reason recorded.')}</p>
                                ${e.target_url ? `<a href="${orchEscape(e.target_url)}" target="_blank" rel="noopener">Open source →</a>` : ''}
                            </div>
                            <div class="fc-evidence-actions">
                                <button class="btn-success" onclick="reviewEvidence(${Number(e.id)}, 'APPROVE')">Approve</button>
                                <button class="btn-secondary" onclick="reviewEvidence(${Number(e.id)}, 'REJECT')">Reject</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
                ${pendingEvidence.length > 12 ? '<p class="fc-muted">Showing the first 12 pending items. Use Review Leads for the full queue.</p>' : ''}
            ` : '<div class="fc-success-note">All currently qualified evidence is reviewed.</div>'}
        </section>
        ` : ''}

        <section class="fc-panel fc-next-panel">
            <div>
                <span class="fc-step">05</span>
                <h3>Next: sales outreach</h3>
                <p>Build the strategy and email sequence in Sales Campaigns. Approval is still required before the sender can use it.</p>
            </div>
            <button class="btn" onclick="switchTab('sales_campaigns')" ${status.qualified ? '' : 'disabled'}>Open Sales Campaigns →</button>
        </section>
    `;

    if (running) {
        startAutoPilotMonitoring(status.campaign_id);
    }
    if (failed) {
        orchNotify('The research run failed. Technical Logs contains the execution details.', 'error');
    }
}

function startAutoPilotMonitoring(campaignId) {
    if (autoPilotLogInterval) clearInterval(autoPilotLogInterval);
    if (autoPilotStatusInterval) clearInterval(autoPilotStatusInterval);

    const logContainer = orchEl('auto-pilot-log-container');
    if (logContainer) {
        logContainer.style.display = 'block';
        logContainer.textContent = 'Starting research…';
    }

    let polls = 0;
    autoPilotLogInterval = setInterval(async () => {
        polls += 1;
        try {
            const [logRes, statusRes] = await Promise.all([
                fetch(`/api/research_campaigns/${campaignId}/logs`),
                fetch(`/api/orchestrator/pipeline_status?product_id=${currentOrchestratorProduct}`)
            ]);
            if (logRes.ok && logContainer) {
                const logData = await logRes.json();
                logContainer.textContent = logData.logs || 'Research is running…';
                logContainer.scrollTop = logContainer.scrollHeight;
            }
            if (statusRes.ok) {
                const status = await statusRes.json();
                if (status.campaign_status === 'COMPLETED' || status.campaign_status === 'FAILED' || polls >= 1800) {
                    clearInterval(autoPilotLogInterval);
                    autoPilotLogInterval = null;
                    loadOrchestratorPipeline(currentOrchestratorProduct);
                }
            }
        } catch (e) {
            if (polls >= 1800) {
                clearInterval(autoPilotLogInterval);
                autoPilotLogInterval = null;
            }
        }
    }, 2000);
}

async function runAutoPilot() {
    if (!currentOrchestratorProduct) return;
    const budget = Number(orchEl('fc-max-leads')?.value || 150);
    const btn = document.querySelector('.fc-main-action');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Starting research…';
    }

    orchNotify('Starting market research…', 'success');
    try {
        const res = await fetch('/api/orchestrator/auto_pilot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: currentOrchestratorProduct,
                max_leads: budget
            })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.detail || data.error || 'Auto-Pilot failed to start');
        }

        orchNotify('Research started. No email has been sent.', 'success');
        startAutoPilotMonitoring(data.campaign_id);
    } catch (e) {
        console.error(e);
        orchNotify(e.message || 'Could not start research', 'error');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Find Customers';
        }
    }
}

// Kept for Advanced/legacy flows.
async function runFitEvaluation() {
    if (!currentOrchestratorProduct) return;
    try {
        const res = await fetch('/api/orchestrator/evaluate_fit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ product_id: currentOrchestratorProduct })
        });
        const data = await res.json();
        if (data.success) {
            orchNotify(`Qualification check complete: ${data.stats.qualified} qualified`, 'success');
            loadOrchestratorPipeline(currentOrchestratorProduct);
        } else {
            orchNotify(data.detail || 'Qualification check failed', 'error');
        }
    } catch (e) {
        orchNotify('Error running qualification check', 'error');
    }
}

async function reviewEvidence(prospectId, action) {
    if (!currentOrchestratorProduct) return;
    let reason = '';
    if (action === 'REJECT') {
        reason = typeof showPrompt === 'function'
            ? await showPrompt('Reason for rejection:', 'Not a fit')
            : window.prompt('Reason for rejection:', 'Not a fit');
        if (reason === null) return;
    }

    try {
        const res = await fetch(`/api/orchestrator/prospect/${prospectId}/review`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action, reason })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.detail || 'Review failed');
        }
        orchNotify(action === 'APPROVE' ? 'Evidence approved' : 'Prospect rejected', 'success');
        loadOrchestratorPipeline(currentOrchestratorProduct);
    } catch (e) {
        console.error(e);
        orchNotify(e.message || 'Could not update evidence', 'error');
    }
}
