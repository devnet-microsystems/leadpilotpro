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
        const res = await fetch(`/api/products/${productId}/analyze`, { method: 'POST' });
        if (!res.ok) throw new Error("Failed to start analysis");
        showToast("Analysis started", "success");
        loadProductsList();

        await loadProductsList();
    } catch (e) {
        showToast(e.message, "error");
    }
}

function toggleProductSourceInput() {
    const type = document.getElementById('add-product-type').value;
    if (type === 'URL') {
        document.getElementById('add-product-url-container').style.display = 'block';
        document.getElementById('add-product-text-container').style.display = 'none';
    } else {
        document.getElementById('add-product-url-container').style.display = 'none';
        document.getElementById('add-product-text-container').style.display = 'block';
    }
}

async function submitNewProduct() {
    const name = document.getElementById('add-product-name').value.trim();
    const type = document.getElementById('add-product-type').value;
    const url = document.getElementById('add-product-url').value.trim();
    const text = document.getElementById('add-product-text').value.trim();
    
    if (!name) return showToast('Product Name is required', 'error');
    if (type === 'URL' && !url) return showToast('Source URL is required', 'error');
    if (type === 'TEXT' && !text) return showToast('Source Text is required', 'error');
    
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
        res = await fetch(`/api/products/${productId}/sources`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source_type: type, content: contentPayload})
        });
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
        showToast('Product created and analysis started!', 'success');
        
        await loadProductsList();
        
    } catch (e) {
        alert(e.message || "An error occurred.");
    } finally {
        document.getElementById('add-product-submit-btn').disabled = false;
        document.getElementById('add-product-submit-btn').textContent = "Save Product";
    }
}
