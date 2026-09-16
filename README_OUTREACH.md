# Controlled B2B Outreach Sender

`outreach_sender.py` collega il CSV prodotto dal collector a una coda SQLite locale. Non invia automaticamente a tutte le righe: importa i contatti business a ruolo, richiede un’approvazione per ciascun record e invia esclusivamente record `approved` non presenti nella suppression list.

> Lo script è progettato per outreach B2B limitato e tracciabile, non per invii massivi. Un indirizzo email pubblico non equivale da solo a un’autorizzazione universale al marketing. Prima di inviare, verifica le regole applicabili ai Paesi coinvolti, configura il dominio in modo corretto e conserva la fonte del contatto.

## Protezioni incluse

| Protezione | Comportamento |
| --- | --- |
| Email ammesse | Solo indirizzi business a ruolo presenti nel CSV: `hello@`, `sales@`, `partners@`, `security@` e simili |
| Approvazione | Ogni prospect inizia come `pending_review`; l’invio legge solo `approved` |
| Suppression list | Un indirizzo soppresso non viene importato o inviato di nuovo |
| Invio | SMTP con TLS obbligatorio; nessun invio in chiaro |
| Conferma | Il sender è in preview per default; l’invio reale richiede sia `--send` sia `--confirm-send` |
| Volume | Limite giornaliero configurabile da 1 a 25; default 5 |
| Frequenza | Pausa casuale prudente da 90 a 150 secondi, configurabile solo fra 60 e 600 secondi |
| Trasparenza | Mittente, reply-to e istruzioni di opt-out nel messaggio; `List-Unsubscribe` con indirizzo `mailto:` |
| Audit | SQLite locale e file `outreach_audit.jsonl` con import, approvazioni, invii, errori e suppression |

## 1. Configurare il mittente

Usa una casella business dedicata, per esempio `outreach@tuodominio.com`, e verifica prima che il dominio abbia SPF, DKIM e DMARC. Non inserire password reali nel codice o nel repository.

Nel Terminale:

```bash
cd ~/public_business_lead_collector
cp .env.example .env
chmod 600 .env
nano .env
```

Sostituisci i valori di esempio con quelli del provider SMTP autorizzato. Per un account con autenticazione a due fattori, usa una password per app oppure un meccanismo SMTP/OAuth supportato dal provider, mai la password principale dell’account.

Ogni volta che avvii il sender, carica le variabili nel Terminale corrente:

```bash
cd ~/public_business_lead_collector
set -a
source .env
set +a
```

## 2. Importare il CSV del collector

Il CSV deve avere esattamente le colonne `Target URL`, `Extracted Name/Title`, `Verified Email`.

```bash
source .venv/bin/activate
python outreach_sender.py import \
  --csv b2b_enterprise_leads.csv \
  --campaign wordpress-agencies-pilot
```

L’importatore scarta automaticamente righe senza email business a ruolo, email webmail personali, duplicati e contatti già soppressi.

## 3. Revisionare e approvare manualmente

Visualizza la coda:

```bash
python outreach_sender.py list --status pending_review
```

Per ciascun record, verifica il sito, la fonte e il motivo del contatto. Approva solo dopo questa verifica. Il campo `--reason` deve riferirsi a un fatto pubblico, non a un’inferenza su persone o vulnerabilità.

```bash
python outreach_sender.py approve \
  --id 1 \
  --reason "Il sito aziendale dichiara servizi di manutenzione WordPress per clienti B2B."
```

Puoi vedere gli approvati:

```bash
python outreach_sender.py list --status approved
```

## 4. Personalizzare il messaggio

Modifica il file `templates/agency_intro.txt`. Mantieni identità chiara, spiegazione fedele del prodotto e opt-out. Sono ammessi questi placeholder:

| Placeholder | Valore |
| --- | --- |
| `{company_name}` | Titolo/nome estratto dal CSV |
| `{target_url}` | Sito del prospect |
| `{reason_for_contact}` | Ragione pubblica inserita al momento dell’approvazione |
| `{company}` | Nome della tua azienda da `.env` |
| `{website}` | Sito della tua azienda da `.env` |
| `{reply_to}` | Indirizzo per le risposte |
| `{unsubscribe_address}` | Casella che riceve le richieste di disiscrizione |

Il template deve avere questa struttura:

```text
Subject: Oggetto del messaggio

Corpo dell’email in testo semplice.
```

## 5. Fare una preview senza inviare

Il comando seguente non invia email e non cambia lo stato dei record. Mostra la versione finale del messaggio per gli account approvati.

```bash
set -a; source .env; set +a
python outreach_sender.py send \
  --campaign wordpress-agencies-pilot \
  --template templates/agency_intro.txt \
  --limit 2
```

## 6. Inviare un batch reale e limitato

Dopo una preview corretta, l’invio reale richiede due flag distinti. Il valore di `OUTREACH_DAILY_LIMIT` nella `.env` resta il limite massimo anche se `--limit` è maggiore.

```bash
set -a; source .env; set +a
python outreach_sender.py send \
  --campaign wordpress-agencies-pilot \
  --template templates/agency_intro.txt \
  --limit 2 \
  --send \
  --confirm-send
```

Lo script usa TLS sul porto SMTP configurato, invia solo due prospect già approvati, registra il Message-ID e aspetta tra un invio e il successivo. In caso di errore SMTP non segna il record come inviato; salva invece un errore nel database e nel log.

## 7. Gestire risposte, bounce e opt-out

Quando ricevi una richiesta di stop, una risposta negativa o un bounce, aggiungi subito l’indirizzo alla suppression list:

```bash
python outreach_sender.py suppress \
  --email hello@azienda.example \
  --reason "Requested opt-out by email on 2026-08-26"
```

Questo blocca ogni futuro import e invio verso quell’indirizzo. Il sender non legge la tua inbox in automatico: per implementare un inbound processor serve una seconda integrazione IMAP/OAuth o webhook del provider, che va progettata separatamente.

## 8. Esecuzione in background

Per batch già approvati e già verificati:

```bash
cd ~/public_business_lead_collector
mkdir -p logs
nohup sh -c 'set -a; source .env; set +a; .venv/bin/python outreach_sender.py send --campaign wordpress-agencies-pilot --template templates/agency_intro.txt --limit 2 --send --confirm-send' \
  > logs/outreach.log 2>&1 &
echo $! > outreach_sender.pid
```

Controlla l’esecuzione e il log:

```bash
ps -p "$(cat outreach_sender.pid)"
tail -f logs/outreach.log
```

Per arrestare il processo:

```bash
kill "$(cat outreach_sender.pid)"
rm -f outreach_sender.pid
```

## Limiti intenzionali

Lo script non acquista liste, non estrae email personali, non esegue dork Google, non automatizza LinkedIn, non aggira CAPTCHA, non ruota user-agent e non tenta di mascherare l’origine del traffico. Non invia follow-up automatici o email a ogni riga importata. Un eventuale follow-up va costruito come funzionalità separata, con stop automatico per risposta, bounce o opt-out e approvazione iniziale della sequenza.

Google raccomanda per l’invio a Gmail un dominio autenticato e crescita graduale dei volumi; per mittenti bulk richiede SPF, DKIM e DMARC, oltre a meccanismi di disiscrizione.[1]

## Referenze

[1]: https://support.google.com/mail/answer/81126?hl=en "Google — Email sender guidelines"
