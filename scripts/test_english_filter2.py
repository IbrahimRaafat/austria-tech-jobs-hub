import json
import re

def is_strictly_english(title, description=""):
    text = (title + " " + description).lower()
    title_lower = title.lower()
    
    # German title keywords (German nouns/conjunctions in job titles)
    german_title_terms = [
        'entwickler', 'entwicklerin', 'mitarbeiter', 'mitarbeiterin',
        'berater', 'beraterin', 'projektleiter', 'projektleiterin',
        'techniker', 'technikerin', 'spezialist', 'spezialistin',
        'fachkraft', 'führungskraft', 'leitung', 'fokus', 'schwerpunkt',
        'bereich', 'verwaltung', 'öffentliche', 'bau', 'vertrieb', 'buchhaltung'
    ]
    for term in german_title_terms:
        if re.search(r'\b' + re.escape(term) + r'\b', title_lower):
            return False
            
    # German stop words & phrases in description or title
    german_phrases = [
        ' und ', ' mit ', ' für ', ' der ', ' die ', ' das ', ' dem ', ' den ', ' ein ', ' eine ',
        'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil',
        'erfahrung', 'kenntnisse', 'abgeschlossenes', 'dienstort', 'gehalt',
        'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung', 'bieten wir',
        'unserem team', 'sowie', 'oder', 'nachhaltig'
    ]
    
    german_count = sum(1 for p in german_phrases if p in text)
    if german_count >= 2:
        return False
        
    return True

# Test against jobs.json
with open('data/jobs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

raw_jobs = data.get('jobs', [])
english_jobs = [j for j in raw_jobs if is_strictly_english(j['title'], j.get('description', ''))]

print(f'Total Raw Jobs: {len(raw_jobs)}')
print(f'Strictly English Jobs: {len(english_jobs)}')
print('\nSample Strictly English Jobs:')
for j in english_jobs[:10]:
    print(' -', j['title'], '|', j['company'], '|', j['location'])
