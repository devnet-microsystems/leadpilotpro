import sqlite3
import pytest
from pathlib import Path
from schema_bootstrap import ensure_all_schema
from migration_p6_1 import migrate as p6_1_migrate
from outreach_sender import OutreachDatabase

def get_table_info(conn: sqlite3.Connection, table_name: str) -> dict:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1]: row for row in rows}

def get_indexes(conn: sqlite3.Connection, table_name: str) -> list:
    indexes = conn.execute(f"PRAGMA index_list('{table_name}')").fetchall()
    idx_details = []
    for idx in indexes:
        info = conn.execute(f"PRAGMA index_info({idx[1]})").fetchall()
        cols = [col[2] for col in info]
        idx_details.append({"name": idx[1], "unique": idx[2], "columns": cols})
    return idx_details

def assert_outbound_jobs_schema_is_correct(conn: sqlite3.Connection):
    info = get_table_info(conn, "outbound_jobs")
    assert "id" in info
    assert "campaign_id" in info
    assert "prospect_id" in info
    assert "sequence_step" in info
    assert "status" in info
    
    # Verify the unique constraint
    indexes = get_indexes(conn, "outbound_jobs")
    unique_found = False
    for idx in indexes:
        if idx["unique"] == 1:
            cols = set(idx["columns"])
            if cols == {"campaign_id", "prospect_id", "sequence_step"}:
                unique_found = True
                break
    assert unique_found, "UNIQUE(campaign_id, prospect_id, sequence_step) constraint not found!"

def test_clean_bootstrap_produces_correct_schema(tmp_path):
    db_path = tmp_path / "test_clean.sqlite3"
    ensure_all_schema(str(db_path))
    conn = sqlite3.connect(str(db_path))
    assert_outbound_jobs_schema_is_correct(conn)
    conn.close()

def test_legacy_upgrade_produces_correct_schema(tmp_path):
    db_path = tmp_path / "test_upgrade.sqlite3"
    # Create the legacy base schema
    base = OutreachDatabase(db_path)
    base.connection.close()
    
    # At this point outbound_jobs should not exist
    conn = sqlite3.connect(str(db_path))
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT 1 FROM outbound_jobs").fetchone()
    conn.close()
    
    # Run the specific P6.1 migration
    p6_1_migrate(str(db_path))
    
    # Verify it matches
    conn = sqlite3.connect(str(db_path))
    assert_outbound_jobs_schema_is_correct(conn)
    conn.close()
