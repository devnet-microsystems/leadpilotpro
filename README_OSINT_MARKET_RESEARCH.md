# Public OSINT Market Research Aggregator

`public_osint_market_research.py` è un modulo di **market research pubblico**. Parte da una lista limitata di query fornite in un CSV, consulta una sola pagina HTML di risultati DuckDuckGo per query e visita poi solo URL esterni che rappresentano potenziali siti aziendali.

Dalle homepage e da un massimo di due pagine interne Contact/About/Team, registra in `public_business_leads.csv` unicamente email business a ruolo rese pubbliche, per esempio `sales@`, `partners@`, `security@` o `hello@`.

> Il modulo non è un motore di scraping massivo. Non automatizza Google o LinkedIn, non risolve CAPTCHA, non ruota user-agent, non usa proxy, non raccoglie email personali e non visita risultati da social network, motori di ricerca o directory escluse.

## Installazione

Il progetto usa le stesse dipendenze del collector precedente. Se la cartella contiene già `.venv`, bastano:

```bash
cd ~/public_business_lead_collector
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Creare le query

Copia l’esempio e modifica solo le query che rappresentano il tuo perimetro di ricerca aziendale:

```bash
cd ~/public_business_lead_collector
cp market_research_queries.example.csv market_research_queries.csv
nano market_research_queries.csv
```

Il formato è intenzionalmente semplice:

```csv
query
Top Web Agencies London
Luxury Real Estate Developers Miami
```

Usa query aziendali generiche e rilevanti. Non usare richieste orientate a profili personali, email individuali o piattaforme che non autorizzano l’automazione.

## Esecuzione

Avvia prima con browser visibile:

```bash
python public_osint_market_research.py \
  --queries market_research_queries.csv \
  --output public_business_leads.csv \
  --headed
```

Dopo la verifica, puoi eseguirlo senza finestra:

```bash
python public_osint_market_research.py \
  --queries market_research_queries.csv \
  --output public_business_leads.csv
```

Per ridurre ulteriormente il perimetro:

```bash
python public_osint_market_research.py \
  --queries market_research_queries.csv \
  --results-per-query 5 \
  --max-contact-pages-per-site 1 \
  --output public_business_leads.csv
```

## File prodotti

| File | Contenuto |
| --- | --- |
| `public_business_leads.csv` | URL aziendale, titolo estratto, email corporate a ruolo, pagina fonte, query e data UTC |
| `public_osint_state.sqlite3` | Stato locale per deduplicare gli stessi risultati fra esecuzioni |
| `public_osint_audit.jsonl` | Audit degli URL scoperti, skip robots, blocchi, errori e record salvati |

Il campo **Verified Corporate Email** significa soltanto che lo script ha visto l’indirizzo nel markup HTML pubblico o in un link `mailto:` della pagina fonte. Non verifica che la casella esista né che il contatto abbia dato consenso a ricevere marketing.

## Limiti e controlli

| Controllo | Comportamento |
| --- | --- |
| Ritmo SERP | Una pagina risultati per query; attesa casuale di 30–60 secondi prima della query successiva |
| Ritmo siti aziendali | Attesa casuale di 8–15 secondi fra pagine |
| `robots.txt` | Se vieta il collector o non è raggiungibile, il sito viene ignorato |
| CAPTCHA/blocchi | Il sito o le query restanti vengono ignorati senza bypass o retry aggressivi |
| Email | Solo local-part a ruolo predefinite e domini non webmail; nessun indirizzo nominativo |
| Pagine | Homepage più al massimo due pagine interne Contact/About/Team per sito |

L’uso successivo delle informazioni raccolte, compreso il direct marketing, deve rispettare le regole applicabili per la giurisdizione e il tipo di destinatario. I messaggi commerciali devono identificare chiaramente il mittente e offrire un opt-out semplice. Google richiede l’autenticazione del dominio per i mittenti verso Gmail e raccomanda crescita graduale e monitoraggio della reputazione.[1]

## Referenze

[1]: https://support.google.com/mail/answer/81126?hl=en "Google — Email sender guidelines"
