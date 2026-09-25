const fs = require('fs');
const cheerio = require('cheerio');
const { execSync } = require('child_process');

const html_bak = fs.readFileSync('static/index.html.bak', 'utf8');
const html_head = execSync('git show HEAD:static/index.html').toString();

const $bak = cheerio.load(html_bak);
const $head = cheerio.load(html_head);

console.log("Head tabs:");
$head('div[id^="tab-"]').each((i, el) => console.log($head(el).attr('id')));

console.log("\nBak tabs:");
$bak('div[id^="tab-"]').each((i, el) => console.log($bak(el).attr('id')));
