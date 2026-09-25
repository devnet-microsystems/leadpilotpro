"""
product_intelligence/store.py

Database operations for the Product Intelligence system.
Tables: products, product_sources

IMPORTANT: Does NOT touch any P1-P4 tables (prospects, campaigns, etc.)
"""
import json
import logging
import sqlite3
import db_connector
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    slug                TEXT UNIQUE NOT NULL,
    status              TEXT NOT NULL DEFAULT 'DRAFT',
    created_at_utc      TEXT NOT NULL,
    updated_at_utc      TEXT NOT NULL,
    analysis_model      TEXT,
    analysis_provider   TEXT,
    analysis_version    TEXT DEFAULT '1',
    raw_summary         TEXT,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS product_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    source_type     TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    source_url      TEXT,
    content_hash    TEXT NOT NULL,
    extracted_text  TEXT,
    language        TEXT,
    fetched_at_utc  TEXT NOT NULL,
    created_at_utc  TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_schema(db_path: str) -> None:
    """Idempotently create P5 tables without touching existing P1-P4 tables."""
    conn = db_connector.get_connection(db_path)
    conn.executescript(DDL)
    conn.commit()
    conn.close()


def _slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")[:80]
    return slug or "product"


# ──────────────────────────────────────────────────────────────────────────────
# Product CRUD
# ──────────────────────────────────────────────────────────────────────────────

def create_product(db_path: str, name: str) -> dict:
    base_slug = _slugify(name)
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row

    # Ensure slug uniqueness by appending a counter if needed
    slug = base_slug
    suffix = 1
    while conn.execute("SELECT 1 FROM products WHERE slug=?", (slug,)).fetchone():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    now = _utc_now()
    cur = conn.execute(
        """INSERT INTO products (name, slug, status, created_at_utc, updated_at_utc)
           VALUES (?, ?, 'DRAFT', ?, ?)""",
        (name, slug, now, now),
    )
    conn.commit()
    product = conn.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone()
    result = dict(product)
    conn.close()
    return result


def get_product(db_path: str, product_id: int) -> Optional[dict]:
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def list_products(db_path: str) -> List[dict]:
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products ORDER BY created_at_utc DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_product_status(db_path: str, product_id: int, status: str, error: str = "") -> None:
    conn = db_connector.get_connection(db_path)
    conn.execute(
        "UPDATE products SET status=?, error_message=?, updated_at_utc=? WHERE id=?",
        (status, error or None, _utc_now(), product_id),
    )
    conn.commit()
    conn.close()


def save_product_analysis(
    db_path: str,
    product_id: int,
    profile: dict,
    provider_name: str,
    model_name: str,
) -> None:
    raw = json.dumps(profile, ensure_ascii=False)
    conn = db_connector.get_connection(db_path)
    conn.execute(
        """UPDATE products
           SET status='READY', raw_summary=?, analysis_provider=?,
               analysis_model=?, updated_at_utc=?, error_message=NULL
           WHERE id=?""",
        (raw, provider_name, model_name, _utc_now(), product_id),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Product Sources CRUD
# ──────────────────────────────────────────────────────────────────────────────

def source_hash_exists(db_path: str, product_id: int, content_hash: str) -> bool:
    """Return True if this exact content has already been stored for this product."""
    conn = db_connector.get_connection(db_path)
    row = conn.execute(
        "SELECT 1 FROM product_sources WHERE product_id=? AND content_hash=?",
        (product_id, content_hash),
    ).fetchone()
    conn.close()
    return row is not None


def add_source(
    db_path: str,
    product_id: int,
    source_type: str,
    source_name: str,
    content_hash: str,
    extracted_text: str,
    source_url: Optional[str] = None,
    language: Optional[str] = None,
) -> dict:
    now = _utc_now()
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """INSERT INTO product_sources
           (product_id, source_type, source_name, source_url,
            content_hash, extracted_text, language, fetched_at_utc, created_at_utc)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (product_id, source_type, source_name, source_url,
         content_hash, extracted_text, language, now, now),
    )
    # Also update the updated_at on the parent product
    conn.execute(
        "UPDATE products SET updated_at_utc=? WHERE id=?",
        (now, product_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM product_sources WHERE id=?", (cur.lastrowid,)).fetchone()
    result = dict(row)
    conn.close()
    return result


def list_sources(db_path: str, product_id: int) -> List[dict]:
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM product_sources WHERE product_id=? ORDER BY id",
        (product_id,),
    ).fetchall()
    conn.close()
    # Do NOT return extracted_text in the list (can be large) — caller can fetch individually
    results = []
    for r in rows:
        d = dict(r)
        d.pop("extracted_text", None)
        results.append(d)
    return results


def get_sources_with_text(db_path: str, product_id: int) -> List[dict]:
    """Return full source objects including extracted_text, used by the agent."""
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM product_sources WHERE product_id=? ORDER BY id",
        (product_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
