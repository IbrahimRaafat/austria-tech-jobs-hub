import json
import re

def is_strictly_english_job(title, snippet=""):
    title_lower = title.lower()
    text = (title + " " + snippet).lower()
    
    # 1. German Role Title Words (If any of these occur in the title, it's German)
    german_title_words = [
        'entwickler', 'entwicklerin', 'mitarbeiter', 'mitarbeiterin',
        'berater', 'beraterin', 'projektleiter', 'projektleiterin',
        'techniker', 'technikerin', 'spezialist', 'spezialistin',
        'fachkraft', 'führungskraft', 'leitung', 'fokus', 'schwerpunkt',
        'bereich', 'verwaltung', 'öffentliche', 'bau', 'vertrieb', 'buchhaltung',
        'assistent', 'assistentin', 'planer', 'planerin', 'objektleiter', 'objektleiterin',
        'einkäufer', 'einkäuferin', 'verkäufer', 'verkäuferin', 'versicherungsexperte',
        'fachplanung', 'architektur', 'betreuung', 'sachbearbeiter', 'teamleiter', 'teamleiterin'
    ]
    
    for word in german_title_words:
        if re.search(r'\b' + re.escape(word) + r'\b', title_lower):
            return False
            
    # 2. Check German vocabulary in raw text
    german_vocab = [
        ' und ', ' mit ', ' für ', ' der ', ' die ', ' das ', ' dem ', ' den ', ' ein ', ' eine ',
        'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil',
        'erfahrung', 'kenntnisse', 'abgeschlossenes', 'dienstort', 'gehalt',
        'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung', 'bieten wir',
        'unserem team', 'sowie', 'oder', 'nachhaltig'
    ]
    
    german_hits = sum(1 for v in german_vocab if v in text)
    if german_hits >= 2:
        return False
        
    return True

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

filtered = [j for j in jobs if is_strictly_english_job(j['title'], j.get('description', ''))]

print(f'Total jobs before: {len(jobs)}')
print(f'Total jobs after strict filter: {len(filtered)}')
print('\n--- ALL STRICTLY ENGLISH TITLES REMAINING ---')
for i, j in enumerate(filtered):
    print(f'{i+1}. [{j.get("source")}] {j.get("title")} ({j.get("location")})')
