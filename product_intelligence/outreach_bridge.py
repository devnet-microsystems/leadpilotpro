"""
product_intelligence/outreach_bridge.py

Ponte ESPLICITO tra una campagna prodotto APPROVED (P5.3) e il sender legacy.

Il sender legacy usa `str.format` con un set fisso di campi ({company_name}, {reason_for_contact}, ...)
e una campagna = (nome, nome del template). Le sequenze P5.3 usano invece {{first_name}}, {{role}}, ...
Questo modulo converte ogni email della sequenza in un template legacy valido e crea una campagna
legacy per ogni step, cosi' compaiono nelle tab Templates / Campaigns / Sender Queue.

Garanzie:
  * NON invia nulla e non tocca prospect: crea solo righe in `templates` e `campaigns`.
  * Idempotente: template/campagne gia' esistenti non vengono mai sovrascritti (potresti averli modificati).
  * Solo campagne APPROVED.
"""
from __future__ import annotations

import re
import sqlite3
import db_connector
from datetime import datetime, timezone
from string import Formatter
from typing import Any, Dict, List

from .sales_campaign_store import get_product_campaign

# Campi che il sender legacy sa risolvere (vedi outreach_sender.read_template / build_message)
LEGACY_FIELDS = {
    "company_name", "domain", "target_url", "reason_for_contact",
    "company", "website", "reply_to", "unsubscribe_address",
}

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

# placeholder P5.3 -> token legacy
_MAP = {
    "company_name": "{company_name}",
    "why_matched": "{reason_for_contact}",
    "matched_signal": "{reason_for_contact}",
    # I prospect legacy sono caselle di ruolo (info@, sales@): nessun nome di persona. Il nome azienda
    # e' l'unico fallback neutro rispetto alla lingua ("Hola Acme," / "Ciao Acme," / "Hi Acme,").
    "first_name": "{company_name}",
}
# placeholder senza alcun dato disponibile nel modello legacy: vengono rimossi e segnalati
_DROPPED = {"last_name", "role", "industry", "market"}

_FOOTERS = {
    "en": 'To stop receiving these emails, reply "unsubscribe" or write to {unsubscribe_address}.',
    "it": 'Per non ricevere piu\' queste email rispondi "unsubscribe" o scrivi a {unsubscribe_address}.',
    "es": 'Para dejar de recibir estos correos, responde "unsubscribe" o escribe a {unsubscribe_address}.',
    "fr": 'Pour ne plus recevoir ces e-mails, repondez "unsubscribe" ou ecrivez a {unsubscribe_address}.',
    "de": 'Wenn Sie keine weiteren E-Mails erhalten moechten, antworten Sie "unsubscribe" oder schreiben Sie an {unsubscribe_address}.',
}
_LANG_CODES = {"english": "en", "italian": "it", "spanish": "es", "french": "fr", "german": "de"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape_literal(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def convert_text(text: str, dropped: set) -> str:
    """Converte {{placeholder}} P5.3 in campi legacy e mette in sicurezza le graffe letterali."""
    out: List[str] = []
    pos = 0
    for m in _PLACEHOLDER.finditer(text):
        out.append(_escape_literal(text[pos:m.start()]))
        name = m.group(1)
        if name in _MAP:
            out.append(_MAP[name])
        elif name in _DROPPED:
            dropped.add(name)
        else:
            raise ValueError(f"Unsupported placeholder '{name}'")
        pos = m.end()
    out.append(_escape_literal(text[pos:]))
    return "".join(out)


def build_legacy_template(subject: str, body: str, language: str = "English", add_footer: bool = True):
    """Ritorna (contenuto_template, placeholder_rimossi). Solleva ValueError se il risultato non e' valido."""
    dropped: set = set()
    subject_c = re.sub(r"\s+", " ", convert_text(subject, dropped)).strip()
    body_c = convert_text(body, dropped).strip()
    if dropped:
        # ripulisce gli spazi lasciati da un placeholder rimosso ("Hi  ," -> "Hi,")
        for _ in (0,):
            subject_c = re.sub(r"\s+([,.;:!?])", r"\1", subject_c)
            body_c = re.sub(r"[ \t]{2,}", " ", body_c)
            body_c = re.sub(r"[ \t]+([,.;:!?])", r"\1", body_c)
    if not subject_c or not body_c:
        raise ValueError("Subject and body cannot be empty after conversion")

    if add_footer:
        code = _LANG_CODES.get((language or "English").strip().lower(), "en")
        body_c += "\n\n--\n{company} - {website}\n" + _FOOTERS.get(code, _FOOTERS["en"])

    content = f"Subject: {subject_c}\n\n{body_c}"

    used = {f for _, f, _, _ in Formatter().parse(content) if f}
    unknown = used - LEGACY_FIELDS
    if unknown:
        raise ValueError(f"Template uses fields unsupported by the sender: {sorted(unknown)}")
    return content, dropped


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", " ", text or "").strip()


def export_to_outreach(db_path: str, product_campaign_id: int, add_footer: bool = True) -> Dict[str, Any]:
    camp = get_product_campaign(db_path, product_campaign_id)
    if not camp:
        raise LookupError("Campaign not found")
    if camp["status"] not in ("APPROVED", "ACTIVE"):
        raise PermissionError(f"Only APPROVED campaigns can be exported (status is {camp['status']})")
    msgs = camp.get("messages", [])
    if not msgs or len(msgs) != camp["sequence_length"]:
        raise ValueError("Sequence is incomplete")

    # Prima converte tutto (cosi' un errore non lascia un export a meta')
    prepared = []
    all_dropped: set = set()
    for m in msgs:
        content, dropped = build_legacy_template(m["subject"], m["body"], camp.get("language", "English"), add_footer)
        all_dropped |= dropped
        n = m["sequence_order"]
        delay = int(m.get("delay_days") or 0)
        label = _slug(f"{camp.get('target_segment', '')} {camp.get('buyer_role', '')} {camp.get('market', '')}")
        prepared.append({
            "template_name": f"pc{camp['id']}_email{n}.txt",
            "campaign_name": f"PC{camp['id']} Email {n}" + (f" (+{delay}d)" if delay else "") + (f" - {label}" if label else ""),
            "content": content,
            "delay_days": delay,
        })

    conn = db_connector.get_connection(db_path)
    try:
        created, existing = [], []
        now = _utc_now()
        for p in prepared:
            t_exists = conn.execute("SELECT 1 FROM templates WHERE name=?", (p["template_name"],)).fetchone()
            if not t_exists:
                conn.execute("INSERT INTO templates (name, content, created_at_utc) VALUES (?, ?, ?)",
                             (p["template_name"], p["content"], now))
            c_exists = conn.execute("SELECT 1 FROM campaigns WHERE name=?", (p["campaign_name"],)).fetchone()
            if not c_exists:
                conn.execute("INSERT INTO campaigns (name, template, created_at_utc) VALUES (?, ?, ?)",
                             (p["campaign_name"], p["template_name"], now))
            (existing if (t_exists and c_exists) else created).append(
                {"campaign": p["campaign_name"], "template": p["template_name"], "delay_days": p["delay_days"]})
        conn.commit()
    finally:
        conn.close()

    warnings = []
    if all_dropped:
        warnings.append(
            "No data available in the outreach model for: " + ", ".join(sorted(all_dropped)) +
            ". These placeholders were removed; review the exported templates before sending.")
    return {"created": created, "existing": existing, "warnings": warnings}
