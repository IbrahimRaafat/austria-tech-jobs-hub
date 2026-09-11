import json
import re

def is_strictly_english_job(title, snippet=""):
    # Normalize title: replace punctuation with space for clean token matching
    title_clean = re.sub(r'[:\*\/\(\)\-\_\.]', ' ', title.lower())
    text_clean = (title_clean + " " + snippet).lower()
    
    # 1. German Job Role Nouns & Titles
    german_title_words = [
        'entwickler', 'entwicklerin', 'mitarbeiter', 'mitarbeiterin',
        'berater', 'beraterin', 'projektleiter', 'projektleiterin',
        'techniker', 'technikerin', 'spezialist', 'spezialistin',
        'fachkraft', 'führungskraft', 'leitung', 'fokus', 'schwerpunkt',
        'bereich', 'verwaltung', 'öffentliche', 'bau', 'vertrieb', 'buchhaltung',
        'assistent', 'assistentin', 'planer', 'planerin', 'objektleiter', 'objektleiterin',
        'einkäufer', 'einkäuferin', 'verkäufer', 'verkäuferin', 'versicherungsexperte',
        'fachplanung', 'architektur', 'betreuung', 'sachbearbeiter', 'teamleiter', 'teamleiterin',
        'praktikum', 'schlosser', 'geodatenmanager', 'abteilung', 'versicherungsberater',
        'hr business partner', 'personalreferent'
    ]
    
    for word in german_title_words:
        if word in title_clean:
            return False
            
    # 2. German Grammar / Vocabulary in description or title
    german_vocab = [
        ' und ', ' mit ', ' für ', ' der ', ' die ', ' das ', ' dem ', ' den ', ' ein ', ' eine ',
        'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil',
        'erfahrung', 'kenntnisse', 'abgeschlossenes', 'dienstort', 'gehalt',
        'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung', 'bieten wir',
        'unserem team', 'sowie', 'oder', 'nachhaltig', 'einführung'
    ]
    
    german_hits = sum(1 for v in german_vocab if v in text_clean)
    if german_hits >= 1:
        return False
        
    return True

with open('data/jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f).get('jobs', [])

filtered = [j for j in jobs if is_strictly_english_job(j['title'], j.get('description', ''))]

print(f'Total jobs before: {len(jobs)}')
print(f'Total jobs after bulletproof strict filter: {len(filtered)}')
print('\n--- ALL REMAINING STRICTLY ENGLISH JOBS ---')
for i, j in enumerate(filtered):
    print(f'{i+1}. [{j.get("source")}] {j.get("title")}')
