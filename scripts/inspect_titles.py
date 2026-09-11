import json

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

print('Total jobs count:', len(jobs))
print('\n--- ALL TITLES IN JOBS.JSON ---')
for i, j in enumerate(jobs):
    print(f'{i+1}. [{j.get("source")}] {j.get("title")}')
