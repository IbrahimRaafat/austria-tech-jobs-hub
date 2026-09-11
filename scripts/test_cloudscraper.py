import cloudscraper
import json
import re

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

print('--- Testing Stepstone.at ---')
try:
    r = scraper.get('https://www.stepstone.at/work/developer/in-wien.html')
    print('Stepstone status:', r.status_code, 'Length:', len(r.text))
    json_ld = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    print('Stepstone JSON-LD count:', len(json_ld))
    for j in json_ld:
        try:
            d = json.loads(j)
            if isinstance(d, dict) and d.get('@type') == 'ItemList':
                items = d.get('itemListElement', [])
                print(' Stepstone ItemList count:', len(items))
                for item in items[:5]:
                    name = item.get('item', {}).get('name') or item.get('name')
                    url = item.get('item', {}).get('url') or item.get('url')
                    print('  -', name, '|', url)
        except Exception as e:
            pass
except Exception as e:
    print('Stepstone error:', e)

print('--- Testing Indeed AT ---')
try:
    r = scraper.get('https://at.indeed.com/jobs?q=developer&l=Vienna')
    print('Indeed status:', r.status_code, 'Length:', len(r.text))
    titles = re.findall(r'aria-label="full details of ([^"]+)"', r.text, re.IGNORECASE)
    print('Indeed titles found:', len(titles))
    for t in titles[:5]:
        print('  -', t)
except Exception as e:
    print('Indeed error:', e)
