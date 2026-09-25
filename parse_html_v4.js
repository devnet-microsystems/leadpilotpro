const fs = require('fs');
const cheerio = require('cheerio');
const { execSync } = require('child_process');

const html_bak = fs.readFileSync('static/index.html.bak', 'utf8');
const html_head = execSync('git show HEAD:static/index.html').toString();

const $bak = cheerio.load(html_bak);
const $head = cheerio.load(html_head);

const tabs = {};

// We want to collect tabs.
$bak('div.tab-content').each((i, el) => {
    tabs[$bak(el).attr('id')] = $bak.html(el);
});

$head('div.tab-content').each((i, el) => {
    const id = $head(el).attr('id');
    // Research 2.0 tabs:
    if (['tab-dashboard', 'tab-research-campaigns', 'tab-query-studio', 'tab-companies', 'tab-providers'].includes(id)) {
        tabs[id] = $head.html(el);
    }
});

console.log("Bak tabs:", Object.keys(tabs).filter(k => html_bak.includes(k)));
console.log("Head tabs:", Object.keys(tabs).filter(k => html_head.includes(k)));

// Find modals
const modals = {};
$bak('div[style*="position:fixed"], div[style*="position: fixed"]').each((i, el) => {
    if ($bak(el).attr('id')) {
        modals[$bak(el).attr('id')] = $bak.html(el);
    }
});

$head('div[style*="position:fixed"], div[style*="position: fixed"]').each((i, el) => {
    if ($head(el).attr('id')) {
        modals[$head(el).attr('id')] = $head.html(el);
    }
});

console.log("Modals:", Object.keys(modals));
