import re

with open("static/app.js", "r") as f:
    content = f.read()

# 1. Update toggleContactSelect to populate the box and handle button state
old_toggle = """function toggleContactSelect() {
    const anyChecked = document.querySelectorAll('.contacts-checkbox:checked').length > 0;
    const btn = document.getElementById('btn-contacts-send');
    if (btn) btn.style.display = anyChecked ? 'inline-block' : 'none';
}"""

new_toggle = """// Track globally selected contacts across pagination (Optional, but let's just do current page for now since that's what was working)
function toggleContactSelect() {
    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    const btn = document.getElementById('btn-contacts-send');
    const box = document.getElementById('selected-contacts-box');
    
    if (checkboxes.length > 0) {
        if (btn) {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.innerText = `🚀 SEND ${checkboxes.length} SELECTED NOW`;
        }
        if (box) {
            box.innerHTML = '';
            checkboxes.forEach(cb => {
                const div = document.createElement('div');
                div.textContent = `${cb.dataset.email} (${cb.dataset.company})`;
                box.appendChild(div);
            });
        }
    } else {
        if (btn) {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.innerText = `🚀 SEND SELECTED NOW`;
        }
        if (box) {
            box.innerHTML = '<em>Nessuna email selezionata.</em>';
        }
    }
}"""

content = content.replace(old_toggle, new_toggle)

# 2. Remove modal functions
content = content.replace("""function showContactsModal() {
    const checkboxes = document.querySelectorAll('.contacts-checkbox:checked');
    if(checkboxes.length === 0) return;
    document.getElementById('contacts-modal').style.display = 'flex';
}

function closeContactsModal() {
    document.getElementById('contacts-modal').style.display = 'none';
}""", "")

# 3. Update executeContactsSend (remove closeContactsModal call)
content = content.replace("closeContactsModal();", "toggleContactSelect();")


with open("static/app.js", "w") as f:
    f.write(content)
print("Done patching app.js for box")
