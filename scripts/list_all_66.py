import json
import re

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

print('=== INSPECTING ALL 66 TITLES IN JOBS.JSON ===\n')
for i, j in enumerate(jobs):
    print(f'{i+1}. {j["title"]}')
