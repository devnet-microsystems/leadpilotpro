# Launcher unico per macOS

Il file `run_growth_pipeline.command` unisce in un unico menu locale quattro passaggi: installazione, raccolta da URL aziendali inseriti da te, importazione nel database outreach e invio di piccoli batch già approvati tramite il tuo account SMTP.

> Il launcher non esegue Google Dorks, non fa scraping LinkedIn, non aggira CAPTCHA né invia automaticamente a qualunque email trovata. Raccoglie soltanto da siti aziendali presenti in `seed_sites.csv`, rispetta `robots.txt`, importa solo email business a ruolo pubblicate e richiede approvazione per ogni prospect prima dell’invio.

## Primo avvio

Dopo avere estratto la cartella sul Mac, apri Terminale e lancia:

```bash
cd ~/public_business_lead_collector
chmod +x run_growth_pipeline.command
./run_growth_pipeline.command
```

Puoi anche fare doppio clic sul file `.command` nel Finder dopo averlo reso eseguibile. Il primo avvio crea `.venv`, installa le dipendenze Python, scarica Chromium per Playwright, crea `.env` da `.env.example` e crea `seed_sites.csv` dall’esempio.

## Configurazione una sola volta

Prima di qualsiasi invio reale, modifica questi due file:

```bash
cd ~/public_business_lead_collector
nano .env
nano seed_sites.csv
```

In `.env` inserisci la tua casella SMTP business, una password per app o credenziale SMTP autorizzata, il reply-to e la casella per unsubscribe. In `seed_sites.csv` inserisci solo URL di aziende che sei autorizzato a esaminare.

| File | Da configurare |
| --- | --- |
| `.env` | SMTP, mittente, reply-to, unsubscribe, nome e sito della tua azienda, limiti giornalieri |
| `seed_sites.csv` | URL aziende e un eventuale `company_hint` |
| `templates/agency_intro.txt` | Testo dell’email e oggetto trasparente |

Non inviare mai `.env` a terzi e non caricarlo su repository pubblici.

## Uso quotidiano

Il menu propone questa sequenza:

| Opzione | Azione |
| --- | --- |
| 2 | Visita gli URL consentiti, estrae email business a ruolo pubblicate e importa le righe nel database locale |
| 3 | Mostra la coda `pending_review` |
| 4 | Approva manualmente un prospect e annota una ragione pubblica e fattuale |
| 5 | Mostra anteprima del messaggio senza inviare email |
| 6 | Invia da uno a cinque messaggi già approvati dopo una conferma testuale `SEND` |
| 7 | Inserisce una richiesta di opt-out o un’esclusione nella suppression list permanente |
| 8 | Mostra lo stato della pipeline e le posizioni dei file |

Le risposte arrivano normalmente alla casella impostata in `OUTREACH_REPLY_TO`, quindi le vedrai nella tua posta. I bounce e le richieste di stop devono essere inseriti senza ritardo con l’opzione 7; il launcher non legge o interpreta automaticamente la tua inbox.

## Perché non è completamente autonomo

Il processo può essere eseguito con un solo launcher e inviare dal tuo account, ma non è corretto né prudente fare in modo che trovi e invii automaticamente a tutte le email scoperte. L’approvazione del prospect e la conferma `SEND` evitano che un errore di scraping, una pagina non pertinente o una richiesta di opt-out ignorata danneggino il dominio, il rapporto commerciale o la conformità.

Google richiede autenticazione del dominio per l’invio a Gmail e raccomanda crescita graduale, mittente identificabile, disiscrizione semplice e monitoraggio della reputazione; SPF, DKIM e DMARC sono requisiti per mittenti bulk.[1]

## Processo in background

Il launcher è interattivo per scelta, perché richiede review e conferma prima dell’invio. Per lanciare solo la fase di raccolta non interattiva puoi usare direttamente il collector; per l’invio, esegui il launcher in primo piano così puoi controllare la lista e gli indirizzi prima che i messaggi escano dal tuo account.

## Referenze

[1]: https://support.google.com/mail/answer/81126?hl=en "Google — Email sender guidelines"
