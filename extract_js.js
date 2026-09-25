const fs = require('fs');

const orig = fs.readFileSync('static/app.js.orig', 'utf8');
const head = fs.readFileSync('static/app_head.js', 'utf8');

const origFuncs = new Set();
for (const match of orig.matchAll(/function ([a-zA-Z0-9_]+)/g)) { origFuncs.add(match[1]); }
for (const match of orig.matchAll(/window\.([a-zA-Z0-9_]+)\s*=/g)) { origFuncs.add(match[1]); }

// We want to extract chunks from head that define functions not in origFuncs
// Since head is mostly `window.funcName = async function...` or `async function funcName...`
// We can just split by lines and look for blocks.
const lines = head.split('\n');
const blocks = [];
let currentBlock = [];
let inBlock = false;
let blockName = null;
let braceCount = 0;

for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Start of a function block
    let match = line.match(/^(?:async )?function ([a-zA-Z0-9_]+)/);
    if (!match) match = line.match(/^window\.([a-zA-Z0-9_]+)\s*=\s*(?:async )?function/);
    
    if (match && !inBlock) {
        inBlock = true;
        blockName = match[1];
        currentBlock = [];
        braceCount = 0;
    }
    
    if (inBlock) {
        currentBlock.push(line);
        braceCount += (line.match(/\{/g) || []).length;
        braceCount -= (line.match(/\}/g) || []).length;
        
        if (braceCount <= 0 && currentBlock.some(l => l.includes('{'))) {
            if (!origFuncs.has(blockName) && blockName !== 'fetch' && blockName !== 'switchTab') {
                blocks.push(currentBlock.join('\n'));
            }
            inBlock = false;
            blockName = null;
        }
    }
}

fs.writeFileSync('static/research.js', blocks.join('\n\n'));
console.log("Extracted to research.js", blocks.length, "functions.");
