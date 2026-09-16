import urllib.request
import urllib.parse

data = urllib.parse.urlencode({'q': 'Top Web Agencies London'}).encode('utf-8')
req = urllib.request.Request("https://lite.duckduckgo.com/lite/", data=data, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        print("Success, length:", len(html))
        if 'Top Web' in html or 'Agency' in html:
            print("Found relevant words.")
        else:
            print("Not found.")
except Exception as e:
    print("Error:", e)
