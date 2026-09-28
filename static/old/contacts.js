// static/contacts.js
// Tab "Address Book" (menu Outreach): mostra tutti i contatti gia' noti (deduplicati, esclusi i
// rejected/unsubscribed) e permette di rimettere quelli scelti in uscita su un'altra campagna,
// oppure di blacklistarli. Riusa endpoint gia' esistenti: /api/contacts, /api/contacts/blacklist
// e /api/quick_send (lo stesso usato dal riquadro "Manual Quick Send" qui accanto).

const CONTACTS_PAGE_SIZE = 25;
let contactsAll = [];               // tutti i contatti da /api/contacts: {business_email, company_name}
let contactsFiltered = [];          // dopo il filtro testuale
let contactsPage = 0;
const contactsSelected = new Set(); // business_email selezionati: persiste cambiando pagina/filtro

function ctEl(id) { return document.getElementById(id); }

async function loadContactsTab() {
    contactsSelected.clear();
    const tbody = ctEl('contacts-tbody');
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 1rem;">Loading...</td></tr>';
    try {
        const res = await fetch('/api/contacts');
        contactsAll = await res.json();
        if (!Array.isArray(contactsAll)) contactsAll = [];
    } catch (e) {
        console.error('Error loading contacts', e);
        contactsAll = [];
    }
    applyContactsFilter();
}

function applyContactsFilter() {
    const q = (ctEl('contacts-search').value || '').trim().toLowerCase();
    contactsFiltered = q
        ? contactsAll.filter(c => (c.business_email || '').toLowerCase().includes(q) || (c.company_name || '').toLowerCase().includes(q))
        : contactsAll;
    contactsPage = 0;
    renderContactsTable();
    updateSelectedContactsUI();
}

function contactsCurrentPageRows() {
    const start = contactsPage * CONTACTS_PAGE_SIZE;
    return contactsFiltered.slice(start, start + CONTACTS_PAGE_SIZE);
}

function renderContactsTable() {
    const totalPages = Math.max(1, Math.ceil(contactsFiltered.length / CONTACTS_PAGE_SIZE));
    contactsPage = Math.min(contactsPage, totalPages - 1);
    const pageRows = contactsCurrentPageRows();

    const tbody = ctEl('contacts-tbody');
    tbody.innerHTML = '';
    if (pageRows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 1rem; color:var(--text-muted);">No contacts found.</td></tr>';
    }
    pageRows.forEach(c => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border)';

        const tdChk = document.createElement('td');
        tdChk.style.padding = '0.5rem';
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.checked = contactsSelected.has(c.business_email);
        chk.onchange = () => {
            if (chk.checked) contactsSelected.add(c.business_email);
            else contactsSelected.delete(c.business_email);
            updateContactsSelectAllState();
            updateSelectedContactsUI();
        };
        tdChk.appendChild(chk);

        const tdEmail = document.createElement('td');
        tdEmail.style.padding = '0.5rem';
        tdEmail.textContent = c.business_email;

        const tdCompany = document.createElement('td');
        tdCompany.style.padding = '0.5rem';
        tdCompany.textContent = c.company_name || '';

        tr.append(tdChk, tdEmail, tdCompany);
        tbody.appendChild(tr);
    });

    ctEl('contacts-count').textContent = `(${contactsFiltered.length} total)`;
    ctEl('contacts-page-info').textContent = `Page ${contactsPage + 1} of ${totalPages}`;
    updateContactsSelectAllState();
}

// La checkbox nell'intestazione riflette/agisce solo sulla pagina corrente (visibile), non su tutti i risultati.
function updateContactsSelectAllState() {
    const pageEmails = contactsCurrentPageRows().map(c => c.business_email);
    const selectAll = ctEl('contacts-select-all');
    selectAll.checked = pageEmails.length > 0 && pageEmails.every(e => contactsSelected.has(e));
}

function toggleAllContacts(checkbox) {
    contactsCurrentPageRows().forEach(c => {
        if (checkbox.checked) contactsSelected.add(c.business_email);
        else contactsSelected.delete(c.business_email);
    });
    renderContactsTable();
    updateSelectedContactsUI();
}

function prevContactsPage() {
    if (contactsPage > 0) { contactsPage--; renderContactsTable(); }
}

function nextContactsPage() {
    const totalPages = Math.max(1, Math.ceil(contactsFiltered.length / CONTACTS_PAGE_SIZE));
    if (contactsPage < totalPages - 1) { contactsPage++; renderContactsTable(); }
}

function updateSelectedContactsUI() {
    const box = ctEl('selected-contacts-box');
    const n = contactsSelected.size;
    box.innerHTML = n === 0
        ? '<em>Nessuna email selezionata.</em>'
        : [...contactsSelected].map(e => `<div>${e}</div>`).join('');

    const sendBtn = ctEl('btn-contacts-send');
    sendBtn.disabled = n === 0;
    sendBtn.style.opacity = n === 0 ? '0.5' : '1';
    ctEl('btn-contacts-delete').style.display = n === 0 ? 'none' : 'inline-block';
}

async function blacklistSelectedContacts() {
    const emails = [...contactsSelected];
    if (emails.length === 0) return;
    if (!(await showConfirm(`Blacklist ${emails.length} selected contact(s)? They will no longer receive emails from any campaign.`))) return;

    try {
        const res = await fetch('/api/contacts/blacklist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`${emails.length} contact(s) blacklisted.`, 'info');
            contactsAll = contactsAll.filter(c => !emails.includes(c.business_email));
            contactsSelected.clear();
            applyContactsFilter();
        } else {
            showToast(data.error || 'Blacklist failed.', 'info');
        }
    } catch (e) {
        console.error(e);
        showToast('Network or server error.', 'info');
    }
}

// Rimette i contatti selezionati in uscita sulla campagna scelta e avvia subito l'invio
// (stesso endpoint /api/quick_send del riquadro "Manual Quick Send" qui accanto: sposta lo
// status a 'approved' e il campaign_id su quello scelto, anche se erano gia' 'sent' o 'rejected').
async function executeContactsSend() {
    const campaign = ctEl('contacts-campaign-select').value;
    const emails = [...contactsSelected];
    if (!campaign) { showToast('Select a target campaign first!', 'info'); return; }
    if (emails.length === 0) { showToast('Select at least one contact.', 'info'); return; }

    if (!(await showConfirm(`Move ${emails.length} contact(s) to campaign '${campaign}' and start sending immediately?`))) return;

    const companyByEmail = new Map(contactsAll.map(c => [c.business_email, c.company_name]));
    const leads = emails.map(e => ({ email: e, company: companyByEmail.get(e) || 'Unknown Company' }));

    const btn = ctEl('btn-contacts-send');
    btn.disabled = true;
    btn.textContent = 'SENDING...';
    try {
        const res = await fetch('/api/quick_send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ campaign, leads, limit: leads.length })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(data.message || 'Send started.', 'info');
            contactsSelected.clear();
            switchTab('send'); // per vedere subito il progresso nella Sender Queue
        } else {
            showToast(data.error || data.detail || 'An error occurred.', 'info');
        }
    } catch (e) {
        console.error(e);
        showToast('Network or server error.', 'info');
    } finally {
        btn.disabled = contactsSelected.size === 0;
        btn.textContent = '🚀 SEND SELECTED NOW';
    }
}
