import json
import re

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

print(f'=== TOTAL JOBS TO AUDIT: {len(jobs)} ===\n')

german_found_count = 0
english_clean_count = 0

german_markers = [
    'und', 'mit', 'für', 'der', 'die', 'das', 'dem', 'den', 'ein', 'eine', 'einer', 'einem',
    'suchen', 'aufgaben', 'profil', 'erfahrung', 'kenntnisse', 'bereich', 'abgeschlossenes',
    'dienstort', 'gehalt', 'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung',
    'bieten', 'unserem', 'team', 'sowie', 'oder', 'nachhaltig', 'einführung', 'entwickler',
    'mitarbeiter', 'berater', 'projektleiter', 'techniker', 'spezialist', 'fachkraft',
    'führungskraft', 'leitung', 'fokus', 'schwerpunkt', 'verwaltung', 'öffentliche', 'bau',
    'vertrieb', 'buchhaltung', 'assistent', 'planer', 'objektleiter', 'einkäufer', 'verkäufer',
    'betreuung', 'sachbearbeiter', 'teamleiter', 'praktikum', 'schlosser', 'abteilung', 'w/m/d', 'm/w/d', 'w/m/x'
]

for i, j in enumerate(jobs):
    title = j.get('title', '')
    desc = j.get('description', '')
    source = j.get('source', '')
    company = j.get('company', '')
    location = j.get('location', '')
    
    text = (title + " " + desc).lower()
    text_words = re.findall(r'\b[a-zäöüß]+\b', text)
    
    matched_german = [w for w in text_words if w in german_markers]
    
    if matched_german:
        german_found_count += 1
        print(f'FAIL [{i+1}] GERMAN DETECTED in [{source}]')
        print(f'   Title: {title}')
        print(f'   Company: {company} | Location: {location}')
        print(f'   Matched German Words: {set(matched_german)}')
        print(f'   Description Snippet: {desc[:150]}...')
        print('-'*50)
    else:
        english_clean_count += 1
        print(f'PASS [{i+1}] 100% ENGLISH in [{source}]')
        print(f'   Title: {title}')
        print(f'   Company: {company} | Location: {location}')
        print('-'*50)

print(f'\n=== AUDIT SUMMARY ===')
print(f'Total Jobs: {len(jobs)}')
print(f'100% Clean English Jobs: {english_clean_count}')
print(f'Jobs with German words: {german_found_count}')
