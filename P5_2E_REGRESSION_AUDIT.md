# P5.2E-R1 — Regression Audit

## 1. Initial Failed Tests

| Test | File | Error |
|---|---|---|
| `test_campaign_creation_from_product` | `tests/test_p5_2_discovery.py` | `sqlite3.OperationalError: table campaign_queries has no column named target_key` |
| `test_concrete_query_expansion` | `tests/test_p5_2_discovery.py` | Same root cause |

---

## 2. Root Cause — Three Distinct Issues

### Issue A — P5.2E introduced wrong fixture schema (my error)
During P5.2E execution, I added a `CREATE TABLE IF NOT EXISTS campaign_queries` block to the test fixture to fix a "no such table" error. I used a minimal schema:

```sql
-- WRONG (added during P5.2E):
CREATE TABLE IF NOT EXISTS campaign_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    family TEXT,
    query TEXT,
    priority INTEGER,
    score REAL,
    status TEXT,
    created_at_utc TEXT
);
```

The **real** `campaign_queries` schema (from production DB) is:
```sql
-- CORRECT (production):
(id, campaign_id, family, query, target_key, is_enabled, status)
```

`campaign_builder.py` correctly uses `target_key` and `is_enabled` but the test fixture lacked them.

### Issue B — P5.2C naming convention change (intentional)
`campaign_builder.py` uses `product_id`-based naming:
```python
camp_name = f"[Auto] Discovery: Product {product_id}"
icp_name  = f"[Auto] ICP: Product {product_id}"
```

The test still asserted old product_name convention:
```python
assert "TestAI CRM" in camp["name"]   # STALE
assert "TestAI CRM" in icp["name"]    # STALE
```

### Issue C — P5.2D "Global" fallback removal (intentional)
`campaign_builder.py` comment (line 76):
> `# We DO NOT use "Global" anymore, but if empty, we leave it empty to avoid "UNKNOWN" leakage`

The test still asserted `"Global"` in query strings and ICP countries.

---

## 3. Corrected Assertions (OLD → NEW → WHY)

### `test_campaign_creation_from_product`

| OLD | NEW | WHY |
|---|---|---|
| `assert "TestAI CRM" in camp["name"]` | `assert "Discovery: Product 1" in camp["name"]` | P5.2C changed naming to product_id |
| `assert "TestAI CRM" in icp["name"]` | `assert "ICP: Product 1" in icp["name"]` | P5.2C changed naming to product_id |
| `assert "Global" in icp["countries"]` | `assert icp["countries"] == "[]"` | P5.2D removed Global fallback |
| `assert len(templates) == 6` | unchanged | Still correct: 2 keywords x 3 templates = 6 |

### `test_concrete_query_expansion`

| OLD | NEW | WHY |
|---|---|---|
| `'"AI sales" "VP Sales" Global'` | `'"AI sales" "VP Sales"'` | P5.2D removed Global suffix |
| `'"AI sales" "CEO" Global'` | `'"AI sales" "CEO"'` | P5.2D removed Global suffix |
| `'"automated CRM" "VP Sales" Global'` | `'"automated CRM" "VP Sales"'` | P5.2D removed Global suffix |
| `'"AI sales" companies Global'` | `'"AI sales" companies'` | P5.2D removed Global suffix |
| `'B2B "automated CRM" Global'` | `'B2B "automated CRM"'` | P5.2D removed Global suffix |

---

## 4. Real Regression in Production Code?

**NO.** `campaign_builder.py` behavior is intentional. The assertions that fail test the old behavior that was deliberately changed in P5.2C and P5.2D.

---

## 5. Additional Fixes Applied During P5.2E-R1

### Fix 1 — `LeadStore._init_tables()`: Missing columns in `prospects` DDL
`save_lead()` reads `qualification_status` and related P3 columns but `_init_tables()` DDL didn't declare them. Fresh DBs (used by `test_osint_engine.py`) had no column → crash.

```python
# ADDED to prospects DDL:
email_quality TEXT,
qualification_status TEXT DEFAULT 'REVIEW_REQUIRED',
rejection_reason TEXT
```

### Fix 2 — `LeadStore._init_tables()`: `research_campaigns` stub missing
`save_lead()` now queries `research_campaigns.product_id` for Product Fit, but the table was created only by `OutreachDatabase`. Added a minimal `IF NOT EXISTS` stub so LeadStore can operate standalone.

### Fix 3 — `LeadStore._init_tables()`: `query_runs` missing `campaign_id`, `template_id`
`save_query_run()` inserts `campaign_id` and `template_id`, which were previously added by `migrate_v2` ALTER TABLE. Added directly to DDL to cover fresh-DB isolation.

### Fix 4 — `test_osint_engine.py`: `save_lead(campaign_id=…)` → `save_lead(research_campaign_id=…)`
P5.2E renamed the parameter. Updated all 5 call sites.

### Note
All four fixes above are **correctness fixes in test infrastructure and DDL coherence** — not changes to P3/P4/P5 business logic.

---

## 6. Timestamp of Final Clean Run

```
Sat Sep 19 23:57:23 CEST 2026
tests/: 21 passed, 6 skipped (all skips = live network tests)
test_osint_engine.py: 7 passed
```
