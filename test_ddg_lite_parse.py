import urllib.request
import urllib.parse
import re

data = urllib.parse.urlencode({'q': 'Top Web Agencies London'}).encode('utf-8')
req = urllib.request.Request("https://lite.duckduckgo.com/lite/", data=data, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        # DDG Lite results are in <a rel="nofollow" href="URL">
        links = re.findall(r'<a rel="nofollow" href="([^"]+)"', html)
        for link in links:
            if not link.startswith('//lite.duckduckgo.com') and not link.startswith('/lite/'):
                print(link)
except Exception as e:
    print("Error:", e)
