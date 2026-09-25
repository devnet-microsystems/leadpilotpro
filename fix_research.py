import re

with open('static/app_head.js', 'r') as f:
    app_head = f.read()

with open('static/legacy_outreach.js', 'r') as f:
    legacy = f.read()

# get all window.xxx assignments
window_funcs = re.findall(r'window\.([a-zA-Z0-9_]+)\s*=\s*(?:async\s+)?function', app_head)
# get all top level async functions
async_funcs = re.findall(r'^async function ([a-zA-Z0-9_]+)', app_head, flags=re.MULTILINE)
# get all top level normal functions
normal_funcs = re.findall(r'^function ([a-zA-Z0-9_]+)', app_head, flags=re.MULTILINE)

# same for legacy to find the diff
legacy_funcs = set()
legacy_funcs.update(re.findall(r'async function ([a-zA-Z0-9_]+)', legacy))
legacy_funcs.update(re.findall(r'function ([a-zA-Z0-9_]+)', legacy))
legacy_funcs.update(re.findall(r'window\.([a-zA-Z0-9_]+)\s*=\s*(?:async\s+)?function', legacy))

research_only = set(window_funcs + async_funcs + normal_funcs) - legacy_funcs - {'fetch', 'switchTab'}

print("Research only functions:", research_only)
