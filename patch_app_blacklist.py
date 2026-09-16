import re

with open("static/app.js", "r") as f:
    content = f.read()

# 1. Rename deleteSelectedContacts to blacklistSelectedContacts
old_delete = """async function deleteSelectedContacts() {
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
}"""

new_blacklist = """async function blacklistSelectedContacts() {
    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const emails = Array.from(checkboxes).map(cb => cb.dataset.email);
    
    if (emails.length === 0) return;
    
    if (!confirm(`Sei sicuro di voler INSERIRE IN BLACKLIST ${emails.length} contatti? Non verranno più mostrati nella rubrica e non potranno essere ricontattati.`)) return;
    
    try {
        const res = await fetch('/api/contacts/blacklist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: emails })
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            alert(`Inseriti in blacklist ${emails.length} contatti.`);
            document.getElementById('contacts-select-all').checked = false;
            loadContacts();
            loadRejected(); // Aggiorna anche la tab rejected in background
        } else {
            alert(data.error || "Errore durante l'operazione.");
        }
    } catch (e) {
        alert("Errore di rete.");
        console.error(e);
    }
}"""
content = content.replace(old_delete, new_blacklist)

with open("static/app.js", "w") as f:
    f.write(content)
print("Done patching app.js for blacklist")
