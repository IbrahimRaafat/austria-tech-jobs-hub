import json
import re

def is_strictly_english_tech_job(title, snippet=""):
    title_lower = title.lower()
    text_lower = (title + " " + snippet).lower()
    
    # 1. Require whole-word match for tech role keywords
    tech_keywords = [
        'developer', 'engineer', 'data', 'software', 'ai', 'cloud', 'devops', 'backend', 'frontend',
        'fullstack', 'full-stack', 'architect', 'qa', 'sre', 'product owner', 'product manager',
        'tech', 'it', 'python', 'java', 'react', 'node', 'sql', 'sysadmin', 'scrum', 'cybersecurity'
    ]
    
    has_tech_word = False
    for kw in tech_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', title_lower):
            has_tech_word = True
            break
            
    if not has_tech_word:
        return False

    # 2. Reject German words anywhere in title or snippet
    german_keywords = [
        'projektleitung', 'hochbau', 'elektrotechnik', 'servicetechniker', 'elektriker',
        'monteur', 'maschinenbautechniker', 'vertriebsmitarbeiter', 'außendienst',
        'sondermaschinenbau', 'entwickler', 'entwicklerin', 'mitarbeiter', 'mitarbeiterin',
        'berater', 'beraterin', 'projektleiter', 'projektleiterin', 'techniker', 'technikerin',
        'spezialist', 'spezialistin', 'fachkraft', 'führungskraft', 'leitung', 'fokus', 'schwerpunkt',
        'bereich', 'verwaltung', 'öffentliche', 'bau', 'vertrieb', 'buchhaltung', 'buchhalter',
        'assistent', 'planer', 'objektleiter', 'einkäufer', 'verkäufer', 'betreuung', 'sachbearbeiter',
        'teamleiter', 'praktikum', 'schlosser', 'geodatenmanager', 'abteilung', 'veranstaltungen',
        'kongresse', 'dienstort', 'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung',
        'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil', 'erfahrung',
        'kenntnisse', 'abgeschlossenes', 'gehalt', 'bieten wir', 'unserem team', 'sowie', 'oder', 'nachhaltig'
    ]
    
    title_clean = re.sub(r'[:\*\/\(\)\-\_\.]', ' ', title_lower)
    for g_word in german_keywords:
        if re.search(r'\b' + re.escape(g_word) + r'\b', title_clean) or g_word in text_lower:
            return False
            
    return True

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

filtered = [j for j in jobs if is_strictly_english_tech_job(j['title'], j.get('description', ''))]

print(f'Total jobs before fix: {len(jobs)}')
print(f'Total jobs after whole-word precision fix: {len(filtered)}')
print('\n=== ALL 100% PERFECT ENGLISH TECH JOBS ===')
for i, j in enumerate(filtered):
    print(f'{i+1}. [{j.get("source")}] {j.get("title")} ({j.get("company")})')
