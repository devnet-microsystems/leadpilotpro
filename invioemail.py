import csv
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CREDENZIALI ---
SMTP_HOST = "mail.infomaniak.com"
SMTP_PORT = 587
SMTP_USERNAME = "antoniomichelotti@devnet-microsystems.com"
SMTP_PASSWORD = "Y*76G88gYvNth&!*"
OUTREACH_FROM_NAME = "Antonio Michelotti"
OUTREACH_FROM_EMAIL = "antoniomichelotti@devnet-microsystems.com"

# --- RESUME CONFIGURATION ---
START_FROM = 61  # L'indice da cui ripartire (il log si è fermato al 60)

# --- IL PAYLOAD ---
SUBJECT = "API & Auth security review for your infrastructure"
BODY = """Hi,

I'm an independent Systems Architect specialized in Zero-Trust WebAuthn and API security. 

I'm reaching out because as your platform scales, authentication endpoints inevitably become prime targets for credential stuffing, token hijacking, and brute-force attacks.

I don't do bloated $5,000 agency audits that require endless Zoom meetings. I perform ruthless, focused security reviews of your authentication and API layers. 

I test your endpoints and deliver a detailed PDF report with severity rankings and code-level remediation steps. 

My rules of engagement:
- 100% Asynchronous. Zero calls. Zero corporate fluff.
- Fixed Price: €149.
- Turnaround: 48 hours.

If you want your perimeter checked by a Senior Architect, you can initialize the audit and submit your endpoint specs here:
https://devnet-microsystems.com/audit

Best regards,

Antonio Michelotti
Systems Architect | DEV-NET Microsystems
"""

def pulisci_e_estrai(file_csv):
    print(f"[*] Fase 1: Estrazione dati da {file_csv}...")
    emails_valide = [] 
    viste = set()
    try:
        with open(file_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # Salta l'header
            for row in reader:
                if len(row) > 1:
                    email = row[1].strip()
                    if "@" in email and "." in email and email not in viste:
                        viste.add(email)
                        emails_valide.append(email)
        print(f"[*] Trovate {len(emails_valide)} email uniche.\n")
        return emails_valide
    except FileNotFoundError:
        print(f"[!] ERRORE: Il file {file_csv} non esiste.")
        return []

def invia_singola_email(target_email):
    """Apre la connessione, invia una singola mail e si disconnette subito."""
    msg = MIMEMultipart()
    msg['From'] = f"{OUTREACH_FROM_NAME} <{OUTREACH_FROM_EMAIL}>"
    msg['To'] = target_email
    msg['Subject'] = SUBJECT
    msg['Reply-To'] = OUTREACH_FROM_EMAIL
    msg.attach(MIMEText(BODY, 'plain'))

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.ehlo()
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    server.send_message(msg)
    server.quit()

def esegui_attacco_smtp(email_list):
    if not email_list:
        return

    print(f"[*] Fase 2: Ripristino sessione. Partenza dall'indice {START_FROM}...")

    for count, target_email in enumerate(email_list, 1):
        if count < START_FROM:
            continue  # Salta quelli già inviati ieri

        try:
            # Invio effimero: si connette, spara e si disconnette
            invia_singola_email(target_email)
            print(f"[{count}/{len(email_list)}] [+] INVIATA -> {target_email}")
            
            # Pausa tattica a connessione chiusa
            if count < len(email_list):
                delay = random.randint(35, 65)
                print(f"    ...pausa fantasma di {delay} secondi...")
                time.sleep(delay)

        except Exception as e:
            print(f"\n[!] ERRORE SU {target_email}: {e}")
            print("    ...attesa di 60 secondi per ripristino connessione...")
            time.sleep(60)

    print("\n[*] GIOVANNI 2.0 PROTOCOL COMPLETE. Tutte le 140 email sono state consegnate.")

if __name__ == "__main__":
    target_emails = pulisci_e_estrai('pippo.csv')
    esegui_attacco_smtp(target_emails)
