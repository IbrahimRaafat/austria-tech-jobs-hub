import urllib.request
import json
import re

# Test Stepstone alternatives & Indeed RSS/Search
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
}

urls = [
    ('Stepstone 1', 'https://www.stepstone.at/work/developer/in-wien.html'),
    ('Stepstone 2', 'https://www.stepstone.at/5/ergebnisliste.html?ke=software+developer&ws=wien'),
    ('Indeed AT 1', 'https://at.indeed.com/jobs?q=developer&l=Vienna'),
    ('Indeed AT 2', 'https://at.indeed.com/rss?q=software+developer&l=Austria'),
    ('Jooble AT', 'https://at.jooble.org/api/jobs'),
]

for name, url in urls:
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=5)
        content = res.read().decode('utf-8', errors='ignore')
        print(f'{name}: Success! Length: {len(content)}')
    except Exception as e:
        print(f'{name}: {e}')
