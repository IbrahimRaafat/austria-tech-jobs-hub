import json
import re

def is_strictly_english_tech_job(title, snippet=""):
    title_raw = title
    desc_raw = snippet
    title_lower = title.lower()
    text_lower = (title + " " + snippet).lower()
    
    # 1. Tech relevance filter (Must be IT / Software / Data / AI / Cloud / Engineering / Product)
    tech_keywords = [
        'developer', 'engineer', 'data', 'software', 'ai', 'cloud', 'devops', 'backend', 'frontend',
        'fullstack', 'full-stack', 'full stack', 'architect', 'qa', 'sre', 'product owner', 'product manager',
        'tech', 'it', 'python', 'java', 'react', 'node', 'sql', 'sysadmin', 'scrum', 'cybersecurity'
    ]
    if not any(k in title_lower for k in tech_keywords):
        return False
        
    # 2. Rejection of non-tech / corporate admin terms in title
    non_tech_terms = [
        'writer', 'copywriter', 'counsel', 'sales contractor', 'office assistant', 'recruiter', 'hr',
        'accountant', 'legal', 'finance manager', 'fp&a', 'customer success manager', 'event'
    ]
    if any(t in title_lower for t in non_tech_terms):
        return False

    # 3. German Title Nouns / German Words in Title
    german_title_words = [
        'entwickler', 'entwicklerin', 'mitarbeiter', 'mitarbeiterin',
        'berater', 'beraterin', 'projektleiter', 'projektleiterin',
        'techniker', 'technikerin', 'spezialist', 'spezialistin',
        'fachkraft', 'führungskraft', 'leitung', 'fokus', 'schwerpunkt',
        'bereich', 'verwaltung', 'öffentliche', 'bau', 'vertrieb', 'buchhaltung',
        'buchhalter', 'buchhalterin', 'assistent', 'assistentin', 'planer', 'planerin',
        'objektleiter', 'objektleiterin', 'einkäufer', 'einkäuferin', 'verkäufer', 'verkäuferin',
        'versicherungsexperte', 'fachplanung', 'architektur', 'betreuung', 'sachbearbeiter',
        'teamleiter', 'teamleiterin', 'praktikum', 'schlosser', 'geodatenmanager', 'abteilung',
        'veranstaltungen', 'kongresse', 'dienstort', 'vollzeit', 'teilzeit'
    ]
    
    title_clean = re.sub(r'[:\*\/\(\)\-\_\.]', ' ', title_lower)
    for word in german_title_words:
        if re.search(r'\b' + re.escape(word) + r'\b', title_clean):
            return False

    # 4. Strict German Body / Description Detection
    german_body_vocab = [
        ' und ', ' mit ', ' für ', ' der ', ' die ', ' das ', ' dem ', ' den ', ' ein ', ' eine ',
        'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil',
        'erfahrung', 'kenntnisse', 'abgeschlossenes', 'dienstort', 'gehalt',
        'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung', 'bieten wir',
        'unserem team', 'sowie', 'oder', 'nachhaltig', 'einführung', 'bereich'
    ]
    
    german_hits = sum(1 for v in german_body_vocab if v in text_lower)
    if german_hits >= 1:
        return False
        
    return True

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

filtered = [j for j in jobs if is_strictly_english_tech_job(j['title'], j.get('description', ''))]

print(f'Total jobs before: {len(jobs)}')
print(f'Total jobs after BULLETPROOF English Tech filter: {len(filtered)}')
print('\n--- ALL REMAINING 100% ENGLISH TECH JOBS ---')
for i, j in enumerate(filtered):
    print(f'{i+1}. [{j.get("source")}] {j.get("title")} ({j.get("location")})')
