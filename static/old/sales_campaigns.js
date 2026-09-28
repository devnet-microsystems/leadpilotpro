// static/sales_campaigns.js
// Tab "Sales Campaigns" (P5.3): contesto -> strategia -> sequenza email -> approvazione -> export verso Outreach.
// Nessun invio parte da qui: l'export crea solo template e campagne nel sender esistente.

const SC_ALLOWED_PLACEHOLDERS = ['first_name', 'last_name', 'company_name', 'role', 'industry', 'matched_signal', 'why_matched', 'market'];
let scContextToken = 0; // scarta le risposte di contesti selezionati prima e arrivate dopo

function scEl(id) { return document.getElementById(id); }

function scNotify(msg, type) {
    if (typeof showToast === 'function') showToast(msg, type || 'info');
    else alert(msg);
}

// FastAPI restituisce detail come stringa (HTTPException) o come lista di errori (422)
function scDetail(data, fallback) {
    const d = data && data.detail;
    if (Array.isArray(d)) return d.map(e => e.msg || JSON.stringify(e)).join('; ');
    return d || (data && data.error) || fallback || 'Request failed';
}

async function scJson(res) {
    try { return await res.json(); } catch (e) { return {}; }
}

function scFillSelect(selectId, items, placeholder) {
    const sel = scEl(selectId);
    sel.innerHTML = '';
    const first = document.createElement('option');
    first.value = '';
    first.textContent = placeholder;
    sel.appendChild(first);
    (items || []).forEach(item => {
        const o = document.createElement('option');
        o.value = item.value !== undefined ? item.value : item;
        o.textContent = item.label !== undefined ? item.label : item;
        sel.appendChild(o);
    });
    if ((items || []).length === 1) sel.selectedIndex = 1; // un solo valore possibile: preselezionato
}

function scResetPanels() {
    scEl('sc-strategy-panel').classList.add('hidden');
    scEl('sc-sequence-panel').classList.add('hidden');
    scEl('sc-export-result').textContent = '';
    window.current_sc_campaign_id = null;
}

function scResetContextSelects() {
    scFillSelect('sc-context-select', [], '-- Select Context (Market, Language, Segment, Role) --');
    scEl('sc-context-note').textContent = '';
}

function getSCContext() {
    const ctxVal = scEl('sc-context-select').value;
    if (!ctxVal) return null;
    const ctxParts = JSON.parse(ctxVal);
    const ctx = {
        product_id: parseInt(scEl('sc-product-select').value),
        research_campaign_id: parseInt(scEl('sc-rc-select').value),
        market: ctxParts.market,
        language: ctxParts.language,
        target_segment: ctxParts.target_segment,
        buyer_role: ctxParts.buyer_role
    };
    const complete = ctx.product_id && ctx.research_campaign_id && ctx.market && ctx.language && ctx.target_segment && ctx.buyer_role;
    return complete ? ctx : null;
}

// ---------------------------------------------------------------- selezione contesto

async function loadSalesCampaignsTab() {
    scResetPanels();
    scResetContextSelects();
    await loadSCProducts();
}

async function loadSCProducts() {
    try {
        const res = await fetch('/api/products');
        const prods = await res.json();
        scFillSelect('sc-product-select',
            (Array.isArray(prods) ? prods : []).map(p => ({ value: p.id, label: `${p.name} (${p.status})` })),
            '-- Select Product --');
        scFillSelect('sc-rc-select', [], '-- Select Research Campaign --');
    } catch (e) {
        console.error('Error loading products', e);
        scNotify('Could not load products', 'info');
    }
}

async function onSCProductChange() {
    const pid = scEl('sc-product-select').value;
    scResetPanels();
    scResetContextSelects();
    scFillSelect('sc-rc-select', [], '-- Select Research Campaign --');
    if (!pid) return;
    try {
        const res = await fetch(`/api/research_campaigns?product_id=${encodeURIComponent(pid)}`);
        const camps = await res.json();
        const list = Array.isArray(camps) ? camps : [];
        scFillSelect('sc-rc-select', list.map(c => ({ value: c.id, label: c.name })), '-- Select Research Campaign --');
        if (!list.length) scEl('sc-context-note').textContent = 'This product has no research campaign yet.';
        else if (list.length === 1) await onSCRCChange();
    } catch (e) {
        console.error('Error loading research campaigns', e);
    }
}

// /api/research_campaigns/{id}/contexts restituisce i contesti reali abilitati:
// {contexts: [{market, language, target_segment, buyer_role}]}
async function onSCRCChange() {
    const rcid = scEl('sc-rc-select').value;
    scResetPanels();
    scResetContextSelects();
    if (!rcid) return;
    try {
        const res = await fetch(`/api/research_campaigns/${encodeURIComponent(rcid)}/contexts`);
        const data = await scJson(res);
        if (!res.ok) { scNotify(scDetail(data, 'Could not load contexts'), 'info'); return; }
        
        const contexts = data.contexts || [];
        const options = contexts.map(c => {
            const label = `${c.market} | ${c.language} | ${c.target_segment} | ${c.buyer_role}`;
            return { value: JSON.stringify(c), label: label };
        });
        
        scFillSelect('sc-context-select', options, '-- Select Context (Market, Language, Segment, Role) --');
        
        if (!contexts.length) {
            scEl('sc-context-note').textContent = 'This research campaign has no enabled contexts.';
        }
        await onSCContextChange();
    } catch (e) {
        console.error('Error loading contexts', e);
    }
}

// Quando i quattro campi sono scelti mostra strategia e campagna GIA' esistenti (nessuna rigenerazione, nessun costo AI)
async function onSCContextChange() {
    const token = ++scContextToken;
    scResetPanels();
    const ctx = getSCContext();
    if (!ctx) return;
    const qs = new URLSearchParams(ctx).toString();
    scEl('sc-context-note').textContent = '';
    try {
        const sres = await fetch(`/api/sales_strategy?${qs}`);
        if (token !== scContextToken) return;
        if (sres.ok) {
            renderSCStrategy(await sres.json());
            scEl('sc-context-note').textContent = 'A strategy already exists for this context.';
        } else {
            scEl('sc-context-note').textContent = 'No strategy yet for this context: click "Generate Strategy".';
        }
        const lres = await fetch(`/api/product_campaign_lookup?${qs}`);
        if (token !== scContextToken) return;
        const look = await scJson(lres);
        if (look.campaign_id) await loadSCCampaign(look.campaign_id);
    } catch (e) {
        console.error('Error checking existing strategy/campaign', e);
    }
}

// ---------------------------------------------------------------- strategia

function renderSCStrategy(st) {
    scEl('sc-strategy-panel').classList.remove('hidden');
    scEl('sc-strat-vp').textContent = st.core_value_proposition || '';
    scEl('sc-strat-pp').textContent = (st.pain_points || []).map(x => `• ${x}`).join('\n') || '(none)';
    scEl('sc-strat-proof').textContent = (st.proof_points || []).map(x => `• ${x}`).join('\n') || '(none: the product profile does not provide any)';
    scEl('sc-strat-cta').textContent = st.primary_cta || '';
    scEl('sc-strat-tone').textContent = st.tone || '';
}

async function generateSCStrategy() {
    const ctx = getSCContext();
    if (!ctx) { scNotify('Please select product, research campaign, market, language, segment and role', 'info'); return; }
    const btn = scEl('btn-sc-gen-strategy');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    try {
        const res = await fetch('/api/sales_strategy/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ctx)
        });
        const data = await scJson(res);
        if (res.ok && data.strategy) {
            renderSCStrategy(data.strategy);
            scNotify('Strategy generated', 'info');
        } else {
            scNotify('Error: ' + scDetail(data), 'info');
        }
    } catch (e) {
        console.error(e);
        scNotify('Failed to generate strategy', 'info');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate Strategy';
    }
}

// ---------------------------------------------------------------- sequenza

async function generateSCCampaign() {
    const ctx = getSCContext();
    if (!ctx) { scNotify('Please select product, research campaign, market, language, segment and role', 'info'); return; }
    ctx.sequence_length = parseInt(scEl('sc-seq-length').value || 4);
    const btn = scEl('btn-sc-gen-campaign');
    btn.disabled = true;
    btn.textContent = 'Generating Sequence...';
    try {
        const res = await fetch('/api/product_campaigns/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ctx)
        });
        const data = await scJson(res);
        if (!res.ok) { scNotify('Error: ' + scDetail(data), 'info'); return; }
        scNotify(data.skipped
            ? `A ${data.status} campaign already exists for this context: it was preserved.`
            : 'Campaign generated', 'info');
        await loadSCCampaign(data.campaign_id);
    } catch (e) {
        console.error(e);
        scNotify('Failed to generate campaign', 'info');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate Campaign Sequence';
    }
}

async function loadSCCampaign(cid) {
    try {
        const res = await fetch(`/api/product_campaigns/${encodeURIComponent(cid)}`);
        const data = await scJson(res);
        if (!res.ok) { scNotify(scDetail(data, 'Could not load campaign'), 'info'); return; }

        window.current_sc_campaign_id = cid;
        window.current_sc_messages_len = data.messages.length;
        const editable = data.status === 'DRAFT';

        if (data.strategy) renderSCStrategy(data.strategy);

        const list = scEl('sc-messages-list');
        list.innerHTML = '';
        const hint = document.createElement('p');
        hint.style.cssText = 'color:var(--text-muted); font-size:0.85rem;';
        hint.textContent = 'Allowed placeholders: ' + SC_ALLOWED_PLACEHOLDERS.map(p => `{{${p}}}`).join(' ');
        list.appendChild(hint);

        data.messages.forEach((m, idx) => {
            const box = document.createElement('div');
            box.className = 'sc-message-editor';
            box.style.cssText = 'border:1px solid var(--border); padding:1rem; margin-bottom:1rem;';

            const title = document.createElement('h4');
            title.textContent = `Email ${idx + 1}` + (m.purpose ? ` - ${m.purpose}` : '');
            box.appendChild(title);

            const mk = (labelText, el) => {
                const l = document.createElement('label');
                l.textContent = labelText;
                box.appendChild(l);
                box.appendChild(el);
            };
            const delay = document.createElement('input');
            delay.type = 'number'; delay.min = '0'; delay.id = `sc-msg-delay-${idx}`;
            delay.value = m.delay_days ?? 0; delay.style.cssText = 'width:60px; margin-bottom:10px;';
            const subj = document.createElement('input');
            subj.type = 'text'; subj.id = `sc-msg-subj-${idx}`;
            subj.value = m.subject || ''; subj.style.cssText = 'width:100%; margin-bottom:10px;';
            const body = document.createElement('textarea');
            body.id = `sc-msg-body-${idx}`; body.rows = 8; body.style.width = '100%';
            body.value = m.body || '';
            [delay, subj, body].forEach(el => { el.disabled = !editable; });

            mk('Delay Days', delay);
            mk('Subject', subj);
            mk('Body', body);
            list.appendChild(box);
        });

        scEl('sc-campaign-status').textContent = data.status;
        scEl('btn-sc-save-draft').disabled = !editable;
        scEl('btn-sc-approve').disabled = !editable;
        scEl('btn-sc-export').classList.toggle('hidden', !['APPROVED', 'ACTIVE'].includes(data.status));
        scEl('sc-export-result').textContent = '';
        scEl('sc-sequence-panel').classList.remove('hidden');
    } catch (e) {
        console.error('Error loading campaign', e);
    }
}

// silent=true quando e' chiamata da "Approve": ritorna true solo se il salvataggio e' andato a buon fine
async function saveSCDraft(silent) {
    if (!window.current_sc_campaign_id) return false;

    const msgs = [];
    for (let i = 0; i < window.current_sc_messages_len; i++) {
        msgs.push({
            sequence_order: i + 1,
            delay_days: parseInt(scEl(`sc-msg-delay-${i}`).value || 0),
            subject: scEl(`sc-msg-subj-${i}`).value,
            body: scEl(`sc-msg-body-${i}`).value
        });
    }

    try {
        const res = await fetch(`/api/product_campaigns/${window.current_sc_campaign_id}/messages`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: msgs })
        });
        if (res.ok) {
            if (!silent) scNotify('Draft saved', 'info');
            return true;
        }
        scNotify('Error: ' + scDetail(await scJson(res)), 'info');
        return false;
    } catch (e) {
        console.error(e);
        scNotify('Failed to save draft', 'info');
        return false;
    }
}

async function approveSCCampaign() {
    if (!window.current_sc_campaign_id) return;
    const ok = (typeof showConfirm === 'function')
        ? await showConfirm('Approve this sequence? Approved sequences can no longer be edited.')
        : true;
    if (!ok) return;

    // Prima si salva quello che vedi a schermo; se il salvataggio fallisce NON si approva la versione vecchia.
    if (!(await saveSCDraft(true))) return;

    try {
        const res = await fetch(`/api/product_campaigns/${window.current_sc_campaign_id}/approve`, { method: 'POST' });
        const data = await scJson(res);
        if (res.ok) {
            scNotify('Campaign approved', 'info');
            await loadSCCampaign(window.current_sc_campaign_id);
        } else {
            scNotify('Error: ' + scDetail(data), 'info');
        }
    } catch (e) {
        console.error(e);
        scNotify('Failed to approve campaign', 'info');
    }
}

// Crea template + campagne nel sender esistente. Non invia nulla e non tocca i prospect.
async function exportSCCampaign() {
    if (!window.current_sc_campaign_id) return;
    const btn = scEl('btn-sc-export');
    btn.disabled = true;
    const out = scEl('sc-export-result');
    out.textContent = '';
    try {
        const res = await fetch(`/api/product_campaigns/${window.current_sc_campaign_id}/export_to_outreach`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ add_footer: true })
        });
        const data = await scJson(res);
        if (!res.ok) { scNotify('Error: ' + scDetail(data), 'info'); return; }

        const line = (text, color) => {
            const p = document.createElement('p');
            p.textContent = text;
            if (color) p.style.color = color;
            out.appendChild(p);
        };
        line(`Exported: ${data.created.length} new, ${data.existing.length} already present. Nothing was sent.`, 'var(--success)');
        data.created.forEach(c => line(`+ ${c.campaign}  (template ${c.template})`));
        data.existing.forEach(c => line(`= ${c.campaign}  (kept as it was)`, 'var(--text-muted)'));
        (data.warnings || []).forEach(w => line('! ' + w, '#f59e0b'));
        line('Next: Outreach > Campaigns / Templates to review, then Pending Review and Sender Queue to send.', 'var(--text-muted)');
    } catch (e) {
        console.error(e);
        scNotify('Failed to export campaign', 'info');
    } finally {
        btn.disabled = false;
    }
}
