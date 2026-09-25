"""
Configurazione condivisa dei test.

REGOLE DI SICUREZZA (nate da un incidente reale: i test copiavano il DB di produzione, credenziali SMTP
incluse, e hanno inviato email vere a domini veri):
  * nessun test usa outreach_queue.sqlite3 di produzione: LEADPILOT_DB_PATH punta a un DB temporaneo;
  * l'invio SMTP e' disabilitato (LEADPILOT_DISABLE_SMTP=1; outreach_sender lo rispetta anche sotto pytest).
Va impostato PRIMA che web_server venga importato, per questo sta qui.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["LEADPILOT_DISABLE_SMTP"] = "1"
os.environ["LEADPILOT_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="leadpilot_tests_")) / "session.sqlite3")


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """DB nuovo con lo schema COMPLETO (come un'installazione da zero), collegato a web_server."""
    from schema_bootstrap import ensure_all_schema

    db_path = tmp_path / "test.sqlite3"
    ensure_all_schema(db_path)
    monkeypatch.setattr("web_server.DB_PATH", db_path)
    return str(db_path)
