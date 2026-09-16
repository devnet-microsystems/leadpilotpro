import re

with open("static/app.js", "r") as f:
    content = f.read()

# 1. Update loadContacts() function to use pagination variables
old_contacts = """// -- Contacts Hub Functions --
async function loadContacts() {
    let url = '/api/contacts?t=' + Date.now();
    const res = await fetch(url);
    const data = await res.json();
    
    document.getElementById('contacts-count').innerText = `(${data.length} total)`;
    const tbody = document.getElementById('contacts-tbody');
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">No contacts found.</td></tr>';
        document.getElementById('btn-contacts-send').style.display = 'none';
        return;
    }
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="checkbox" class="contacts-checkbox" value="${escapeHtml(row.business_email)}|${escapeHtml(row.company_name)}" onchange="toggleContactSelect()"></td>
            <td>${escapeHtml(row.business_email)}</td>
            <td>${escapeHtml(row.company_name)}</td>
        `;
        tbody.appendChild(tr);
    });
    toggleContactSelect();
}"""

new_contacts = """// -- Contacts Hub Functions --
let allContactsData = [];
let currentContactsPage = 1;
const CONTACTS_PER_PAGE = 50;

async function loadContacts() {
    let url = '/api/contacts?t=' + Date.now();
    const res = await fetch(url);
    allContactsData = await res.json();
    
    document.getElementById('contacts-count').innerText = `(${allContactsData.length} total)`;
    currentContactsPage = 1;
    renderContactsPage();
}

function renderContactsPage() {
    const tbody = document.getElementById('contacts-tbody');
    tbody.innerHTML = '';
    
    if (allContactsData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">No contacts found.</td></tr>';
        document.getElementById('btn-contacts-send').style.display = 'none';
        document.getElementById('contacts-page-info').innerText = 'Page 1 of 1';
        return;
    }
    
    const totalPages = Math.ceil(allContactsData.length / CONTACTS_PER_PAGE) || 1;
    if (currentContactsPage > totalPages) currentContactsPage = totalPages;
    if (currentContactsPage < 1) currentContactsPage = 1;
    
    document.getElementById('contacts-page-info').innerText = `Page ${currentContactsPage} of ${totalPages}`;
    
    const startIdx = (currentContactsPage - 1) * CONTACTS_PER_PAGE;
    const endIdx = startIdx + CONTACTS_PER_PAGE;
    const pageData = allContactsData.slice(startIdx, endIdx);
    
    // Clear select all if paginated
    const selectAllCb = document.getElementById('contacts-select-all');
    if (selectAllCb) selectAllCb.checked = false;
    
    pageData.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="padding:0.5rem;"><input type="checkbox" class="contacts-checkbox" value="${escapeHtml(row.business_email)}|${escapeHtml(row.company_name)}" onchange="toggleContactSelect()"></td>
            <td style="padding:0.5rem;">${escapeHtml(row.business_email)}</td>
            <td style="padding:0.5rem;">${escapeHtml(row.company_name)}</td>
        `;
        tbody.appendChild(tr);
    });
    toggleContactSelect();
}

function prevContactsPage() {
    if (currentContactsPage > 1) {
        currentContactsPage--;
        renderContactsPage();
    }
}

function nextContactsPage() {
    const totalPages = Math.ceil(allContactsData.length / CONTACTS_PER_PAGE);
    if (currentContactsPage < totalPages) {
        currentContactsPage++;
        renderContactsPage();
    }
}"""

content = content.replace(old_contacts, new_contacts)

# Fix switchTab('contacts') mapping to switchTab('quicksend') inside loadContacts() equivalent
content = content.replace("else if (tabId === 'contacts') loadContacts();", "else if (tabId === 'quicksend') loadContacts();")

with open("static/app.js", "w") as f:
    f.write(content)
print("Done patching app.js")
