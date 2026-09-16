import re

with open("static/index.html", "r") as f:
    content = f.read()

# Add Delete button in the header of Database Contacts
old_header = """<h3 style="margin: 0; color: #10b981;">Database Contacts <span id="contacts-count" style="color:var(--text-muted); font-size:0.9rem; font-weight:normal; margin-left:0.5rem;">(0 total)</span></h3>"""
new_header = """<div style="display:flex; align-items:center; gap: 1rem;">
                                <h3 style="margin: 0; color: #10b981;">Database Contacts <span id="contacts-count" style="color:var(--text-muted); font-size:0.9rem; font-weight:normal; margin-left:0.5rem;">(0 total)</span></h3>
                                <button id="btn-contacts-delete" style="display:none; background:transparent; border:1px solid #ef4444; color:#ef4444; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.8rem; cursor:pointer;" onclick="deleteSelectedContacts()">🗑️ Delete Selected</button>
                            </div>"""

content = content.replace(old_header, new_header)

with open("static/index.html", "w") as f:
    f.write(content)
print("Done patching index.html for delete button")
