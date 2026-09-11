import urllib.request
import re
import json

urls = [
    ('Stepstone RSS 1', 'https://www.stepstone.at/rss/software-developer-wien.xml'),
    ('Stepstone RSS 2', 'https://www.stepstone.at/rss/data-wien.xml'),
    ('Careerjet AT', 'https://www.careerjet.at/rss/jobs?s=developer&l=wien'),
    ('NoFluffJobs AT', 'https://nofluffjobs.com/api/search/posting?region=at')
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}

for name, url in urls:
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=5)
        text = res.read().decode('utf-8', errors='ignore')
        print(f'{name}: Success! Length: {len(text)}')
        items = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
        if items:
            print(f' {name} RSS items count:', len(items))
            for item in items[:3]:
                title = re.search(r'<title>(.*?)</title>', item)
                link = re.search(r'<link>(.*?)</link>', item)
                print('   -', title.group(1) if title else '', '|', link.group(1) if link else '')
    except Exception as e:
        print(f'{name}: {e}')
