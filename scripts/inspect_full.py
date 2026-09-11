import json

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

print('--- INSPECTING TITLES AND DESCRIPTIONS ---')
for i, j in enumerate(jobs):
    title = j.get("title")
    desc = j.get("description", "")
    source = j.get("source")
    print(f'[{i+1}] Source: {source} | Title: {title}')
    print(f'    Desc Snippet: {desc[:120]}...')
    print('---')
