import re

def extract_div(content, start_marker):
    start_idx = content.find(start_marker)
    if start_idx == -1: return ""
    
    div_count = 0
    in_div = False
    
    for i in range(start_idx, len(content)):
        # Very simple tag counting
        if content[i:i+4] == "<div":
            div_count += 1
            in_div = True
        elif content[i:i+6] == "</div":
            div_count -= 1
            
        if in_div and div_count == 0:
            end_idx = content.find(">", i) + 1
            return content[start_idx:end_idx]
            
    return ""

with open("static/index.html.bak", "r") as f:
    bak = f.read()

tabs_to_extract = [
    ('id="tab-overview"', 'id="tab-dashboard" class="tab-content"'),
    ('id="tab-research_campaigns"', 'id="tab-research-campaigns" class="tab-content"'),
    ('id="tab-query_studio"', 'id="tab-query-studio" class="tab-content"'),
    ('id="tab-analytics"', 'id="tab-analytics" class="tab-content"')
]

extracted = []
for old_id, new_id in tabs_to_extract:
    div = extract_div(bak, f'<div {old_id}')
    if div:
        # replace the opening div to have the correct ID and class
        div = re.sub(r'<div id="[^"]+"[^>]*>', f'<div {new_id}>', div, count=1)
        extracted.append(div)

with open("static/index.html", "r") as f:
    idx = f.read()

# Insert before the first tab-companies
insert_point = idx.find('<div id="tab-companies"')
if insert_point != -1:
    new_idx = idx[:insert_point] + "\n".join(extracted) + "\n" + idx[insert_point:]
    with open("static/index.html", "w") as f:
        f.write(new_idx)
    print("Tabs inserted successfully.")
else:
    print("Could not find insert point.")
