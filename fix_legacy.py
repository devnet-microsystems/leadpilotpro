import re

with open('static/app.js.orig', 'r') as f:
    orig = f.read()

# remove originalFetch block
orig = re.sub(r'const originalFetch = window\.fetch;.*?return res;\n};\n', '', orig, flags=re.DOTALL)

# remove DOMContentLoaded block
orig = re.sub(r'document\.addEventListener\(\'DOMContentLoaded\', \(\) => \{.*?\n\}\);\n', '', orig, flags=re.DOTALL)

# remove switchTab function
orig = re.sub(r'function switchTab\(tabId\) \{.*?\n\}\n', '', orig, flags=re.DOTALL)

with open('static/legacy_outreach.js', 'w') as f:
    f.write(orig)
