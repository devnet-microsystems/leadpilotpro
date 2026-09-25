ATTACH DATABASE 'outreach_queue.BACKUP-2026-09-17.sqlite3' AS backup_db;

-- 1. Remove Email Archive 327
DELETE FROM email_archive WHERE id=327;

-- 2. Remove Test Artifacts (Offers, ICPs, Research Campaigns)
DELETE FROM sales_offers WHERE id=35;
DELETE FROM ideal_customer_profiles WHERE id=32;
DELETE FROM research_campaigns WHERE id=32;

-- 3. Remove queries related to campaign 32
DELETE FROM campaign_queries WHERE campaign_id=32;
DELETE FROM query_templates WHERE campaign_id=32;

-- 4. Remove 2 test query runs (IDs 32, 33)
DELETE FROM query_runs WHERE id IN (32, 33);

-- 5. Remove 1 test prospect source (ID 323)
DELETE FROM prospect_sources WHERE id=323;

-- 6. Remove test sessions (those not in backup)
DELETE FROM sessions WHERE token NOT IN (SELECT token FROM backup_db.sessions);

-- 7. Restore prospect 163 and send_event 330
INSERT INTO prospects SELECT * FROM backup_db.prospects WHERE id=163;
INSERT INTO send_events SELECT * FROM backup_db.send_events WHERE id=330;

DETACH DATABASE backup_db;
