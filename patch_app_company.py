import re

with open("static/app.js", "r") as f:
    content = f.read()

# 1. Update renderContactsPage row creation
old_row = """    pageData.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="padding:0.5rem;"><input type="checkbox" class="contacts-checkbox" value="${escapeHtml(row.business_email)}|${escapeHtml(row.company_name)}" onchange="toggleContactSelect()"></td>
            <td style="padding:0.5rem;">${escapeHtml(row.business_email)}</td>
            <td style="padding:0.5rem;">${escapeHtml(row.company_name)}</td>
        `;
        tbody.appendChild(tr);
    });"""

new_row = """    pageData.forEach(row => {
        const tr = document.createElement('tr');
        const safeEmail = escapeHtml(row.business_email);
        const safeCompany = escapeHtml(row.company_name);
        tr.innerHTML = `
            <td style="padding:0.5rem;"><input type="checkbox" class="contacts-checkbox" data-email="${safeEmail}" data-company="${safeCompany}" onchange="toggleContactSelect()"></td>
            <td style="padding:0.5rem;">${safeEmail}</td>
            <td style="padding:0.5rem;">
                <input type="text" value="${safeCompany}" 
                       style="background: transparent; border: 1px solid transparent; color: white; width: 100%; border-radius: 4px; padding: 0.25rem; font-family: inherit; font-size: inherit;"
                       onfocus="this.style.border='1px solid var(--primary)'"
                       onblur="updateContactCompany('${safeEmail}', this.value); this.style.border='1px solid transparent'"
                       title="Click to edit">
            </td>
        `;
        tbody.appendChild(tr);
    });"""

content = content.replace(old_row, new_row)

# 2. Add updateContactCompany function
update_func = """
async function updateContactCompany(email, newCompany) {
    const c = allContactsData.find(x => x.business_email === email);
    if (c && c.company_name !== newCompany) {
        c.company_name = newCompany;
        const cb = document.querySelector(`.contacts-checkbox[data-email="${email}"]`);
        if (cb) cb.dataset.company = newCompany;
        
        try {
            const res = await fetch('/api/contacts/update_company', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, company: newCompany })
            });
            if (!res.ok) {
                console.error("Failed to update company");
            }
        } catch (e) {
            console.error("Network error updating company", e);
        }
    }
}
"""

content = content.replace("function prevContactsPage() {", update_func + "\nfunction prevContactsPage() {")


# 3. Update executeContactsSend to use dataset
old_leads = """    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const leads = Array.from(checkboxes).map(cb => {
        const parts = cb.value.split('|');
        return { email: parts[0], company: parts[1] };
    });"""

new_leads = """    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const leads = Array.from(checkboxes).map(cb => {
        return { email: cb.dataset.email, company: cb.dataset.company };
    });"""

content = content.replace(old_leads, new_leads)

with open("static/app.js", "w") as f:
    f.write(content)
print("Done patching app.js for inline edits")
