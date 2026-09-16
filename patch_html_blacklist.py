import re

with open("static/index.html", "r") as f:
    content = f.read()

old_button = """<button id="btn-contacts-delete" style="display:none; background:transparent; border:1px solid #ef4444; color:#ef4444; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.8rem; cursor:pointer;" onclick="deleteSelectedContacts()">🗑️ Delete Selected</button>"""
new_button = """<button id="btn-contacts-delete" style="display:none; background:transparent; border:1px solid #ef4444; color:#ef4444; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.8rem; cursor:pointer;" onclick="blacklistSelectedContacts()">🚫 Blacklist Selected</button>"""

content = content.replace(old_button, new_button)

with open("static/index.html", "w") as f:
    f.write(content)
print("Done patching index.html for blacklist")
