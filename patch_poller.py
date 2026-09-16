import re

with open("imap_poller.py", "r") as f:
    content = f.read()

# 1. Update stats dictionary to include bounced
content = content.replace(
    'stats = {"replied": 0, "auto_reply": 0, "unsubscribed": 0, "ignored": 0}',
    'stats = {"replied": 0, "auto_reply": 0, "unsubscribed": 0, "ignored": 0, "bounced": 0}'
)

# 2. Add bounce detection
old_ooo = """            is_unsubscribe = "unsubscribe" in subject.lower()
            is_ooo = False
            
            # OOO Detection"""

new_bounce = """            is_unsubscribe = "unsubscribe" in subject.lower()
            is_ooo = False
            is_bounce = False
            
            bounce_keywords = ["undelivered mail", "delivery status notification", "delivery failure", "returned to sender", "failure notice", "address not found", "bounced"]
            if any(kw in subject.lower() for kw in bounce_keywords):
                is_bounce = True

            # OOO Detection"""

content = content.replace(old_ooo, new_bounce)

# 3. Add body parsing for bounces if thread check fails
old_thread = """            for ref_id in search_ids:
                ref_id = ref_id.strip("<>")
                row = db.connection.execute("SELECT id FROM prospects WHERE message_id = ?", (f"<{ref_id}>",)).fetchone()
                if not row:
                    row = db.connection.execute("SELECT id FROM prospects WHERE message_id = ?", (ref_id,)).fetchone()
                
                if row:
                    matched_prospect = row[0]
                    break
                    
            if matched_prospect:"""

new_thread = """            for ref_id in search_ids:
                ref_id = ref_id.strip("<>")
                row = db.connection.execute("SELECT id FROM prospects WHERE message_id = ?", (f"<{ref_id}>",)).fetchone()
                if not row:
                    row = db.connection.execute("SELECT id FROM prospects WHERE message_id = ?", (ref_id,)).fetchone()
                
                if row:
                    matched_prospect = row[0]
                    break
                    
            # Fallback for bounces: check body for failed email address
            if not matched_prospect and is_bounce:
                import re
                found_emails = re.findall(r'[\w\.-]+@[\w\.-]+', body_text)
                for cand in found_emails:
                    cand = cand.lower()
                    if cand == imap_user.lower() or cand == sender_email: continue
                    row = db.connection.execute("SELECT id FROM prospects WHERE business_email = ?", (cand,)).fetchone()
                    if row:
                        matched_prospect = row[0]
                        break

            if matched_prospect:"""

content = content.replace(old_thread, new_thread)

# 4. Handle bounce logic
old_handle = """            if matched_prospect:
                incoming_msg_id = str(msg.get("Message-ID", ""))
                if is_ooo:
                    db.mark_auto_reply(matched_prospect, incoming_msg_id, subject, body_text)
                    stats["auto_reply"] += 1
                else:"""

new_handle = """            if matched_prospect:
                incoming_msg_id = str(msg.get("Message-ID", ""))
                if is_bounce:
                    db.connection.execute("UPDATE prospects SET status='rejected' WHERE id=?", (matched_prospect,))
                    db.connection.commit()
                    stats["bounced"] += 1
                elif is_ooo:
                    db.mark_auto_reply(matched_prospect, incoming_msg_id, subject, body_text)
                    stats["auto_reply"] += 1
                else:"""

content = content.replace(old_handle, new_handle)

# 5. Update success message
old_msg = """            "message": f"Sync completato. Risposte vere: {stats['replied']}, OOO: {stats['auto_reply']}, Disiscritti: {stats['unsubscribed']}." """
new_msg = """            "message": f"Sync completato. Risposte: {stats['replied']}, Bounces: {stats['bounced']}, OOO: {stats['auto_reply']}, Disiscritti: {stats['unsubscribed']}." """
content = content.replace(old_msg, new_msg)

with open("imap_poller.py", "w") as f:
    f.write(content)
print("Done patching imap_poller.py")
