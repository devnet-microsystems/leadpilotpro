.mode list
.separator " | "
SELECT 'campaigns count:', (SELECT count(*) FROM campaigns);
SELECT 'templates count:', (SELECT count(*) FROM templates);
SELECT 'email_archive count:', (SELECT count(*) FROM email_archive);
SELECT 'prospects count:', (SELECT count(*) FROM prospects);
SELECT 'research_campaigns count:', (SELECT count(*) FROM research_campaigns);
SELECT 'campaign_queries count:', (SELECT count(*) FROM campaign_queries);
SELECT 'send_events count:', (SELECT count(*) FROM send_events);

SELECT 'prospect 163 exists:', (SELECT count(*) FROM prospects WHERE id=163);
SELECT 'send_event 330 exists:', (SELECT count(*) FROM send_events WHERE id=330);
SELECT 'archive 327 exists:', (SELECT count(*) FROM email_archive WHERE id=327);
SELECT 'research_campaign 32 exists:', (SELECT count(*) FROM research_campaigns WHERE id=32);
SELECT 'offer 35 exists:', (SELECT count(*) FROM sales_offers WHERE id=35);
SELECT 'ICP 32 exists:', (SELECT count(*) FROM ideal_customer_profiles WHERE id=32);

ATTACH DATABASE 'outreach_queue.BACKUP-2026-09-17.sqlite3' AS backup_db;
SELECT 'campaigns match:', (SELECT count(*) FROM campaigns c JOIN backup_db.campaigns b ON c.id=b.id AND c.name=b.name AND c.template=b.template) = 14 AND (SELECT count(*) FROM campaigns) = 14;
SELECT 'templates match:', (SELECT count(*) FROM templates t JOIN backup_db.templates b ON t.name=b.name AND t.content=b.content) = 16 AND (SELECT count(*) FROM templates) = 16;
DETACH DATABASE backup_db;
