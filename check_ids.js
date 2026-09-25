const fs = require('fs');
const cheerio = require('cheerio');

const html = fs.readFileSync('static/index.html', 'utf8');
const $ = cheerio.load(html);

const idCounts = {};
let duplicateCount = 0;

$('[id]').each((i, el) => {
    const id = $(el).attr('id');
    idCounts[id] = (idCounts[id] || 0) + 1;
});

for (const [id, count] of Object.entries(idCounts)) {
    if (count > 1) {
        console.log("DUPLICATE ID FOUND:", id, "Count:", count);
        duplicateCount++;
    }
}

if (duplicateCount === 0) {
    console.log("STATIC CHECK PASSED: No duplicate IDs found.");
} else {
    console.log("STATIC CHECK FAILED:", duplicateCount, "duplicate IDs found.");
}
