import re

with open("static/app.js", "r") as f:
    content = f.read()

# 1. Update toggleContactSelect to also show/hide the delete button
old_toggle = """function toggleContactSelect() {
    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const btn = document.getElementById('btn-contacts-send');
    const box = document.getElementById('selected-contacts-box');"""

new_toggle = """function toggleContactSelect() {
    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const btn = document.getElementById('btn-contacts-send');
    const box = document.getElementById('selected-contacts-box');
    const btnDelete = document.getElementById('btn-contacts-delete');"""

content = content.replace(old_toggle, new_toggle)

old_btn_show = """        if (btn) {
            btn.disabled = false;"""
new_btn_show = """        if (btnDelete) btnDelete.style.display = 'block';
        if (btn) {
            btn.disabled = false;"""
content = content.replace(old_btn_show, new_btn_show)

old_btn_hide = """        if (btn) {
            btn.disabled = true;"""
new_btn_hide = """        if (btnDelete) btnDelete.style.display = 'none';
        if (btn) {
            btn.disabled = true;"""
content = content.replace(old_btn_hide, new_btn_hide)

# 2. Add deleteSelectedContacts function
delete_func = """
async function deleteSelectedContacts() {
    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const emails = Array.from(checkboxes).map(cb => cb.dataset.email);
    
    if (emails.length === 0) return;
    
    if (!confirm(`Sei sicuro di voler ELIMINARE DEFINITIVAMENTE ${emails.length} contatti dal database?`)) return;
    
    try {
        const res = await fetch('/api/contacts', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: emails })
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            alert(`Eliminati ${emails.length} contatti.`);
            document.getElementById('contacts-select-all').checked = false;
            loadContacts();
        } else {
            alert(data.error || "Errore durante l'eliminazione.");
        }
    } catch (e) {
        alert("Errore di rete.");
        console.error(e);
    }
}
"""

content = content.replace("function prevContactsPage() {", delete_func + "\nfunction prevContactsPage() {")

with open("static/app.js", "w") as f:
    f.write(content)
print("Done patching app.js for delete button")
