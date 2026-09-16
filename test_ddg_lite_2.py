import urllib.request, urllib.parse
data = urllib.parse.urlencode({'q': '"CTO" "SaaS" "Zurich" contact OR email'}).encode('utf-8')
req = urllib.request.Request('https://lite.duckduckgo.com/lite/', data=data, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
import re
print("Length:", len(html))
links = re.findall(r'<a rel="nofollow" href="([^"]+)"', html)
print('Nofollow links:', len(links))
