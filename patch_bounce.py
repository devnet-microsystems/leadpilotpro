import re

with open("imap_poller.py", "r") as f:
    content = f.read()

# Fix the message string
old_msg = '            "message": f"Sync completato. Risposte vere: {stats[\'replied\']}, OOO: {stats[\'auto_reply\']}, Disiscritti: {stats[\'unsubscribed\']}."'
new_msg = '            "message": f"Sync completato. Risposte: {stats[\'replied\']}, Bounces: {stats[\'bounced\']}, OOO: {stats[\'auto_reply\']}, Disiscritti: {stats[\'unsubscribed\']}."'
content = content.replace(old_msg, new_msg)

# Update the fallback parsing to scan the raw email for bounces
old_fallback = """            # Fallback for bounces: check body for failed email address
            if not matched_prospect and is_bounce:
                import re
                found_emails = re.findall(r'[\\w\\.-]+@[\\w\\.-]+', body_text)
                for cand in found_emails:
                    cand = cand.lower()
                    if cand == imap_user.lower(): continue
                    row = db.connection.execute("SELECT id FROM prospects WHERE business_email = ?", (cand,)).fetchone()
                    if row:
                        matched_prospect = row[0]
                        break"""

new_fallback = """            # Fallback for bounces: check raw email for failed email address
            if not matched_prospect and is_bounce:
                import re
                try:
                    raw_text = raw_email.decode(errors='replace')
                except:
                    raw_text = body_text
                found_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_text)
                for cand in found_emails:
                    cand = cand.lower()
                    if cand == imap_user.lower(): continue
                    row = db.connection.execute("SELECT id FROM prospects WHERE business_email = ?", (cand,)).fetchone()
                    if row:
                        matched_prospect = row[0]
                        break"""
content = content.replace(old_fallback, new_fallback)

# To ensure the backend reloads the module, we can inject importlib.reload in web_server.py
with open("imap_poller.py", "w") as f:
    f.write(content)
print("Done patching imap_poller.py fallback")
