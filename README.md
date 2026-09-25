# LeadPilot Pro 🚀
**Unified Local Market Intelligence & Cold Outreach Automation**

LeadPilot Pro is an enterprise-grade B2B lead generation and cold outreach CRM. Designed for agencies and sales teams, it bridges the gap between raw data extraction and highly personalized, automated email outreach.

---

## 🌟 Key Features

### 1. Product-Driven Market Intelligence & OSINT Lead Generation
Start from what you actually sell. LeadPilot Pro turns a product URL, text, or PDF into an evidence-backed customer profile, then discovers and qualifies matching companies from live public sources.

- **Product Intelligence**: Extracts product facts, target markets, buyer roles, use cases, keywords, and explicit uncertainty from one or more sources.
- **ICP + Market Discovery**: Builds an ICP and market-specific research campaign from the product profile.
- **Evidence Gate**: Product-fit leads retain source evidence, fit score, matched signals, and human review status before outreach.
- **Precision Targeting**: Filter by Country, State, Industry, and exact Job Title (e.g., *Marketing Director in Texas*).
- **Target Account Search**: Extract key decision-makers from specific target domains.
- **Automated Scraping**: Just type a query like *"Luxury Web Agencies Dubai"* and let the engine scrape live, verified business data.

### 2. Manual QA & Approval Workflow
Protect your sender reputation. Unlike bulk email blasting tools, LeadPilot Pro forces a manual review stage.
- **Human-in-the-Loop**: Review every single lead before approving them for a campaign.
- **Personalized Hooks**: Automatically generate or manually tweak the "Reason for Contact" for every prospect, ensuring your cold emails feel like 1-to-1 communication.

### 3. Smart Campaign & Follow-up Engine
Send sequences that actually get responses without breaking email provider rules.
- **True Email Threading**: Follow-up emails are mathematically linked to the original email using standard `In-Reply-To` and `References` headers. Your follow-ups appear cleanly in the same conversation thread in Gmail/Outlook.
- **AI Template Editor**: Write high-converting hooks using the built-in AI template generator.

### 4. IMAP Sync & Automated Inbox Management
Your time should be spent closing deals, not reading bounce notifications.
- **Reply Detection**: Automatically scans your inbox to detect when a prospect replies.
- **Out of Office (OOO)**: Smart detection of auto-responders vs. genuine human replies.
- **Unsubscribe Handling**: Native support for the `List-Unsubscribe` header. If a prospect clicks unsubscribe, they are instantly flagged and suppressed system-wide.
- **Bounce Protection**: Detects server rejections to keep your deliverability score high.

### 5. Enterprise Reporting
Gain complete visibility over your outreach pipeline.
- **Real-Time Dashboard**: Monitor Approved, Sent, and Suppressed leads through interactive charts.
- **Date Filtering**: Slice and dice your data to analyze performance over specific timeframes (e.g., *Last 7 days*).
- **Export & Print**: Instantly export any view to CSV or generate clean, print-ready PDF reports for stakeholder meetings.

---

## 🔒 Security & Infrastructure

LeadPilot Pro can run locally with SQLite or in production with PostgreSQL / Google Cloud SQL. The application does not require a hosted lead database SaaS.

- **Production persistence**: Cloud Run can connect to PostgreSQL through `LEADPILOT_DB_URL`; SQLite remains available for local development and deterministic tests.
- **Human approval gates**: Discovery, qualification, Sales Campaign approval, and legacy outreach sending remain separate stages.
- **Direct SMTP/IMAP**: Connects directly to your mail infrastructure rather than a shared sending network.
- **Security controls**: Suppression lists, business-email validation, explicit send confirmation, session cookies, and audit events protect the outreach path.

---

## 📈 Why LeadPilot Pro?

Most outreach tools force you to choose between **Scale** and **Personalization**. 
LeadPilot Pro gives you both. By automating the heavy lifting of data collection and inbox management, it frees your sales team to focus entirely on approving high-quality leads and writing personalized hooks. The result? Higher open rates, more replies, and a pristine domain reputation.
