import imaplib
import email
import email.policy
import logging
import os
from pathlib import Path
from outreach_sender import OutreachDatabase
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("LEADPILOT_DB_PATH") or (ROOT / "outreach_queue.sqlite3"))

def extract_email_address(from_header: str) -> str:
    match = re.search(r'[\w\.-]+@[\w\.-]+', from_header)
    return match.group(0).lower() if match else ""

def get_body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                return part.get_payload(decode=True).decode(errors='replace')
    else:
        return msg.get_payload(decode=True).decode(errors='replace')
    return ""

def sync_imap_inbox(db: OutreachDatabase):
    settings = {row["key"]: row["value"] for row in db.connection.execute("SELECT key, value FROM settings")}
    
    imap_host = settings.get("imap_host")
    if not imap_host:
        logging.info("IMAP non configurato. Salto il sync.")
        return {"success": False, "error": "IMAP non configurato."}
        
    imap_port = int(settings.get("imap_port", 993))
    imap_user = settings.get("smtp_user") # default to smtp user if no imap user
    imap_password = settings.get("smtp_password")
    
    if not imap_user or not imap_password:
        return {"success": False, "error": "Credenziali mancanti per IMAP (usa le stesse di SMTP)."}
        
    logging.info(f"Connessione IMAP a {imap_host}:{imap_port}...")
    try:
        if imap_port == 993:
            mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            mail = imaplib.IMAP4(imap_host, imap_port)
            
        mail.login(imap_user, imap_password)
        mail.select("INBOX")
        
        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            return {"success": False, "error": "Errore nella ricerca dei messaggi."}
            
        message_ids = data[0].split()
        logging.info(f"Trovati {len(message_ids)} messaggi UNSEEN.")
        
        stats = {"replied": 0, "auto_reply": 0, "unsubscribed": 0, "ignored": 0, "bounced": 0}
        
        for num in message_ids:
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
                
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email, policy=email.policy.default)
            
            subject = str(msg.get("Subject", ""))
            from_hdr = str(msg.get("From", ""))
            in_reply_to = str(msg.get("In-Reply-To", "")).strip("<>")
            references = str(msg.get("References", "")).strip("<>")
            auto_submitted = str(msg.get("Auto-Submitted", ""))
            precedence = str(msg.get("Precedence", ""))
            
            body_text = get_body_text(msg) or ""
            
            is_unsubscribe = "unsubscribe" in subject.lower()
            is_ooo = False
            is_bounce = False
            
            bounce_keywords = ["undelivered mail", "delivery status notification", "delivery failure", "returned to sender", "failure notice", "address not found", "bounced"]
            if any(kw in subject.lower() for kw in bounce_keywords):
                is_bounce = True

            # OOO Detection
            if auto_submitted.lower() in ("auto-replied", "auto-generated") or precedence.lower() == "auto_reply":
                is_ooo = True
                
            ooo_keywords = ["out of office", "automatic reply", "auto-reply", "abwesenheit", "fuori sede"]
            if any(kw in subject.lower() for kw in ooo_keywords):
                is_ooo = True
                
            matched_prospect = None
            
            # 1. Check if it's a direct unsubscribe (mailto link)
            if is_unsubscribe:
                sender_email = extract_email_address(from_hdr)
                if sender_email:
                    row = db.connection.execute("SELECT id FROM prospects WHERE business_email = ?", (sender_email,)).fetchone()
                    if row:
                        db.mark_unsubscribed(sender_email, "Unsubscribe request via Email")
                        stats["unsubscribed"] += 1
                        continue
            
            # 2. Check Thread via In-Reply-To or References
            search_ids = []
            if in_reply_to: search_ids.append(in_reply_to)
            if references: search_ids.extend(references.split())
            
            for ref_id in search_ids:
                ref_id = ref_id.strip("<>")
                row = db.connection.execute("SELECT id FROM prospects WHERE message_id = ?", (f"<{ref_id}>",)).fetchone()
                if not row:
                    row = db.connection.execute("SELECT id FROM prospects WHERE message_id = ?", (ref_id,)).fetchone()
                
                if row:
                    matched_prospect = row[0]
                    break
                    
            # Fallback for bounces: check raw email for failed email address
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
                        break

            if matched_prospect:
                incoming_msg_id = str(msg.get("Message-ID", ""))
                if is_bounce:
                    db.connection.execute("UPDATE prospects SET status='rejected' WHERE id=?", (matched_prospect,))
                    db.connection.commit()
                    stats["bounced"] += 1
                elif is_ooo:
                    db.mark_auto_reply(matched_prospect, incoming_msg_id, subject, body_text)
                    stats["auto_reply"] += 1
                else:
                    db.mark_replied(matched_prospect, incoming_msg_id, subject, body_text)
                    stats["replied"] += 1
            else:
                stats["ignored"] += 1
                
        mail.close()
        mail.logout()
        
        return {
            "success": True, 
            "message": f"Sync completato. Risposte: {stats['replied']}, Bounces: {stats['bounced']}, OOO: {stats['auto_reply']}, Disiscritti: {stats['unsubscribed']}."
        }
        
    except Exception as e:
        logging.error(f"IMAP Error: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    db = OutreachDatabase(DB_PATH)
    res = sync_imap_inbox(db)
    print(res)
