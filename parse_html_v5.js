const fs = require('fs');
const cheerio = require('cheerio');

const html_bak = fs.readFileSync('static/index.html.bak', 'utf8');
const $bak = cheerio.load(html_bak);

const ids = [];
$bak('[id]').each((i, el) => {
    ids.push($bak(el).attr('id'));
});

console.log(ids.filter(id => id.startsWith('tab-') || id.includes('smtp') || id.includes('imap') || id.includes('lusha') || id.includes('log')));
