#!/usr/bin/env python3
"""Controlled B2B Outreach Sender.

Imports role-based business emails from the lead collector CSV into a local SQLite
queue. Messages are sent only after an explicit manual approval step. It includes:
- CSV import and deduplication
- approval queue and suppression list
- daily limit and 90–150 second spacing
- TLS-only SMTP delivery
- unsubscribe/reply-to details in every message
- audit logging and dry-run by default

This is intentionally not a bulk-mail or anti-detection tool. Use it only for
lawful B2B outreach to public business contacts where you have verified an
appropriate basis to contact the company.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import smtplib
import socket
import sqlite3
import db_connector
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from string import Formatter
from typing import Iterable

from email_hygiene import junk_reason

APP_NAME = "ControlledB2BOutreach"

PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "icloud.com", "live.com",
    "me.com", "msn.com", "outlook.com", "proton.me", "protonmail.com", "yahoo.com",
}
EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}$", re.IGNORECASE)


@dataclass(frozen=True)
class MailSettings:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    from_name: str
    from_email: str
    reply_to: str
    unsubscribe_address: str
    company_name: str
    company_website: str
    daily_limit: int
    minimum_delay_seconds: int
    maximum_delay_seconds: int


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, event: str, detail: dict[str, str | int]) -> None:
        payload = {
            "timestamp_utc": utc_now(),
            "event": event,
            **detail,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


class OutreachDatabase:
    def __init__(self, path: Path) -> None:
        self.db_path = path
        self.connection = db_connector.get_connection(path, timeout=10.0, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY,
                target_url TEXT NOT NULL,
                company_name TEXT NOT NULL,
                business_email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                source_file TEXT NOT NULL,
                campaign_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending_review',
                reason_for_contact TEXT NOT NULL DEFAULT '',
                imported_at_utc TEXT NOT NULL,
                approved_at_utc TEXT,
                sent_at_utc TEXT,
                message_id TEXT,
                last_error TEXT,
                email_confidence REAL,
                confidence_type TEXT,
                company_score REAL,
                relevance_score REAL,
                research_campaign_id INTEGER,
                why_matched TEXT,
                email_quality TEXT DEFAULT 'UNKNOWN',
                qualification_status TEXT DEFAULT 'REVIEW_REQUIRED',
                rejection_reason TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                FOREIGN KEY (research_campaign_id) REFERENCES research_campaigns (id)
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                template TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS suppression_list (
                business_email TEXT PRIMARY KEY COLLATE NOCASE,
                reason TEXT NOT NULL,
                suppressed_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS send_events (
                id INTEGER PRIMARY KEY,
                prospect_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_at_utc TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(prospect_id) REFERENCES prospects(id)
            );

            CREATE TABLE IF NOT EXISTS email_archive (
                id INTEGER PRIMARY KEY,
                business_email TEXT NOT NULL,
                campaign_id INTEGER,
                sent_at_utc TEXT NOT NULL,
                message_text TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY,
                query TEXT NOT NULL,
                executed_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash BYTES NOT NULL,
                salt BYTES NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at_utc TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                message_id TEXT NOT NULL,
                received_at_utc TEXT NOT NULL,
                subject TEXT,
                body_text TEXT,
                FOREIGN KEY(prospect_id) REFERENCES prospects(id)
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                daily_limit INTEGER NOT NULL,
                scheduled_at_utc TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS prospect_product_fit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                fit_status TEXT NOT NULL,
                fit_score INTEGER DEFAULT 0,
                reason TEXT,
                matched_signals TEXT,
                missing_signals TEXT,
                negative_signals TEXT,
                evidence_source_ids TEXT,
                provider TEXT,
                model TEXT,
                evidence_reviewed_at TEXT,
                evidence_reviewed_by TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                UNIQUE(prospect_id, product_id)
            )
        """)
        for column, sql_type in (
            ("evidence_reviewed_at", "TEXT"),
            ("evidence_reviewed_by", "TEXT"),
            ("analysis_version", "TEXT"),
        ):
            try:
                self.connection.execute(
                    f"ALTER TABLE prospect_product_fit ADD COLUMN {column} {sql_type}"
                )
            except sqlite3.OperationalError:
                pass

        self.connection.commit()
        
        # Check if admin user exists, if not create default
        user_count = self.connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            import hashlib
            import os
            import secrets

            # Supporta un bootstrap esplicito tramite variabile d'ambiente Render.
            # In assenza della variabile resta il comportamento sicuro di default:
            # password casuale mai stampata nei log.
            configured_password = os.environ.get("LEADPILOT_ADMIN_PASSWORD", "").strip()
            if configured_password and len(configured_password) < 12:
                raise RuntimeError("LEADPILOT_ADMIN_PASSWORD must be at least 12 characters")
            generated_password = configured_password or secrets.token_urlsafe(15)
            salt = os.urandom(16)
            password_hash = hashlib.pbkdf2_hmac('sha256', generated_password.encode(), salt, 100000)
            self.connection.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                ("admin", password_hash, salt)
            )
            try:
                pw_file = Path(self.db_path).with_name("FIRST_LOGIN_PASSWORD.txt")
                pw_file.write_text(
                    "LeadPilot Pro - initial admin credentials\n"
                    "username: admin\n"
                    f"password: {generated_password}\n\n"
                    "Change the password after logging in, then delete this file.\n"
                )
            except OSError:
                pass  # il DB resta comunque utilizzabile; l'utente puo' recuperare la password da qui solo se il file e' stato scritto
            
            # Seed default settings from environment if possible, otherwise empty
            import os
            
            default_settings = [
                ('smtp_host', os.environ.get("SMTP_HOST", "")),
                ('smtp_port', os.environ.get("SMTP_PORT", "587")),
                ('smtp_user', os.environ.get("SMTP_USER", "")),
                ('smtp_password', os.environ.get("SMTP_PASSWORD", "")),
                ('smtp_from_email', os.environ.get("OUTREACH_FROM_EMAIL", ""))
            ]
            
            self.connection.executemany(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                default_settings
            )
            self.connection.commit()

    def get_or_create_campaign_id(self, campaign_name: str) -> int:
        row = self.connection.execute("SELECT id FROM campaigns WHERE name = ?", (campaign_name,)).fetchone()
        if row:
            return row["id"]
        cursor = self.connection.execute(
            "INSERT INTO campaigns (name, template, created_at_utc) VALUES (?, ?, ?)",
            (campaign_name, "Please configure template for this campaign.", utc_now())
        )
        self.connection.commit()
        return cursor.lastrowid

    def import_rows(self, rows: Iterable[dict[str, str]], source_file: str, campaign: str) -> tuple[int, int]:
        added = 0
        skipped = 0
        camp_id = self.get_or_create_campaign_id(campaign)
        for row in rows:
            email = normalize_email(row.get("Verified Email", "") or row.get("Verified Corporate Email", ""))
            target_url = row.get("Target URL", "").strip()
            company_name = (
                row.get("Extracted Name/Title", "").strip()
                or row.get("Company Name/Title", "").strip()
                or "Unknown company"
            )
            if not target_url or not is_allowed_business_role_email(email):
                skipped += 1
                continue
            if self.is_suppressed(email):
                skipped += 1
                continue
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO prospects
                (target_url, company_name, business_email, source_file, campaign_id, imported_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (target_url, company_name, email, source_file, camp_id, utc_now()),
            )
            if cursor.rowcount:
                added += 1
            else:
                skipped += 1
        self.connection.commit()
        return added, skipped

    def is_suppressed(self, email: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM suppression_list WHERE business_email = ?", (email,)
        ).fetchone()
        return row is not None

    def list_prospects(self, status: str, date_from: str = None, date_to: str = None) -> list[sqlite3.Row]:
        query = """
            SELECT p.id, p.company_name, p.business_email, p.target_url, c.name as campaign,
                   p.campaign_id, p.reason_for_contact, p.imported_at_utc,
                   p.why_matched, p.relevance_score, rc.name as research_campaign_name,
                   p.email_quality, p.qualification_status
            FROM prospects p 
            LEFT JOIN campaigns c ON p.campaign_id = c.id
            LEFT JOIN research_campaigns rc ON p.research_campaign_id = rc.id
            WHERE p.status = ?
        """
        params = [status]
        
        if date_from:
            query += " AND substr(p.imported_at_utc, 1, 10) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND substr(p.imported_at_utc, 1, 10) <= ?"
            params.append(date_to)
            
        query += " ORDER BY p.id"
        return self.connection.execute(query, params).fetchall()

    def reject_junk_prospects(self, where_sql: str = "status = 'pending_review'", params: tuple = ()) -> int:
        """Rifiuta (status='rejected') i prospect con indirizzo strutturalmente inutilizzabile
        (chiavi Sentry, domini segnaposto/riservati, fixture di test...). Ritorna quanti ne ha rifiutati."""
        rows = self.connection.execute(f"SELECT id, business_email FROM prospects WHERE {where_sql}", params).fetchall()
        rejected = 0
        for row in rows:
            reason = junk_reason(row["business_email"])
            if reason:
                self.connection.execute(
                    "UPDATE prospects SET status = 'rejected', rejection_reason = ? WHERE id = ?",
                    (reason, row["id"]),
                )
                try:
                    self.connection.execute(
                        "INSERT INTO audit_log (prospect_id, timestamp_utc, action, details) VALUES (?, ?, ?, ?)",
                        (row["id"], utc_now(), "rejected_junk_address", reason),
                    )
                except sqlite3.OperationalError:
                    pass  # audit_log assente su DB molto vecchi: il rifiuto resta valido
                rejected += 1
        return rejected

    def approve(self, prospect_id: int, reason: str, campaign_id: int | None = None) -> bool:
        self.reject_junk_prospects("id = ? AND status = 'pending_review'", (prospect_id,))
        cursor = self.connection.execute(
            """
            UPDATE prospects
            SET status = 'approved', approved_at_utc = ?, reason_for_contact = ?, campaign_id = COALESCE(?, campaign_id)
            WHERE id = ? AND status = 'pending_review'
            """,
            (utc_now(), reason.strip(), campaign_id, prospect_id),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def approve_all(self, campaign: str, reason: str) -> int:
        camp_id = self.get_or_create_campaign_id(campaign)
        self.reject_junk_prospects("campaign_id = ? AND status = 'pending_review'", (camp_id,))
        cursor = self.connection.execute(
            """
            UPDATE prospects
            SET status = 'approved', approved_at_utc = ?, reason_for_contact = ?, campaign_id = COALESCE(?, campaign_id)
            WHERE campaign_id = ? AND status = 'pending_review'
            """,
            (utc_now(), reason.strip(), camp_id),
        )
        self.connection.commit()
        return cursor.rowcount

    def suppress(self, email: str, reason: str) -> bool:
        email = normalize_email(email)
        if not email:
            return False
        self.connection.execute(
            """
            INSERT INTO suppression_list(business_email, reason, suppressed_at_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(business_email) DO UPDATE SET
                reason = excluded.reason,
                suppressed_at_utc = excluded.suppressed_at_utc
            """,
            (email, reason.strip() or "manual suppression", utc_now()),
        )
        self.connection.execute(
            """
            UPDATE prospects SET status = 'do_not_contact'
            WHERE business_email = ? AND status NOT IN ('sent', 'bounced', 'replied')
            """,
            (email,),
        )
        self.connection.commit()
        return True

    def approved_for_campaign(self, campaign: str, limit: int) -> list[sqlite3.Row]:
        """Prospect approvati e inviabili. Gli indirizzi inutilizzabili vengono rifiutati qui,
        cosi' non arrivano mai a SMTP anche se approvati in passato."""
        rows = self._approved_rows(campaign, limit)
        for _ in range(5):
            junk_ids = [r["id"] for r in rows if junk_reason(r["business_email"])]
            if not junk_ids:
                return rows
            marks = ",".join("?" for _ in junk_ids)
            self.reject_junk_prospects(f"id IN ({marks})", tuple(junk_ids))
            rows = self._approved_rows(campaign, limit)
        return [r for r in rows if not junk_reason(r["business_email"])]

    def _approved_rows(self, campaign: str, limit: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT p.*, c.name as campaign_name FROM prospects p
            JOIN campaigns c ON p.campaign_id = c.id
            LEFT JOIN suppression_list s ON lower(s.business_email) = lower(p.business_email)
            LEFT JOIN research_campaigns rc ON p.research_campaign_id = rc.id
            LEFT JOIN prospect_product_fit ppf ON ppf.prospect_id = p.id AND ppf.product_id = rc.product_id
            WHERE c.name = ? 
              AND p.status = 'approved' 
              AND p.qualification_status = 'QUALIFIED' 
              AND s.business_email IS NULL
              AND (
                  rc.product_id IS NULL
                  OR (
                      ppf.id IS NOT NULL 
                      AND ppf.fit_status = 'FIT' 
                      AND ppf.fit_score >= 60
                  )
              )
            ORDER BY p.approved_at_utc, p.id
            LIMIT ?
            """,
            (campaign, limit),
        ).fetchall()

    def sent_today_count(self, campaign: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        row = self.connection.execute(
            """
            SELECT COUNT(p.id) AS total FROM prospects p
            JOIN campaigns c ON p.campaign_id = c.id
            WHERE c.name = ? AND p.status = 'sent' AND substr(p.sent_at_utc, 1, 10) = ?
            """,
            (campaign, today),
        ).fetchone()
        return int(row["total"])

    def mark_sent(self, prospect_id: int, message_id: str, email: str, campaign_id: int, message_text: str) -> None:
        now = utc_now()
        self.connection.execute(
            """
            UPDATE prospects
            SET status = 'sent', sent_at_utc = ?, message_id = ?, last_error = NULL
            WHERE id = ? AND status = 'approved'
            """,
            (now, message_id, prospect_id),
        )
        self.connection.execute(
            "INSERT INTO send_events(prospect_id, event_type, event_at_utc, detail) VALUES (?, ?, ?, ?)",
            (prospect_id, "sent", now, message_id),
        )
        self.connection.execute(
            """
            INSERT INTO email_archive (business_email, campaign_id, sent_at_utc, message_text)
            VALUES (?, ?, ?, ?)
            """,
            (email, campaign_id, now, message_text),
        )
        self.connection.commit()

    def mark_replied(self, prospect_id: int, message_id: str, subject: str, body_text: str) -> None:
        now = utc_now()
        self.connection.execute("UPDATE prospects SET status = 'replied' WHERE id = ?", (prospect_id,))
        self.connection.execute("INSERT INTO send_events(prospect_id, event_type, event_at_utc, detail) VALUES (?, ?, ?, ?)", (prospect_id, "replied", now, subject))
        self.connection.execute("INSERT INTO replies(prospect_id, message_id, received_at_utc, subject, body_text) VALUES (?, ?, ?, ?, ?)", (prospect_id, message_id, now, subject, body_text))
        self.connection.commit()

    def mark_auto_reply(self, prospect_id: int, message_id: str, subject: str, body_text: str) -> None:
        now = utc_now()
        self.connection.execute("UPDATE prospects SET status = 'auto_reply' WHERE id = ?", (prospect_id,))
        self.connection.execute("INSERT INTO send_events(prospect_id, event_type, event_at_utc, detail) VALUES (?, ?, ?, ?)", (prospect_id, "auto_reply", now, subject))
        self.connection.execute("INSERT INTO replies(prospect_id, message_id, received_at_utc, subject, body_text) VALUES (?, ?, ?, ?, ?)", (prospect_id, message_id, now, subject, body_text))
        self.connection.commit()

    def mark_unsubscribed(self, email: str, reason: str = "Unsubscribed") -> None:
        now = utc_now()
        self.connection.execute("INSERT OR IGNORE INTO suppression_list(business_email, reason, added_at_utc) VALUES (?, ?, ?)", (email.strip().lower(), reason, now))
        self.connection.execute("UPDATE prospects SET status = 'unsubscribed' WHERE business_email = ?", (email.strip().lower(),))
        self.connection.commit()

    def mark_error(self, prospect_id: int, error: str) -> None:
        now = utc_now()
        self.connection.execute("UPDATE prospects SET last_error = ? WHERE id = ?", (error[:500], prospect_id))
        self.connection.execute("INSERT INTO send_events(prospect_id, event_type, event_at_utc, detail) VALUES (?, ?, ?, ?)", (prospect_id, "send_error", now, error[:500]))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_allowed_business_role_email(email: str) -> bool:
    if email.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff", ".css", ".js", ".mp4", ".mp3", ".pdf", ".zip", ".tar.gz", ".woff", ".woff2", ".ttf")):
        return False
    if not EMAIL_PATTERN.fullmatch(email):
        return False
    local_part, _, domain = email.partition("@")
    if domain in PERSONAL_EMAIL_DOMAINS:
        return False
    return True


def env_required(name: str, db_val: str) -> str:
    if db_val:
        return db_val
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required setting: {name}")
    return value


def load_settings(db: OutreachDatabase) -> MailSettings:
    db_settings = {}
    try:
        rows = db.connection.execute("SELECT key, value FROM settings").fetchall()
        for r in rows:
            db_settings[r["key"]] = r["value"]
    except sqlite3.OperationalError:
        pass

    daily_limit = int(db_settings.get("daily_limit") or os.getenv("OUTREACH_DAILY_LIMIT", "5"))
    delay_minimum = int(db_settings.get("delay_minimum") or os.getenv("OUTREACH_MIN_DELAY_SECONDS", "90"))
    delay_maximum = int(db_settings.get("delay_maximum") or os.getenv("OUTREACH_MAX_DELAY_SECONDS", "150"))
    if daily_limit < 1:
        raise ValueError("OUTREACH_DAILY_LIMIT must be at least 1")
    if delay_minimum < 60 or delay_maximum < delay_minimum or delay_maximum > 600:
        raise ValueError("Delay must be 60–600 seconds and max must be >= min")

    settings = MailSettings(
        smtp_host=env_required("SMTP_HOST", db_settings.get("smtp_host", "")),
        smtp_port=int(db_settings.get("smtp_port") or os.getenv("SMTP_PORT", "587")),
        smtp_username=env_required("SMTP_USERNAME", db_settings.get("smtp_user", "")),
        smtp_password=env_required("SMTP_PASSWORD", db_settings.get("smtp_password", "")),
        from_name=env_required("OUTREACH_FROM_NAME", db_settings.get("from_name", "") or db_settings.get("company_name", "Marketing")),
        from_email=env_required("OUTREACH_FROM_EMAIL", db_settings.get("smtp_from_email", "")),
        reply_to=env_required("OUTREACH_REPLY_TO", db_settings.get("reply_to", "") or db_settings.get("smtp_from_email", "")),
        unsubscribe_address=env_required("OUTREACH_UNSUBSCRIBE_ADDRESS", db_settings.get("unsubscribe_address", "") or db_settings.get("smtp_from_email", "")),
        company_name=env_required("OUTREACH_COMPANY_NAME", db_settings.get("company_name", "")),
        company_website=env_required("OUTREACH_COMPANY_WEBSITE", db_settings.get("company_website", "https://example.com")),
        daily_limit=daily_limit,
        minimum_delay_seconds=delay_minimum,
        maximum_delay_seconds=delay_maximum,
    )
    for address_name, address in {
        "from_email": settings.from_email,
        "reply_to": settings.reply_to,
        "unsubscribe_address": settings.unsubscribe_address,
    }.items():
        if not EMAIL_PATTERN.fullmatch(address):
            raise ValueError(f"{address_name} is not a valid email address: {address}")
    return settings


def read_template(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw.startswith("Subject:") or "\n\n" not in raw:
        raise ValueError("Template must start with 'Subject:' followed by a blank line and plain-text body")
    header, body = raw.split("\n\n", 1)
    subject = header.removeprefix("Subject:").strip()
    if not subject or not body.strip():
        raise ValueError("Template requires both subject and body")
    fields = {field_name for _, field_name, _, _ in Formatter().parse(raw) if field_name}
    allowed = {"company_name", "domain", "target_url", "reason_for_contact", "company", "website", "reply_to", "unsubscribe_address"}
    unknown = fields - allowed
    if unknown:
        raise ValueError(f"Template uses unsupported fields: {sorted(unknown)}")
    return subject, body.strip()


def build_message(row: sqlite3.Row, settings: MailSettings, template_content: str) -> EmailMessage:
    parts = template_content.split("\n\n", 1)
    subject_template = parts[0].replace("Subject:", "").strip()
    body_template = parts[1].strip() if len(parts) > 1 else ""
    
    # Extract clean domain from email for a better fallback
    email = row["business_email"]
    domain_full = email.split("@")[1] if "@" in email else ""
    domain_clean = domain_full.split(".")[0].capitalize() if domain_full else ""
    
    # Clean up company name: if it's too long (slogan) or "Unknown", use the domain
    raw_company = row["company_name"]
    if not raw_company or len(raw_company) > 30 or "Unknown" in raw_company or "(" in raw_company:
        clean_company = domain_clean
    else:
        clean_company = raw_company

    values = {
        "company_name": clean_company,
        "domain": domain_clean,
        "target_url": row["target_url"],
        "reason_for_contact": row["reason_for_contact"],
        "company": settings.company_name,
        "website": settings.company_website,
        "reply_to": settings.reply_to,
        "unsubscribe_address": settings.unsubscribe_address,
    }
    message = EmailMessage()
    message["Subject"] = subject_template.format(**values)
    message["From"] = formataddr((settings.from_name, settings.from_email))
    message["To"] = row["business_email"]
    message["Reply-To"] = settings.reply_to
    message["Message-ID"] = make_msgid(domain=settings.from_email.partition("@")[2])
    message["List-Unsubscribe"] = f"<mailto:{settings.unsubscribe_address}?subject=unsubscribe>"
    message["Auto-Submitted"] = "auto-generated"
    
    if dict(row).get("message_id"):
        # This is a follow-up, thread it
        old_msg_id = row["message_id"]
        message["In-Reply-To"] = old_msg_id
        message["References"] = old_msg_id
        
    message.set_content(body_template.format(**values))
    return message


class SmtpDisabledError(ConnectionError):
    """Invio disabilitato (test mode). Sottoclasse di ConnectionError: il batch si ferma e nessun prospect viene rifiutato."""


def send_message(message: EmailMessage, settings: MailSettings) -> None:
    # Rete di sicurezza: sotto pytest (o con LEADPILOT_DISABLE_SMTP=1) non si spedisce MAI email vere.
    # In passato i test copiavano il DB di produzione, credenziali SMTP incluse, e hanno inviato a domini reali.
    if os.environ.get("LEADPILOT_DISABLE_SMTP") == "1" or "PYTEST_CURRENT_TEST" in os.environ:
        raise SmtpDisabledError("SMTP disabled in test mode (LEADPILOT_DISABLE_SMTP / pytest)")
    # TLS is mandatory. The script does not support plain SMTP.
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def display_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No records found.")
        return
    print("ID | Company | Business email | Target URL | Reason")
    print("-" * 120)
    for row in rows:
        reason = (row["reason_for_contact"] or "").replace("\n", " ")[:80]
        print(f"{row['id']} | {row['company_name'][:30]} | {row['business_email']} | {row['target_url'][:45]} | {reason}")


def import_csv(db: OutreachDatabase, audit: AuditLog, input_path: Path, campaign: str) -> None:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        has_target = "Target URL" in headers
        has_company = "Extracted Name/Title" in headers or "Company Name/Title" in headers
        has_email = "Verified Email" in headers or "Verified Corporate Email" in headers
        if not (has_target and has_company and has_email):
            raise ValueError(
                "CSV must include Target URL plus either Extracted Name/Title or Company Name/Title "
                "and either Verified Email or Verified Corporate Email"
            )
        added, skipped = db.import_rows(reader, str(input_path), campaign)
    audit.write("csv_imported", {"input": str(input_path), "campaign": campaign, "added": added, "skipped": skipped})
    print(f"Import completed. Added: {added}; skipped: {skipped}.")
    print("Review before sending: python outreach_sender.py list --status pending_review")


def approve(db: OutreachDatabase, audit: AuditLog, prospect_id: int, reason: str) -> None:
    if not reason.strip():
        raise ValueError("Approval requires a public, factual reason for contact")
    if db.approve(prospect_id, reason):
        audit.write("prospect_approved", {"prospect_id": prospect_id, "reason": reason})
        print(f"Prospect {prospect_id} approved.")
    else:
        print(f"Prospect {prospect_id} was not found or is not pending review.")


def approve_all(db: OutreachDatabase, audit: AuditLog, campaign: str, reason: str) -> None:
    if not reason.strip():
        raise ValueError("Approval requires a public, factual reason for contact")
    count = db.approve_all(campaign, reason)
    audit.write("campaign_approved", {"campaign": campaign, "reason": reason, "count": count})
    print(f"Approved {count} pending prospects for campaign '{campaign}'.")


def suppress(db: OutreachDatabase, audit: AuditLog, email: str, reason: str) -> None:
    if db.suppress(email, reason):
        audit.write("email_suppressed", {"email": normalize_email(email), "reason": reason or "manual suppression"})
        print(f"Suppressed {normalize_email(email)}. It will not be sent in future runs.")
    else:
        raise ValueError("Provide a valid email address")


def execute_campaign(
    db: OutreachDatabase,
    audit: AuditLog,
    settings: MailSettings,
    campaign: str,
    template_content: str,
    requested_limit: int | None,
    dry_run: bool,
    confirmed: bool,
) -> None:
    remaining_today = settings.daily_limit - db.sent_today_count(campaign)
    if remaining_today <= 0:
        print(f"Daily limit of {settings.daily_limit} already reached for campaign '{campaign}'.")
        return
    batch_limit = min(requested_limit or remaining_today, remaining_today)
    if batch_limit < 1:
        print("Nothing to send.")
        return
    prospects = db.approved_for_campaign(campaign, batch_limit)
    if not prospects:
        print("No approved, non-suppressed prospects are available for this campaign.")
        return

    print(f"Campaign: {campaign}; approved queue selected: {len(prospects)}; daily remaining: {remaining_today}.")
    if dry_run:
        print("DRY RUN: no email is sent and no status is changed.")
        for prospect in prospects:
            preview = build_message(prospect, settings, template_content)
            print(f"\n--- Prospect {prospect['id']} / {prospect['business_email']} ---")
            print(preview.as_string())
        return
    if not confirmed:
        raise ValueError("Real sending requires both --send and --confirm-send")

    infrastructure_errors = (
        smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
        smtplib.SMTPHeloError, ConnectionError, TimeoutError, socket.gaierror,
    )
    for position, prospect in enumerate(prospects, start=1):
        try:
            message = build_message(prospect, settings, template_content)
        except Exception as e:
            # Un errore di template colpisce TUTTI i prospect: si ferma il batch senza toccare nessuno.
            logging.error("template error (prospect %s): %s - batch aborted, no prospect was modified", prospect["id"], e)
            raise
        try:
            send_message(message, settings)
        except infrastructure_errors as e:
            # Password errata, host irraggiungibile, timeout: non e' colpa del destinatario.
            # Si ferma il batch e il prospect resta 'approved' (prima veniva rifiutato uno dopo l'altro).
            logging.error("SMTP infrastructure error (%s): %s - batch aborted, prospect %s left approved",
                          type(e).__name__, e, prospect["id"])
            return
        except Exception as e:
            logging.error(f"send failed for prospect {prospect['id']}: {e}")
            db.connection.execute("UPDATE prospects SET status='rejected' WHERE id=?", (prospect["id"],))
            db.connection.execute("INSERT INTO audit_log (prospect_id, timestamp_utc, action, details) VALUES (?, ?, ?, ?)",
                         (prospect["id"], datetime.utcnow().isoformat(), "send_failed", str(e)))
            db.connection.commit()
            continue
        message_id = message["Message-ID"]
        message_text = message.as_string()
        db.mark_sent(prospect["id"], message_id, prospect["business_email"], prospect["campaign_id"], message_text)
        audit.write("email_sent", {"prospect_id": prospect["id"], "email": prospect["business_email"], "message_id": message_id})
        logging.info("sent %d/%d to %s", position, len(prospects), prospect["business_email"])
        if position < len(prospects):
            delay = random.randint(settings.minimum_delay_seconds, settings.maximum_delay_seconds)
            logging.info("waiting %d seconds before next approved send", delay)
            time.sleep(delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled local B2B outreach sender")
    parser.add_argument("--database", default="outreach_queue.sqlite3", help="SQLite queue path")
    parser.add_argument("--audit-log", default="outreach_audit.jsonl", help="Audit JSONL path")

    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import", help="Import role-based business emails from collector CSV")
    import_parser.add_argument("--csv", required=True, help="Collector output CSV path")
    import_parser.add_argument("--campaign", required=True, help="Campaign name, e.g. wordpress-agencies-pilot")

    list_parser = subparsers.add_parser("list", help="List queued prospects")
    list_parser.add_argument("--status", default="pending_review", choices=["pending_review", "approved", "sent", "do_not_contact"])

    approve_parser = subparsers.add_parser("approve", help="Manually approve one prospect for sending")
    approve_parser.add_argument("--id", type=int, required=True)
    approve_parser.add_argument("--reason", required=True, help="Public, factual reason the company is relevant")

    approve_all_parser = subparsers.add_parser("approve-all", help="Manually approve all pending prospects for a campaign")
    approve_all_parser.add_argument("--campaign", required=True)
    approve_all_parser.add_argument("--reason", required=True, help="Public, factual reason for the campaign")

    suppress_parser = subparsers.add_parser("suppress", help="Add an address to the permanent do-not-contact list")
    suppress_parser.add_argument("--email", required=True)
    suppress_parser.add_argument("--reason", default="manual opt-out or exclusion")

    send_parser = subparsers.add_parser("send", help="Preview or send only manually approved prospects")
    send_parser.add_argument("--campaign", required=True)
    send_parser.add_argument("--template-content", help="Content of the email template", required=True)
    send_parser.add_argument("--limit", type=int, help="Optional smaller batch; cannot exceed daily limit")
    send_parser.add_argument("--send", action="store_true", help="Enable real SMTP sending; otherwise dry run")
    send_parser.add_argument("--confirm-send", action="store_true", help="Second explicit confirmation required for real sending")

    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    db_path = Path(args.database).expanduser().resolve()
    audit_path = Path(args.audit_log).expanduser().resolve()
    db = OutreachDatabase(db_path)
    audit = AuditLog(audit_path)

    try:
        if args.command == "import":
            import_csv(db, audit, Path(args.csv).expanduser().resolve(), args.campaign)
        elif args.command == "list":
            display_rows(db.list_prospects(args.status))
        elif args.command == "approve":
            approve(db, audit, args.id, args.reason)
        elif args.command == "approve-all":
            approve_all(db, audit, args.campaign, args.reason)
        elif args.command == "suppress":
            suppress(db, audit, args.email, args.reason)
        elif args.command == "send":
            settings = load_settings(db)
            execute_campaign(
                db=db,
                audit=audit,
                settings=settings,
                campaign=args.campaign,
                template_content=args.template_content,
                requested_limit=args.limit,
                dry_run=not args.send,
                confirmed=args.confirm_send,
            )
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        logging.error("%s", exc)
        audit.write("command_error", {"command": args.command, "error": str(exc)[:500]})
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
