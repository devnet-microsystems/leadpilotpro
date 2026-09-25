const fs = require('fs');
const cheerio = require('cheerio');
const { execSync } = require('child_process');

const html_bak = fs.readFileSync('static/index.html.bak', 'utf8');
const html_head = execSync('git show HEAD:static/index.html').toString();

const $bak = cheerio.load(html_bak, { recognizeSelfClosing: true });
const $head = cheerio.load(html_head, { recognizeSelfClosing: true });

// We need a pristine new HTML structure.
const nav_html = `
<nav class="sidebar">
    <div class="logo">
        <h2>LeadPilot Pro</h2>
    </div>

    <div class="nav-section">
        <div class="nav-section-title">RESEARCH 2.0</div>
        <a href="#" class="nav-item active" data-tab="tab-dashboard">Dashboard Analytics</a>
        <a href="#" class="nav-item" data-tab="tab-research-campaigns">Research Campaigns</a>
        <a href="#" class="nav-item" data-tab="tab-query-studio">Query Studio</a>
        <a href="#" class="nav-item" data-tab="tab-companies">Companies</a>
        <a href="#" class="nav-item" data-tab="tab-providers">Providers</a>
    </div>

    <div class="nav-section">
        <div class="nav-section-title">LEGACY OUTREACH</div>
        <a href="#" class="nav-item" data-tab="tab-pending">Pending Review</a>
        <a href="#" class="nav-item" data-tab="tab-approved">Approved Leads</a>
        <a href="#" class="nav-item" data-tab="tab-rejected">Rejected Leads</a>
        <a href="#" class="nav-item" data-tab="tab-campaigns">Outreach Campaigns</a>
        <a href="#" class="nav-item" data-tab="tab-templates">Templates</a>
        <a href="#" class="nav-item" data-tab="tab-send">Sender Queue</a>
        <a href="#" class="nav-item" data-tab="tab-quicksend">Quick Send</a>
        <a href="#" class="nav-item" data-tab="tab-archive">Email Archive</a>
    </div>

    <div class="nav-section">
        <div class="nav-section-title">SYSTEM</div>
        <a href="#" class="nav-item" data-tab="tab-settings">Settings (SMTP/IMAP)</a>
        <a href="#" class="nav-item" data-tab="tab-research">Legacy Queries & Logs</a>
    </div>
</nav>
`;

let combined_tabs_html = "";

// 1. Research 2.0 tabs (from HEAD)
const head_tabs = ['tab-dashboard', 'tab-research-campaigns', 'tab-query-studio', 'tab-companies', 'tab-providers'];
head_tabs.forEach(id => {
    let t = $head('#' + id);
    if(t.length) {
        if(id === 'tab-dashboard') t.addClass('active');
        else t.removeClass('active');
        combined_tabs_html += $head.html(t) + '\n';
    }
});

// 2. Legacy tabs (from bak)
const legacy_tabs = ['tab-pending', 'tab-approved', 'tab-rejected', 'tab-campaigns', 'tab-templates', 'tab-send', 'tab-quicksend', 'tab-archive', 'tab-settings', 'tab-research'];
legacy_tabs.forEach(id => {
    let t = $bak('#' + id);
    if(t.length) {
        t.removeClass('active'); // ensure no active class
        combined_tabs_html += $bak.html(t) + '\n';
    }
});

let combined_extras_html = "";
// Find modals in bak
$bak('div[style*="position:fixed"], div[style*="position: fixed"]').each((i, el) => {
    if ($bak(el).attr('id')) {
        combined_extras_html += $bak.html(el) + '\n';
    }
});
// Find modals in head that are NOT in bak
$head('div[style*="position:fixed"], div[style*="position: fixed"]').each((i, el) => {
    const id = $head(el).attr('id');
    if (id && !$bak('#' + id).length) {
        combined_extras_html += $head.html(el) + '\n';
    }
});

// Any extra global elements like notification container
let notifications = $head('#notification-container');
if(notifications.length) combined_extras_html += $head.html(notifications) + '\n';

const final_html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LeadPilot Pro - Unified OSINT & Outreach</title>
    <link rel="stylesheet" href="/static/style.css">
    <style>
        .nav-section { margin-top: 20px; }
        .nav-section-title { color: var(--text-muted); font-size: 0.75rem; font-weight: bold; padding: 0 1rem; margin-bottom: 0.5rem; letter-spacing: 0.05em; text-transform: uppercase; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="layout">
        ${nav_html}
        <main class="content">
            ${combined_tabs_html}
        </main>
    </div>
    
    ${combined_extras_html}
    
    <script src="/static/app.js"></script>
    <script src="/static/research.js"></script>
    <script src="/static/legacy_outreach.js"></script>
</body>
</html>`;

fs.writeFileSync('static/index.html', final_html);
console.log("Written successfully.");
