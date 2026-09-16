import re

with open("static/index.html", "r") as f:
    content = f.read()

# 1. Update dropdown header
content = content.replace(
    '''<div class="tab" onclick="switchTab('contacts')">Leads ▾</div>''',
    '''<div class="tab" onclick="switchTab('quicksend')">Leads ▾</div>'''
)

# 2. Remove Contacts Hub item & rename Quicksend
content = content.replace(
    '''<div class="tab" onclick="switchTab('contacts')" style="color:#10b981; font-weight:bold;">★ Contacts Hub</div>''',
    ''
)
content = content.replace(
    '''<div class="tab" onclick="switchTab('quicksend')">Quick Import & Send</div>''',
    '''<div class="tab" onclick="switchTab('quicksend')" style="color:#10b981; font-weight:bold;">★ Address Book & Send</div>'''
)

# 3. Remove tab-contacts completely
# Use regex to find and remove the whole div id="tab-contacts" until "<!-- Pending Tab -->"
content = re.sub(r'<!-- Contacts Hub Tab -->.*?<!-- Pending Tab -->', '<!-- Pending Tab -->', content, flags=re.DOTALL)

# 4. Modify tab-quicksend to include the table and pagination
old_quicksend = """            <!-- Quick Import & Send Tab -->
            <div id="tab-quicksend" class="hidden">
                <div class="action-bar">
                    <h2>Quick Import & Send</h2>
                </div>
                <p style="color:var(--text-muted); font-size:0.875rem;">Incolla una lista di email e aziende, seleziona la campagna e invia a tutti immediatamente (ignora la coda di approvazione).</p>
                
                <div class="glass-panel" style="margin-top:1rem; display:flex; flex-direction:column; gap:1rem;">
                    <div>
                        <label style="display:block; margin-bottom:0.5rem; color:var(--text-muted); font-size:0.875rem;">Target Campaign</label>
                        <select id="quick-send-campaign-select" style="width:100%; max-width:400px; padding:0.75rem; border-radius:8px;">
                            <option value="">Loading campaigns...</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block; margin-bottom:0.5rem; color:var(--text-muted); font-size:0.875rem;">Leads (formato: email, azienda - uno per riga)</label>
                        <textarea id="quick-send-data" rows="10" style="width:100%; padding:0.75rem; border-radius:8px; background:rgba(0,0,0,0.2); border:1px solid var(--border); color:white; font-family:monospace;" placeholder="mario.rossi@azienda1.it, Azienda Uno Spa&#10;info@azienda2.com, Azienda Due Srl"></textarea>
                    </div>
                    <div style="margin-top:1rem;">
                        <button id="btn-quick-send-execute" style="background:#ef4444; padding:0.75rem 2rem; font-size:1rem;" onclick="executeQuickSend()">🚀 IMPORT & SEND NOW</button>
                    </div>
                </div>
            </div>"""

new_quicksend = """            <!-- Quick Import & Send Tab -->
            <div id="tab-quicksend" class="hidden">
                <div class="action-bar">
                    <h2>Address Book & Quick Send</h2>
                </div>
                
                <div style="display: flex; gap: 2rem; flex-wrap: wrap;">
                    <!-- Database Contacts (Paginated) -->
                    <div class="glass-panel" style="flex: 2; min-width: 400px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                            <h3 style="margin: 0; color: #10b981;">Database Contacts <span id="contacts-count" style="color:var(--text-muted); font-size:0.9rem; font-weight:normal; margin-left:0.5rem;">(0 total)</span></h3>
                            <button id="btn-contacts-send" class="btn-primary" style="display:none; background:#ef4444; border:none;" onclick="showContactsModal()">✉️ Send to Selected</button>
                        </div>
                        <p style="color:var(--text-muted); font-size:0.8rem; margin-top:-0.5rem; margin-bottom:1rem;">Select contacts from your address book to send immediately.</p>
                        
                        <div style="overflow-x: auto; max-height: 400px;">
                            <table style="width: 100%; text-align: left; border-collapse: collapse;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--border);">
                                        <th style="padding: 0.5rem; width: 40px;"><input type="checkbox" id="contacts-select-all" onchange="toggleAllContacts(this)"></th>
                                        <th style="padding: 0.5rem;">Email</th>
                                        <th style="padding: 0.5rem;">Company</th>
                                    </tr>
                                </thead>
                                <tbody id="contacts-tbody">
                                    <tr><td colspan="3" style="text-align:center; padding: 1rem;">Loading...</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
                            <button onclick="prevContactsPage()" style="background:transparent; border:1px solid var(--border); color:var(--text); padding:0.25rem 0.75rem; border-radius:4px; cursor:pointer;">&laquo; Prev</button>
                            <span id="contacts-page-info" style="color:var(--text-muted); font-size:0.9rem;">Page 1</span>
                            <button onclick="nextContactsPage()" style="background:transparent; border:1px solid var(--border); color:var(--text); padding:0.25rem 0.75rem; border-radius:4px; cursor:pointer;">Next &raquo;</button>
                        </div>
                    </div>
                    
                    <!-- Manual Paste Option -->
                    <div class="glass-panel" style="flex: 1; min-width: 300px; display:flex; flex-direction:column; gap:1rem;">
                        <h3 style="margin: 0;">Manual Quick Send</h3>
                        <p style="color:var(--text-muted); font-size:0.8rem; margin-top:-0.5rem;">Paste custom emails not in the DB to send immediately.</p>
                        
                        <div>
                            <label style="display:block; margin-bottom:0.5rem; color:var(--text-muted); font-size:0.875rem;">Target Campaign</label>
                            <select id="quick-send-campaign-select" style="width:100%; padding:0.75rem; border-radius:8px; background:var(--bg-input); color:var(--text); border:1px solid var(--border);">
                                <option value="">Loading campaigns...</option>
                            </select>
                        </div>
                        <div style="flex: 1;">
                            <label style="display:block; margin-bottom:0.5rem; color:var(--text-muted); font-size:0.875rem;">Leads (email, azienda - one per line)</label>
                            <textarea id="quick-send-data" style="width:100%; height: 100%; min-height: 200px; padding:0.75rem; border-radius:8px; background:rgba(0,0,0,0.2); border:1px solid var(--border); color:white; font-family:monospace;" placeholder="mario.rossi@azienda1.it, Azienda Uno Spa&#10;info@azienda2.com, Azienda Due Srl"></textarea>
                        </div>
                        <div>
                            <button id="btn-quick-send-execute" style="width: 100%; background:#ef4444; padding:0.75rem 2rem; font-size:1rem; font-weight:bold; color: white; border: none; border-radius: 8px; cursor: pointer;" onclick="executeQuickSend()">🚀 PASTE & SEND NOW</button>
                        </div>
                    </div>
                </div>
            </div>"""

content = content.replace(old_quicksend, new_quicksend)

with open("static/index.html", "w") as f:
    f.write(content)
print("Done patching index.html")
