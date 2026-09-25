async function initProductsTab() {
    await loadProductsList();
}

async function loadProductsList() {
    try {
        const res = await fetch('/api/products');
        const data = await res.json();
        
        let html = `
            <div style="margin-bottom: 2rem;">
                <table style="width: 100%;">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.length === 0 ? '<tr><td colspan="3">No products found.</td></tr>' : ''}
                        ${data.map(p => `
                            <tr>
                                <td>${p.id}</td>
                                <td><strong>${p.name}</strong></td>
                                <td>
                                    <span style="color: ${p.status === 'READY' ? 'var(--success)' : (p.status === 'ANALYZING' ? 'var(--accent)' : (p.status === 'FAILED' ? 'var(--error)' : 'var(--text-muted)'))};">${p.status}</span>
                                    ${p.status === 'DRAFT' ? `<button onclick="analyzeProduct(${p.id})" style="margin-left: 10px; padding: 2px 8px; font-size: 0.8rem; background: var(--primary);">Analyze</button>` : ''}
                                    ${p.status === 'FAILED' ? `<button onclick="analyzeProduct(${p.id})" style="margin-left: 10px; padding: 2px 8px; font-size: 0.8rem; background: var(--error);">Retry</button>` : ''}
                                    <button onclick="openProductSources(${p.id})" style="margin-left:10px; padding:2px 8px; font-size:.8rem; background:transparent; border:1px solid var(--border);">Sources / PDFs</button>
                                    ${p.error_message ? `<div style="margin-top:.45rem;color:var(--error);font-size:.78rem;max-width:720px;">Error: ${escapeHtml(p.error_message)}</div>` : ''}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        document.getElementById('products-list-container').innerHTML = html;
        
        // Also refresh orchestrator dropdown if it's already rendered
        if (typeof initOrchestratorTab === 'function') {
            initOrchestratorTab();
        }

        // The global terminal handles all logs now, no need to poll individually.
        data.filter(p => p.status === 'ANALYZING').forEach(p => {
            if (!window.productPollers) window.productPollers = {};
            if (!window.productPollers[p.id]) {
                window.productPollers[p.id] = setInterval(async () => {
                    try {
                        const statusRes = await fetch('/api/products');
                        const statusData = await statusRes.json();
                        const current = statusData.find(x => x.id === p.id);
                        if (current && current.status !== 'ANALYZING') {
                            clearInterval(window.productPollers[p.id]);
                            delete window.productPollers[p.id];
                            loadProductsList();
                        }
                    } catch (err) {}
                }, 2000);
            }
        });

    } catch (e) {
        showToast('Failed to load products', 'error');
    }
}

async function analyzeProduct(productId) {
    try {
        const [productRes, sourceRes] = await Promise.all([
            fetch(`/api/products/${productId}`),
            fetch(`/api/products/${productId}/sources`)
        ]);
        if (!productRes.ok || !sourceRes.ok) throw new Error("Could not inspect product sources");
        const product = await productRes.json();
        const sources = await sourceRes.json();

        if (!Array.isArray(sources) || sources.length === 0) {
            showToast(
                `Add at least one source (URL, text, or PDF) to "${product.name}" before analyzing.`,
                "error"
            );
            openProductSources(productId);
            return;
        }

        const res = await fetch(`/api/products/${productId}/analyze`, { method: 'POST' });
        if (!res.ok) {
            let detail = "Failed to start analysis";
            try {
                const data = await res.json();
                if (data.detail) detail = data.detail;
            } catch (_) {}
            throw new Error(detail);
        }
        showToast("Analysis started", "success");
        await loadProductsList();
    } catch (e) {
        showToast(e.message || "Could not start analysis", "error");
    }
}

function toggleProductSourceInput() {
    const type = document.getElementById('add-product-type').value;
    document.getElementById('add-product-url-container').style.display = type === 'URL' ? 'block' : 'none';
    document.getElementById('add-product-pdf-container').style.display = type === 'PDF' ? 'block' : 'none';
    document.getElementById('add-product-text-container').style.display = type === 'TEXT' ? 'block' : 'none';
}

async function submitNewProduct() {
    const name = document.getElementById('add-product-name').value.trim();
    const type = document.getElementById('add-product-type').value;
    const url = document.getElementById('add-product-url').value.trim();
    const text = document.getElementById('add-product-text').value.trim();
    const pdf = document.getElementById('add-product-pdf').files[0];
    
    if (!name) return showToast('Product Name is required', 'error');
    if (type === 'URL' && !url) return showToast('Source URL is required', 'error');
    if (type === 'TEXT' && !text) return showToast('Source Text is required', 'error');
    if (type === 'PDF' && !pdf) return showToast('Select a PDF document', 'error');
    if (type === 'PDF' && pdf.size > 20 * 1024 * 1024) return showToast('PDF must be 20 MB or smaller', 'error');
    
    const contentPayload = type === 'URL' ? url : text;
    
    document.getElementById('add-product-submit-btn').disabled = true;
    document.getElementById('add-product-submit-btn').textContent = "Saving...";
    
    try {
        // 1. Create Product
        let res = await fetch('/api/products', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name})
        });
        if (!res.ok) throw new Error("Failed to create product");
        const product = await res.json();
        const productId = product.id;
        
        // 2. Add Source
        if (type === 'PDF') {
            const form = new FormData();
            form.append('file', pdf);
            res = await fetch(`/api/products/${productId}/sources/pdf`, {
                method: 'POST',
                body: form
            });
        } else {
            res = await fetch(`/api/products/${productId}/sources`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({source_type: type, content: contentPayload})
            });
        }
        if (!res.ok) {
            let errMsg = `Failed to add source ${type}`;
            try {
                const errData = await res.json();
                if (errData.detail) errMsg = errData.detail;
            } catch (e) {}
            throw new Error(errMsg);
        }
        
        // 3. Analyze
        res = await fetch(`/api/products/${productId}/analyze`, {
            method: 'POST'
        });
        if (!res.ok) throw new Error("Failed to start analysis");
        
        document.getElementById('add-product-name').value = '';
        document.getElementById('add-product-url').value = '';
        document.getElementById('add-product-text').value = '';
        document.getElementById('add-product-pdf').value = '';
        showToast('Product created and analysis started!', 'success');
        
        await loadProductsList();
        
    } catch (e) {
        alert(e.message || "An error occurred.");
    } finally {
        document.getElementById('add-product-submit-btn').disabled = false;
        document.getElementById('add-product-submit-btn').textContent = "Save Product";
    }
}

async function openProductSources(productId) {
    let modal;
    try {
        const [productRes, sourceRes] = await Promise.all([
            fetch(`/api/products/${productId}`),
            fetch(`/api/products/${productId}/sources`)
        ]);
        if (!productRes.ok || !sourceRes.ok) throw new Error('Could not load product sources');
        const product = await productRes.json();
        const sources = await sourceRes.json();

        modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content fc-source-modal">
                <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;">
                    <div>
                        <span class="eyebrow">Product sources</span>
                        <h3 style="margin:.25rem 0 .35rem;">${escapeHtml(product.name)}</h3>
                        <p style="color:var(--text-muted);margin:0;">Add PDFs to enrich the same product without creating duplicate products.</p>
                    </div>
                    <button id="fc-source-close" class="btn-secondary">Close</button>
                </div>
                <div style="margin-top:1.2rem;"><strong>Current sources</strong><div id="fc-source-list" style="margin-top:.6rem;"></div></div>
                <div class="fc-source-add">
                    <div><strong>Add PDF documents</strong><p class="fc-muted">Up to 10 PDFs per product, 20 MB each.</p></div>
                    <input id="fc-source-pdfs" type="file" accept=".pdf,application/pdf" multiple>
                    <button id="fc-upload-pdfs" class="btn-success">Upload PDFs</button>
                </div>
                <div style="display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem;">
                    <button id="fc-source-analyze" class="btn">Analyze product with current sources</button>
                </div>
            </div>`;
        document.body.appendChild(modal);

        const renderSources = (items) => {
            const list = document.getElementById('fc-source-list');
            if (!list) return;
            if (!items.length) { list.innerHTML = '<div class="fc-muted">No sources yet.</div>'; return; }
            list.innerHTML = items.map((s) => `
                <div class="fc-source-row">
                    <span class="fc-status">${escapeHtml(s.source_type || 'SOURCE')}</span>
                    <span style="flex:1;">${escapeHtml(s.source_name || 'Unnamed source')}</span>
                    <span class="fc-muted">${s.source_url ? 'URL source' : 'Local document'}</span>
                </div>`).join('');
        };
        renderSources(Array.isArray(sources) ? sources : []);

        document.getElementById('fc-source-close').onclick = () => modal.remove();
        modal.addEventListener('click', (event) => { if (event.target === modal) modal.remove(); });

        document.getElementById('fc-upload-pdfs').onclick = async () => {
            const input = document.getElementById('fc-source-pdfs');
            const files = Array.from(input.files || []);
            if (!files.length) return showToast('Select at least one PDF', 'error');
            if (files.some(file => file.size > 20 * 1024 * 1024)) return showToast('Each PDF must be 20 MB or smaller', 'error');
            const button = document.getElementById('fc-upload-pdfs');
            button.disabled = true; button.textContent = 'Uploading…';
            try {
                for (const file of files) {
                    const form = new FormData(); form.append('file', file);
                    const res = await fetch(`/api/products/${productId}/sources/pdf`, { method: 'POST', body: form });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(data.detail || `Failed to upload ${file.name}`);
                }
                const refreshed = await fetch(`/api/products/${productId}/sources`);
                renderSources(await refreshed.json());
                input.value = '';
                showToast('PDF sources added. Re-analyze the product to use them.', 'success');
                await loadProductsList();
            } catch (e) { showToast(e.message || 'PDF upload failed', 'error'); }
            finally { button.disabled = false; button.textContent = 'Upload PDFs'; }
        };

        document.getElementById('fc-source-analyze').onclick = async () => { modal.remove(); await analyzeProduct(productId); };
    } catch (e) { if (modal) modal.remove(); showToast(e.message || 'Could not load product sources', 'error'); }
}
