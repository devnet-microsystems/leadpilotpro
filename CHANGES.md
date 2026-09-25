# LeadPilot Pro — modifiche finali

**Versione corretta di questo pacchetto.** La prima versione conteneva solo i file
che avevo effettivamente modificato (17 file) — corretto se sovrapposti file-per-file,
ma se sostituisci intere cartelle (`product_intelligence/`, `static/`, `osint_engine/`,
`tests/`) invece di unirle, quella versione cancellava i file che non avevo toccato
(es. `product_intelligence/store.py`, `static/style.css`, `osint_engine/normalization.py`)
causando `ModuleNotFoundError`. Questa versione ha quelle 4 cartelle COMPLETE — tutto il
contenuto originale piu' le mie correzioni — quindi ora sostituire l'intera cartella e'
sicuro. I file alla radice (`web_server.py`, `outreach_sender.py`, ecc.) restano solo
quelli modificati o nuovi, come prima. Nessun file `.sqlite3`, nessun log: il tuo
database e i tuoi log reali non sono toccati da questa consegna.

## Come installare
1. Chiudi il server se e' in esecuzione.
2. Fai una copia di sicurezza della cartella attuale (per sicurezza, non e' necessaria).
3. Copia il contenuto di questo pacchetto sopra la tua installazione esistente: i file
   alla radice si sovrascrivono uno per uno; le cartelle `static/`, `tests/`,
   `osint_engine/`, `product_intelligence/` puoi sostituirle per intero (sono complete)
   oppure unirle file-per-file, indifferentemente — funziona in entrambi i modi.
4. Riavvia il server. Al primo avvio da un DB gia' esistente non cambia nulla; su un DB nuovo
   verra' creato tutto lo schema mancante e un file `FIRST_LOGIN_PASSWORD.txt` con le
   credenziali iniziali (vedi sotto).
5. `pip install -r requirements.txt` non serve: nessuna nuova dipendenza.

## Bug corretti

- **Tab "Sales Campaigns" non si apriva.** Un selettore troppo rigido nel cambio-tab si
  spezzava sulla voce di menu. Riscritta anche l'interfaccia della tab per combaciare con le
  risposte reali delle API (prima leggeva campi che il backend non restituiva).
- **Il PUT dei messaggi rifiutava `{{ nome }}` con gli spazi** e non controllava l'oggetto,
  solo il corpo.
- **Rigenerare una campagna approvata la sovrascriveva.** Ora una campagna non in bozza
  (`DRAFT`) viene lasciata intatta e la generazione viene saltata.
- **L'AI poteva restituire un numero di email diverso da quello richiesto**, bloccando la
  campagna (non piu' ne' approvabile ne' modificabile). Ora l'eccesso viene scartato, il
  difetto fa fallire la generazione con un messaggio chiaro invece di lasciare la campagna
  in un limbo.
- **Nessun collegamento tra le sequenze P5.3 e il sender.** Nuovo bottone "Export to
  Outreach" nella tab Sales Campaigns: converte le email approvate in template e campagne
  del sender esistente. Non invia nulla da solo.
- **Installazione da zero rotta.** Su un database nuovo 7 endpoint su 22 rispondevano
  errore 500 perche' mancavano 13 tabelle (create solo da script di migrazione lanciati a
  mano in passato). Ora lo schema completo viene creato automaticamente all'avvio.
- **Percorsi assoluti del tuo Mac** in `imap_poller.py` e `analyze_baseline.py` — rimossi,
  ora relativi alla cartella del progetto.
- **Fallback Python mancante.** L'invio in background e la ricerca OSINT presumevano
  sempre un ambiente virtuale `.venv`; se assente, l'invio falliva senza spiegazione. Ora,
  se `.venv` non esiste, usano l'interprete Python corrente.
- **Password admin fissa `admin`/`admin` su ogni installazione nuova.** Ora viene generata
  casualmente e scritta una volta sola in `FIRST_LOGIN_PASSWORD.txt` accanto al database.
  Cambiala dopo il primo accesso e cancella il file.
- **Bug trovato mentre collaudavo la nuova funzione "Address Book" (vedi sotto): l'invio in
  background falliva sempre, in silenzio.** Due costanti (`outreach_audit.jsonl` e
  `campaign_send.log`) erano fissate alla cartella del codice invece di seguire il
  database, e un riferimento rimasto a una costante che avevo gia' rimosso in una modifica
  precedente in questa stessa sessione causava un errore non gestito in ogni invio avviato
  da "Address Book" o da "Quick Send": la richiesta tornava "ok" all'utente ma nessuna
  email veniva davvero processata, e i prospect restavano bloccati su "approved" senza
  nessun messaggio d'errore visibile. Corretto e coperto da un test automatico dedicato.

## Nuova voce di menu: "Address Book"

Sotto il menu Outreach. Mostra tutti i contatti gia' noti (deduplicati, esclusi quelli
gia' rifiutati o disiscritti), con una casella di ricerca per email/azienda e paginazione
25 per pagina. Seleziona quelli che vuoi, poi:

- **Blacklist Selected** — li blacklista, non riceveranno piu' nulla da nessuna campagna.
- **Send Selected Now** — li sposta sulla campagna che scegli dal menu a tendina e avvia
  subito l'invio (stesso meccanismo del riquadro "Manual Quick Send" li' accanto: se un
  contatto era gia' su un'altra campagna, o era gia' stato rifiutato o gia' inviato,
  passa comunque su quella nuova). L'invio effettivo passa sempre dal filtro anti-indirizzi-
  inutilizzabili descritto sotto, anche per contatti gia' "approved" da tempo.

Riusa endpoint gia' esistenti nel tuo backend (`/api/contacts`, `/api/contacts/blacklist`,
`/api/quick_send`): nessuna nuova rotta API per questa funzione.

## Igiene indirizzi email (nuovo: `email_hygiene.py`)

Riconosce indirizzi strutturalmente inutilizzabili: chiavi di tracciamento errori
(Sentry, Bugsnag e simili), domini segnaposto o riservati (`example.com`, `dummy.com`,
`musterfirma.de`...), caselle di sistema (`noreply@`...), indirizzi generati da test
(suffisso con timestamp). Applicato in tre punti, dal piu' al meno permissivo:

1. **Raccolta OSINT** (`osint_engine/quality.py`) — questi indirizzi vengono classificati
   `INVALID` e quindi scartati alla fonte, come gia' accadeva per i domini disposable.
2. **Approvazione** — approvare un prospect con indirizzo inutilizzabile lo rifiuta invece
   di approvarlo (endpoint singolo, di massa, e dalla tab Sales Campaigns).
3. **Invio** — ultima linea di difesa: anche un indirizzo approvato in passato (prima di
   questa modifica) viene scartato appena prima di essere inviato.

## Script di pulizia (nuovo: `cleanup_junk_prospects.py`)

Di sola lettura per impostazione predefinita — non tocca il database finche' non gli dai
`--apply`:

```
python3 cleanup_junk_prospects.py                # solo report
python3 cleanup_junk_prospects.py --apply         # mette in quarantena (status='rejected')
```

Sul tuo database, alla stesura di questa nota, segnala 80 indirizzi inutilizzabili su 200
prospect (62 approved, 18 sent, il resto in altri stati). Nessuna riga viene cancellata,
nessuna email viene inviata da questo script.

## Test

`pytest tests/` — 68 passed, 7 skipped (nessun test invia email vere: SMTP e' disabilitato
sotto pytest, e comunque i test lavorano su database temporanei, mai sul tuo). La nuova
`tests/test_p6_finalization.py` copre: igiene email, il sender che non seleziona mai
indirizzi inutilizzabili, l'agente che rispetta il numero di email richiesto, il
convertitore verso il sender legacy, il flusso completo generazione→approvazione→export,
un'installazione da zero senza errori 500, e la regressione dell'invio in background
descritta sopra.

## Cose che NON ho toccato

- Il tuo database (`outreach_queue.sqlite3`) e i tuoi log reali (`outreach_audit.jsonl`,
  `campaign_send.log`) non sono in questa consegna e non sono stati modificati.
- La tab "Query Studio" ha due pulsanti (`Launch Campaign`, il filtro di "Pending Review")
  che chiamano funzioni non definite nel JS — bug preesistente nell'archivio originale,
  non collegato a quanto mi hai chiesto in questa sessione. Non l'ho toccato: dimmelo se
  vuoi che lo sistemi.
