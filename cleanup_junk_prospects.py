#!/usr/bin/env python3
"""
cleanup_junk_prospects.py

Trova i prospect con indirizzo email strutturalmente inutilizzabile (chiavi Sentry/Bugsnag,
domini segnaposto o riservati, noreply, fixture di test...) usando lo stesso modulo
`email_hygiene.py` gia' integrato in approvazione e invio.

DI SOLA LETTURA per impostazione predefinita: stampa solo un report, non modifica il database.
Nessun invio email: questo script non tocca SMTP.

Uso:
    python3 cleanup_junk_prospects.py                      # report (sola lettura)
    python3 cleanup_junk_prospects.py --db altro.sqlite3    # su un altro file
    python3 cleanup_junk_prospects.py --apply               # mette in quarantena (status='rejected')
    python3 cleanup_junk_prospects.py --apply --only-status sent   # limita l'azione a un solo status

--apply modifica SOLO lo status e la rejection_reason dei prospect individuati come "junk".
Non cancella righe, non tocca prospect gia' 'rejected', non manda nessuna email.
"""
from __future__ import annotations

import argparse
import sqlite3
import db_connector
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from email_hygiene import junk_reason  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default="outreach_queue.sqlite3", help="Percorso del database (default: outreach_queue.sqlite3)")
    parser.add_argument("--apply", action="store_true", help="Applica la quarantena (default: solo report)")
    parser.add_argument("--only-status", default=None,
                         help="Limita ai prospect con questo status (es. 'sent', 'approved'). Default: tutti tranne 'rejected'.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database non trovato: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row

    where = "status != 'rejected'"
    params: tuple = ()
    if args.only_status:
        where = "status = ?"
        params = (args.only_status,)

    rows = conn.execute(f"SELECT id, business_email, status, campaign_id FROM prospects WHERE {where}", params).fetchall()

    junk = [(r, junk_reason(r["business_email"])) for r in rows]
    junk = [(r, reason) for r, reason in junk if reason]

    if not junk:
        print(f"Nessun indirizzo inutilizzabile trovato su {len(rows)} prospect esaminati.")
        conn.close()
        return

    by_reason = Counter(reason for _, reason in junk)
    by_status = Counter(r["status"] for r, _ in junk)

    print(f"Esaminati {len(rows)} prospect, {len(junk)} con indirizzo inutilizzabile.\n")
    print("Per motivo:")
    for reason, n in by_reason.most_common():
        print(f"  {n:4d}  {reason}")
    print("\nPer status attuale:")
    for status, n in by_status.most_common():
        print(f"  {n:4d}  {status}")

    print("\nEsempi (max 25):")
    for r, reason in junk[:25]:
        print(f"  #{r['id']:5d}  {r['status']:10s}  {reason:22s}  {r['business_email']}")
    if len(junk) > 25:
        print(f"  ... e altri {len(junk) - 25}")

    if not args.apply:
        print("\nNessuna modifica applicata (modalita' report). Rilancia con --apply per mettere in quarantena "
              "(status='rejected') questi prospect. Nessuna email viene inviata da questo script.")
        conn.close()
        return

    ids = [r["id"] for r, _ in junk]
    marks = ",".join("?" for _ in ids)
    reasons = {r["id"]: reason for r, reason in junk}
    for pid in ids:
        conn.execute("UPDATE prospects SET status='rejected', rejection_reason=? WHERE id=?", (reasons[pid], pid))
    conn.commit()
    print(f"\n{len(ids)} prospect messi in quarantena (status='rejected'). Nessun'altra riga e' stata toccata.")
    conn.close()


if __name__ == "__main__":
    main()
