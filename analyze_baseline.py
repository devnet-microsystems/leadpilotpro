import sqlite3
from pathlib import Path

DB_PATH = Path("outreach_queue_baseline_v3.sqlite3")

def main():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    report = []
    report.append("# Baseline Analysis Report")

    # BASELINE OVERVIEW
    total_runs = cursor.execute("SELECT COUNT(DISTINCT run_id) FROM query_runs").fetchone()[0]
    total_query_attempts = cursor.execute("SELECT COUNT(id) FROM query_runs").fetchone()[0]
    successful_queries = cursor.execute("SELECT COUNT(id) FROM query_runs WHERE status IN ('SUCCESS', 'ZERO_RESULTS')").fetchone()[0]
    provider_failures = cursor.execute("SELECT COUNT(id) FROM query_runs WHERE status NOT IN ('SUCCESS', 'ZERO_RESULTS')").fetchone()[0]
    total_raw_results = cursor.execute("SELECT SUM(raw_results) FROM query_runs WHERE status IN ('SUCCESS', 'ZERO_RESULTS')").fetchone()[0] or 0
    total_unique_domains = cursor.execute("SELECT SUM(unique_domains) FROM query_runs WHERE status IN ('SUCCESS', 'ZERO_RESULTS')").fetchone()[0] or 0
    total_unique_emails = cursor.execute("SELECT COUNT(id) FROM prospects").fetchone()[0]
    total_prospects = total_unique_emails  # Since prospects table is unique by business_email

    # Latency and Cost
    latencies = [row[0] for row in cursor.execute("SELECT duration_ms FROM query_runs WHERE duration_ms IS NOT NULL AND duration_ms > 0").fetchall()]
    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies)//2]
        p95 = latencies[int(len(latencies) * 0.95)]
    else:
        p50 = p95 = 0

    cost_per_query = 5.0 / 1000.0  # Brave Search pricing: $5 per 1000 queries
    total_cost = total_query_attempts * cost_per_query
    cost_per_success = total_cost / successful_queries if successful_queries > 0 else 0
    cost_per_lead = total_cost / total_unique_emails if total_unique_emails > 0 else 0

    report.append("\n## BASELINE OVERVIEW")
    report.append(f"- **Total runs:** {total_runs}")
    report.append(f"- **Total query attempts:** {total_query_attempts}")
    report.append(f"- **Successful queries:** {successful_queries}")
    report.append(f"- **Provider failures:** {provider_failures}")
    report.append(f"- **Total raw results (successful only):** {total_raw_results}")
    report.append(f"- **Total unique domains (successful only):** {total_unique_domains}")
    report.append(f"- **Total unique emails/prospects:** {total_unique_emails}")
    report.append(f"- **Latency:** p50={p50}ms, p95={p95}ms")
    report.append(f"- **Total Estimated Cost:** ${total_cost:.4f} (calculated at $5/1000 queries)")
    report.append(f"- **Cost per successful query:** ${cost_per_success:.4f}")
    report.append(f"- **Cost per discovered email:** ${cost_per_lead:.4f}")

    # LEAD QUALITY
    report.append("\n## LEAD QUALITY")
    
    # Confidence breakdown
    conf_types = cursor.execute("SELECT confidence_type, COUNT(id) as c FROM prospects GROUP BY confidence_type ORDER BY c DESC").fetchall()
    for row in conf_types:
        report.append(f"- **{row['confidence_type']}**: {row['c']}")
        
    report.append("\n### Relevance Breakdown")
    high_rel = cursor.execute("SELECT COUNT(id) FROM prospects WHERE relevance_score >= 70").fetchone()[0]
    med_rel = cursor.execute("SELECT COUNT(id) FROM prospects WHERE relevance_score >= 40 AND relevance_score < 70").fetchone()[0]
    low_rel = cursor.execute("SELECT COUNT(id) FROM prospects WHERE relevance_score < 40").fetchone()[0]
    report.append(f"- **HIGH (>=70):** {high_rel}")
    report.append(f"- **MEDIUM (40-69):** {med_rel}")
    report.append(f"- **LOW (<40):** {low_rel}")

    # SAME-DOMAIN CONTACTS CHECK
    # email_domain == company_domain. We extract domain from business_email and domain from target_url (or source_url)
    # Actually, we can just use SQL to do a quick heuristic.
    prospects = cursor.execute("SELECT id, business_email, target_url FROM prospects").fetchall()
    same_domain = 0
    third_party = 0
    unknown = 0
    import re
    from urllib.parse import urlparse

    def get_domain(url):
        if not url: return ""
        if not url.startswith("http"): url = "http://" + url
        try:
            return urlparse(url).netloc.replace("www.", "").lower()
        except:
            return ""

    for p in prospects:
        email = p['business_email']
        url = p['target_url']
        if not email or '@' not in email:
            continue
        email_domain = email.split('@')[1].lower()
        if not url:
            unknown += 1
            continue
            
        url_domain = get_domain(url)
        if url_domain:
            if email_domain == url_domain or email_domain in url_domain or url_domain in email_domain:
                same_domain += 1
            else:
                third_party += 1
        else:
            unknown += 1

    report.append("\n### Provenance & Domain Alignment")
    report.append(f"- **Same-domain contacts:** {same_domain}")
    report.append(f"- **Third-party sourced contacts:** {third_party}")
    report.append(f"- **Unknown company-domain contacts:** {unknown}")


    # PER TARGET
    report.append("\n## PER TARGET")
    targets = cursor.execute("SELECT DISTINCT target_key FROM query_runs").fetchall()
    
    report.append("| Target | Attempts | Success | Failures | New Domains | Unique Emails | Personal Emails | High Relevance (>=70) | Qualified Yield/Query | Personal Yield/Query |")
    report.append("|--------|----------|---------|----------|-------------|---------------|-----------------|-----------------------|-----------------------|----------------------|")
    
    for t in targets:
        tk = t['target_key']
        q = cursor.execute("""
            SELECT 
                COUNT(id) as attempts,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status NOT IN ('SUCCESS', 'ZERO_RESULTS') THEN 1 ELSE 0 END) as failures,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN new_domains ELSE 0 END) as n_domains
            FROM query_runs WHERE target_key=?
        """, (tk,)).fetchone()
        
        attempts = q['attempts']
        success = q['successful'] or 0
        failures = q['failures'] or 0
        n_domains = q['n_domains'] or 0
        
        # Unique emails for this target
        # A prospect might be found by multiple runs, we join prospect_sources with query_runs
        e_stats = cursor.execute("""
            SELECT 
                COUNT(DISTINCT p.id) as total_emails,
                COUNT(DISTINCT CASE WHEN p.confidence_type = 'PERSONAL' THEN p.id ELSE NULL END) as personal_emails,
                COUNT(DISTINCT CASE WHEN p.relevance_score >= 70 THEN p.id ELSE NULL END) as high_rel
            FROM prospects p
            JOIN prospect_sources ps ON p.id = ps.prospect_id
            JOIN query_runs qr ON ps.query_run_id = qr.run_id
            WHERE qr.target_key = ? AND qr.status IN ('SUCCESS', 'ZERO_RESULTS')
        """, (tk,)).fetchone()
        
        u_emails = e_stats['total_emails']
        p_emails = e_stats['personal_emails'] or 0
        h_rel = e_stats['high_rel'] or 0
        
        q_yield = h_rel / success if success > 0 else 0
        p_yield = p_emails / success if success > 0 else 0
        
        report.append(f"| {tk} | {attempts} | {success} | {failures} | {n_domains} | {u_emails} | {p_emails} | {h_rel} | {q_yield:.2f} | {p_yield:.2f} |")

    # PER PROVIDER
    report.append("\n## PER PROVIDER")
    provs = cursor.execute("SELECT DISTINCT provider FROM query_runs").fetchall()
    
    report.append("| Provider | Attempts | Success | Failures | Results/Query | New Domains/Query | Emails/Query | High Qual/Query | Latency p50 | Latency p95 | Cost | Cost/Success |")
    report.append("|----------|----------|---------|----------|---------------|-------------------|--------------|-----------------|-------------|-------------|------|--------------|")
    
    for p in provs:
        pv = p['provider']
        q_stat = cursor.execute("""
            SELECT 
                COUNT(id) as attempts,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status NOT IN ('SUCCESS', 'ZERO_RESULTS') THEN 1 ELSE 0 END) as failures,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN raw_results ELSE 0 END) as raw_results,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN new_domains ELSE 0 END) as n_domains
            FROM query_runs WHERE provider=?
        """, (pv,)).fetchone()
        
        attempts = q_stat['attempts']
        success = q_stat['successful'] or 0
        failures = q_stat['failures'] or 0
        
        raw_res = (q_stat['raw_results'] or 0) / success if success > 0 else 0
        new_doms = (q_stat['n_domains'] or 0) / success if success > 0 else 0
        
        e_stat = cursor.execute("""
            SELECT 
                COUNT(DISTINCT p.id) as total_emails,
                COUNT(DISTINCT CASE WHEN p.relevance_score >= 70 THEN p.id ELSE NULL END) as high_rel
            FROM prospects p
            JOIN prospect_sources ps ON p.id = ps.prospect_id
            JOIN query_runs qr ON ps.query_run_id = qr.run_id
            WHERE qr.provider = ? AND qr.status IN ('SUCCESS', 'ZERO_RESULTS')
        """, (pv,)).fetchone()
        
        emails = e_stat['total_emails'] / success if success > 0 else 0
        h_rel = (e_stat['high_rel'] or 0) / success if success > 0 else 0
        
        # Latency for provider
        lats = [row[0] for row in cursor.execute("SELECT duration_ms FROM query_runs WHERE provider=? AND duration_ms > 0", (pv,)).fetchall()]
        if lats:
            lats.sort()
            prov_p50 = lats[len(lats)//2]
            prov_p95 = lats[int(len(lats) * 0.95)]
        else:
            prov_p50 = prov_p95 = 0
            
        prov_cost = attempts * cost_per_query
        prov_cost_success = prov_cost / success if success > 0 else 0
        
        report.append(f"| {pv} | {attempts} | {success} | {failures} | {raw_res:.2f} | {new_doms:.2f} | {emails:.2f} | {h_rel:.2f} | {prov_p50}ms | {prov_p95}ms | ${prov_cost:.4f} | ${prov_cost_success:.4f} |")

    # PER QUERY FAMILY
    report.append("\n## PER QUERY FAMILY")
    fams = cursor.execute("SELECT DISTINCT family FROM query_runs").fetchall()
    
    report.append("| Family | Attempts | Success | Failures | Results/Query | New Domains/Query | Emails/Query | High Qual/Query |")
    report.append("|--------|----------|---------|----------|---------------|-------------------|--------------|-----------------|")
    
    for f in fams:
        fm = f['family']
        q_stat = cursor.execute("""
            SELECT 
                COUNT(id) as attempts,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status NOT IN ('SUCCESS', 'ZERO_RESULTS') THEN 1 ELSE 0 END) as failures,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN raw_results ELSE 0 END) as raw_results,
                SUM(CASE WHEN status IN ('SUCCESS', 'ZERO_RESULTS') THEN new_domains ELSE 0 END) as n_domains
            FROM query_runs WHERE family=?
        """, (fm,)).fetchone()
        
        attempts = q_stat['attempts']
        success = q_stat['successful'] or 0
        failures = q_stat['failures'] or 0
        
        raw_res = (q_stat['raw_results'] or 0) / success if success > 0 else 0
        new_doms = (q_stat['n_domains'] or 0) / success if success > 0 else 0
        
        e_stat = cursor.execute("""
            SELECT 
                COUNT(DISTINCT p.id) as total_emails,
                COUNT(DISTINCT CASE WHEN p.relevance_score >= 70 THEN p.id ELSE NULL END) as high_rel
            FROM prospects p
            JOIN prospect_sources ps ON p.id = ps.prospect_id
            JOIN query_runs qr ON ps.query_run_id = qr.run_id
            WHERE qr.family = ? AND qr.status IN ('SUCCESS', 'ZERO_RESULTS')
        """, (fm,)).fetchone()
        
        emails = e_stat['total_emails'] / success if success > 0 else 0
        h_rel = (e_stat['high_rel'] or 0) / success if success > 0 else 0
        
        report.append(f"| {fm} | {attempts} | {success} | {failures} | {raw_res:.2f} | {new_doms:.2f} | {emails:.2f} | {h_rel:.2f} |")


    # TOP STRATEGIES
    report.append("\n## TOP STRATEGIES (By Qualified Leads / Query)")
    
    strats = cursor.execute("""
        SELECT 
            r.provider,
            r.family,
            r.query_template,
            COUNT(DISTINCT r.id) as samples,
            SUM(r.new_domains) as total_new_domains,
            COUNT(DISTINCT p.id) as total_emails,
            COUNT(DISTINCT CASE WHEN p.relevance_score >= 70 THEN p.id ELSE NULL END) as total_high_rel
        FROM query_runs r
        LEFT JOIN prospect_sources ps ON r.run_id = ps.query_run_id
        LEFT JOIN prospects p ON ps.prospect_id = p.id
        WHERE r.status IN ('SUCCESS', 'ZERO_RESULTS')
        GROUP BY r.provider, r.family, r.query_template
    """).fetchall()
    
    ranked = []
    for s in strats:
        samples = s['samples']
        q_yield = (s['total_high_rel'] or 0) / samples if samples > 0 else 0
        dom_yield = (s['total_new_domains'] or 0) / samples if samples > 0 else 0
        ranked.append({
            "provider": s['provider'],
            "family": s['family'],
            "template": s['query_template'],
            "samples": samples,
            "q_yield": q_yield,
            "dom_yield": dom_yield
        })
        
    ranked.sort(key=lambda x: x['q_yield'], reverse=True)
    
    report.append("| Rank | Provider | Family | Template | Samples | New Domains/Query | Qualified Leads/Query |")
    report.append("|------|----------|--------|----------|---------|-------------------|-----------------------|")
    
    for i, r in enumerate(ranked[:15]):
        report.append(f"| {i+1} | {r['provider']} | {r['family']} | `{r['template']}` | {r['samples']} | {r['dom_yield']:.2f} | **{r['q_yield']:.2f}** |")

    # QUERY EXECUTION LOG
    report.append("\n## QUERY EXECUTION LOG")
    report.append("| ID | Provider | Query | Status | Latency (ms) | Results | Unique Domains | Unique Emails | High Relevance (>=70) |")
    report.append("|----|----------|-------|--------|--------------|---------|----------------|---------------|-----------------------|")
    
    queries = cursor.execute("""
        SELECT 
            r.id, r.provider, r.query, r.status, r.duration_ms, r.raw_results, r.unique_domains,
            COUNT(DISTINCT p.id) as emails,
            COUNT(DISTINCT CASE WHEN p.relevance_score >= 70 THEN p.id ELSE NULL END) as h_rel
        FROM query_runs r
        LEFT JOIN prospect_sources ps ON r.run_id = ps.query_run_id
        LEFT JOIN prospects p ON ps.prospect_id = p.id
        GROUP BY r.id
        ORDER BY r.id ASC
    """).fetchall()
    
    for q in queries:
        report.append(f"| {q['id']} | {q['provider']} | `{q['query']}` | {q['status']} | {q['duration_ms']} | {q['raw_results']} | {q['unique_domains']} | {q['emails']} | {q['h_rel']} |")

    with open("/Users/tonic/.gemini/antigravity-ide/brain/7765947b-1da0-450c-87e9-89e52f935579/baseline_report_v3.md", "w") as f:
        f.write("\n".join(report))
        
    print("Report generated at baseline_report_v3.md")

if __name__ == "__main__":
    main()
