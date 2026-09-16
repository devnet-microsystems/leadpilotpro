import re

with open("static/app.js", "r") as f:
    content = f.read()

old_load = """async function loadContacts() {
    let url = '/api/contacts?t=' + Date.now();
    const res = await fetch(url);
    allContactsData = await res.json();
    
    document.getElementById('contacts-count').innerText = `(${allContactsData.length} total)`;
    currentContactsPage = 1;
    renderContactsPage();
}"""

new_load = """async function loadContacts() {
    try {
        let url = '/api/contacts?t=' + Date.now();
        const res = await fetch(url);
        const data = await res.json();
        if (Array.isArray(data)) {
            allContactsData = data;
        } else {
            allContactsData = [];
            console.error("API did not return an array:", data);
        }
    } catch (e) {
        console.error("Failed to load contacts:", e);
        allContactsData = [];
    }
    
    document.getElementById('contacts-count').innerText = `(${allContactsData.length} total)`;
    currentContactsPage = 1;
    renderContactsPage();
}"""

content = content.replace(old_load, new_load)

with open("static/app.js", "w") as f:
    f.write(content)
print("Done patching app.js loadContacts")
