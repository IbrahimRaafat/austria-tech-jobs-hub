import urllib.request
import re
import json

def test_stepstone():
    url = 'https://www.stepstone.at/jobs/developer/in-wien'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8')
        print('Stepstone.at HTML length:', len(html))
        # Check script blocks / Next.js / JSON-LD / schema.org
        json_ld = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        print('Stepstone JSON-LD count:', len(json_ld))
        for j in json_ld:
            try:
                data = json.loads(j)
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                    print(' Stepstone ItemList count:', len(items))
                    for item in items[:3]:
                        print('  -', item.get('item', {}).get('name') or item.get('name'))
            except Exception as e:
                pass
    except Exception as e:
        print('Stepstone error:', e)

def test_indeed():
    url = 'https://at.indeed.com/rss?q=developer&l=Wien'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        req = urllib.request.Request(url, headers=headers)
        xml = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='ignore')
        print('Indeed RSS length:', len(xml))
        items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        print('Indeed RSS items count:', len(items))
        for item in items[:3]:
            title = re.search(r'<title>(.*?)</title>', item)
            link = re.search(r'<link>(.*?)</link>', item)
            source = re.search(r'<source>(.*?)</source>', item)
            print('  -', title.group(1) if title else 'No title', '|', link.group(1) if link else '')
    except Exception as e:
        print('Indeed error:', e)

test_stepstone()
test_indeed()
