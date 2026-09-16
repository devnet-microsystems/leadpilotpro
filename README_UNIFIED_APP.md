# Sovereign AI Overseer — Applicazione unica per macOS M1

L’applicazione locale è avviata da un solo file:

```text
run_growth_pipeline.command
```

Questo launcher installa il necessario sul Mac, avvia la ricerca di mercato pubblica da query autorizzate, raccoglie contatti business pubblici a ruolo dai siti consentiti, li porta in una coda locale, permette una review manuale e invia solo piccoli batch approvati dal tuo account SMTP.

> **Non serve lanciare gli script Python uno alla volta.** Il launcher li coordina internamente. Per l’invio, il mittente è la casella configurata da te in `.env`; le risposte arrivano alla casella impostata in `OUTREACH_REPLY_TO` e quindi nella tua normale posta elettronica.

## Primo avvio su Mac Apple Silicon

Scarica ed estrai l’archivio nella tua cartella Home. Poi apri **Terminale** e inserisci:

```bash
cd ~/public_business_lead_collector
chmod +x run_growth_pipeline.command
./run_growth_pipeline.command
```

Al primo avvio il programma crea un ambiente Python locale `.venv`, installa Playwright, scarica Chromium compatibile e crea tre file di configurazione da esempi: `.env`, `market_research_queries.csv` e `seed_sites.csv`.

| File | Cosa configuri | Quando serve |
| --- | --- | --- |
| `.env` | SMTP, mittente, reply-to, casella opt-out, nome/sito azienda, limiti | Prima dell’invio reale |
| `market_research_queries.csv` | Query aziendali generiche per la ricerca pubblica | Per l’opzione 2 |
| `seed_sites.csv` | URL aziendali già noti e autorizzati | Per l’opzione 3 |
| `templates/agency_intro.txt` | Oggetto e corpo email | Prima della preview o invio |

Per modificare i file su macOS puoi usare `nano`, TextEdit o VS Code. La voce 4 del menu ricorda le posizioni da modificare.

## Menu dell’applicazione

| Opzione | Operazione |
| --- | --- |
| 1 | Installa o verifica l’ambiente locale Python/Playwright |
| 2 | Ricerca di mercato da query DuckDuckGo e importazione nella coda |
| 3 | Raccolta da URL aziendali già noti e importazione nella coda |
| 4 | Promemoria dei file da modificare |
| 5 | Visualizza la coda di prospect da revisionare |
| 6 | Approva un singolo prospect con una ragione fattuale e pubblica |
| 7 | Mostra una preview di email; non invia nulla |
| 8 | Invia da uno a cinque messaggi già approvati, solo dopo aver digitato `SEND` |
| 9 | Inserisce opt-out o esclusione nella suppression list |
| 10 | Mostra stato della pipeline, CSV e log |
| 11 | Chiude l’applicazione |

## Flusso consigliato

1. Avvia il file `.command` e completa l’opzione 1.
2. Configura `.env` con una casella business dedicata e autenticata; non usare la password principale dell’account se il provider offre password per app o OAuth.
3. Aggiorna `market_research_queries.csv` con un numero piccolo di query aziendali pertinenti, ad esempio “Top Web Agencies London” o “Luxury Real Estate Developers Miami”.
4. Scegli l’opzione 2. Il modulo consulta una pagina di risultati per query, attende tra le query e visita al massimo dieci risultati esterni per query, nel rispetto di `robots.txt`.
5. Scegli l’opzione 5 e controlla ogni azienda, URL e email. Approva soltanto record realmente pertinenti con l’opzione 6.
6. Scegli l’opzione 7 per controllare il testo finale. Solo dopo puoi selezionare l’opzione 8 e digitare `SEND`.
7. Le risposte arrivano nella posta impostata da `OUTREACH_REPLY_TO`. Per ogni opt-out, bounce o richiesta negativa usa subito l’opzione 9.

## Limiti intenzionali e protezioni

La ricerca evita Google e LinkedIn automation, non esegue bypass di CAPTCHA, non usa proxy, non ruota user-agent e non raccoglie email personali. Accetta solo email business a ruolo rese pubbliche, come `sales@`, `security@`, `partners@` o `hello@`. Se un sito nega il crawler tramite `robots.txt`, il file non è leggibile o appare un blocco/CAPTCHA, viene ignorato.

L’applicazione non invia automaticamente a tutti gli indirizzi raccolti. La review, l’approvazione del singolo prospect, la preview e la conferma `SEND` sono controlli necessari per prevenire invii inappropriati e proteggere reputazione e conformità. Google raccomanda autenticazione del dominio, crescita graduale dell’invio, contenuto identificabile e opt-out semplice; SPF, DKIM e DMARC sono richiesti per mittenti bulk verso Gmail.[1]

## File e dati locali

| File | Contenuto |
| --- | --- |
| `public_business_leads.csv` | Risultato progressivo della ricerca pubblica da query |
| `b2b_enterprise_leads.csv` | Risultato progressivo da URL aziendali già noti |
| `outreach_queue.sqlite3` | Coda locale, stato approval, invii e suppression list |
| `public_osint_audit.jsonl` | Audit della ricerca pubblica |
| `lead_collector_audit.jsonl` | Audit della raccolta da URL diretti |
| `outreach_audit.jsonl` | Audit importazione, invii ed esclusioni |

La cartella resta sul tuo Mac. Mantieni privato il file `.env`: contiene credenziali SMTP e non deve essere inviato o caricato in repository pubblici.

## Referenze

[1]: https://support.google.com/mail/answer/81126?hl=en "Google — Email sender guidelines"
