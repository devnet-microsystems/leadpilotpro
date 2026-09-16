import re

with open("static/index.html", "r") as f:
    content = f.read()

# 1. Remove the "Send to Selected" button in the Database Contacts header
content = content.replace(
    '''<button id="btn-contacts-send" class="btn-primary" style="display:none; background:#ef4444; border:none;" onclick="showContactsModal()">✉️ Send to Selected</button>''',
    ''''''
)

# 2. Modify the right column layout
old_right_column = """                    <!-- Manual Paste Option -->
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
                    </div>"""

new_right_column = """                    <!-- Right Column: Selected & Manual -->
                    <div style="flex: 1; min-width: 300px; display:flex; flex-direction:column; gap:2rem;">
                        
                        <!-- Selected Contacts Box -->
                        <div class="glass-panel" style="display:flex; flex-direction:column; gap:1rem;">
                            <h3 style="margin: 0; color: #10b981;">Selected Contacts</h3>
                            
                            <div id="selected-contacts-box" style="background: rgba(0,0,0,0.2); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem; min-height: 80px; max-height: 150px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; color: var(--text-muted);">
                                <em>Nessuna email selezionata.</em>
                            </div>
                            
                            <div>
                                <label style="display:block; margin-bottom:0.5rem; color:var(--text-muted); font-size:0.875rem;">Target Campaign</label>
                                <select id="contacts-campaign-select" style="width:100%; padding:0.75rem; border-radius:8px; background:var(--bg-input); color:var(--text); border:1px solid var(--border);">
                                    <option value="">Loading campaigns...</option>
                                </select>
                            </div>
                            <div>
                                <button id="btn-contacts-send" style="width: 100%; background:#ef4444; padding:0.75rem 2rem; font-size:1rem; font-weight:bold; color: white; border: none; border-radius: 8px; cursor: pointer; opacity: 0.5;" onclick="executeContactsSend(true)" disabled>🚀 SEND SELECTED NOW</button>
                            </div>
                        </div>

                        <!-- Manual Paste Option -->
                        <div class="glass-panel" style="display:flex; flex-direction:column; gap:1rem;">
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
                                <textarea id="quick-send-data" style="width:100%; height: 100%; min-height: 120px; padding:0.75rem; border-radius:8px; background:rgba(0,0,0,0.2); border:1px solid var(--border); color:white; font-family:monospace;" placeholder="mario.rossi@azienda1.it, Azienda Uno Spa&#10;info@azienda2.com, Azienda Due Srl"></textarea>
                            </div>
                            <div>
                                <button id="btn-quick-send-execute" style="width: 100%; background:#ef4444; padding:0.75rem 2rem; font-size:1rem; font-weight:bold; color: white; border: none; border-radius: 8px; cursor: pointer;" onclick="executeQuickSend()">🚀 PASTE & SEND NOW</button>
                            </div>
                        </div>
                        
                    </div>"""

content = content.replace(old_right_column, new_right_column)

# 3. Remove contacts-modal completely
content = re.sub(r'<!-- Contacts Hub Modal -->.*?</div>\s*</div>', '', content, flags=re.DOTALL)

with open("static/index.html", "w") as f:
    f.write(content)
print("Done patching index.html layout")
