import csv
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CREDENZIALI (Dal tuo .env) ---
SMTP_HOST = "mail.infomaniak.com"
SMTP_PORT = 587
SMTP_USERNAME = "antoniomichelotti@devnet-microsystems.com"
SMTP_PASSWORD = "Y*76G88gYvNth&!*"
OUTREACH_FROM_NAME = "Antonio Michelotti"
OUTREACH_FROM_EMAIL = "antoniomichelotti@devnet-microsystems.com"

# --- IL PAYLOAD (Audit a 149€) ---
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
    print(f"[*] Fase 1: Estrazione e sanificazione dati da {file_csv}...")
    emails_valide = set() # Usiamo un Set per eliminare automaticamente i doppioni
    try:
        with open(file_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # Salta la riga dell'header
            for row in reader:
                # La business_email è nella colonna 2 (indice 1)
                if len(row) > 1:
                    email = row[1].strip()
                    if "@" in email and "." in email:
                        emails_valide.add(email)
        print(f"[*] Trovate {len(emails_valide)} email uniche e pronte al bersaglio.\n")
        return list(emails_valide)
    except FileNotFoundError:
        print(f"[!] ERRORE FATALE: Il file {file_csv} non esiste. Mettilo nella cartella dello script.")
        return []

def esegui_attacco_smtp(email_list):
    if not email_list:
        return

    print("[*] Fase 2: Connessione al server Infomaniak (Porta 587 - STARTTLS)...")
    try:
        # Avvio connessione SMTP
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.ehlo()
        server.starttls() # Upgrada la connessione a sicura
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        print("[*] Autenticazione riuscita. I server di DEV-NET sono armati.\n")

        for count, target_email in enumerate(email_list, 1):
            # Creazione email
            msg = MIMEMultipart()
            msg['From'] = f"{OUTREACH_FROM_NAME} <{OUTREACH_FROM_EMAIL}>"
            msg['To'] = target_email
            msg['Subject'] = SUBJECT
            msg['Reply-To'] = OUTREACH_FROM_EMAIL
            msg.attach(MIMEText(BODY, 'plain'))
            
            # Fuoco
            server.send_message(msg)
            print(f"[{count}/{len(email_list)}] [+] INVIATA -> {target_email}")
            
            # Pausa tattica se non è l'ultima email
            if count < len(email_list):
                delay = random.randint(30, 60)
                print(f"    ...pausa fantasma di {delay} secondi per eludere i filtri anti-spam...")
                time.sleep(delay)

        server.quit()
        print("\n[*] GIOVANNI 2.0 PROTOCOL COMPLETE. Le macchine hanno fatto il loro lavoro.")

    except Exception as e:
        print(f"\n[!] ERRORE DI SISTEMA: {e}")

if __name__ == "__main__":
    # Assicurati che pippo.csv sia nella stessa cartella!
    target_emails = pulisci_e_estrai('pippo.csv')
    esegui_attacco_smtp(target_emails)
