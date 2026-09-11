import json
import re

def is_strictly_english(title, description=""):
    text = (title + " " + description).lower()
    
    # 1. German Title Check: Common German job title nouns
    german_title_patterns = [
        r'\bentwickler\b', r'\bentwicklerin\b', r'\bmitarbeiter\b', r'\bmitarbeiterin\b',
        r'\bberater\b', r'\bberaterin\b', r'\bprojektleiter\b', r'\bprojektleiterin\b',
        r'\btechniker\b', r'\btechnikerin\b', r'\bspezialist\b', r'\bspezialistin\b',
        r'\bfachkraft\b', r'\bführungskraft\b', r'\bleitung\b'
    ]
    for pattern in german_title_patterns:
        if re.search(pattern, title.lower()):
            return False
            
    # 2. German Vocabulary Words (Strong indicators of German text)
    german_words = [
        ' und ', ' mit ', ' für ', ' der ', ' die ', ' das ', ' dem ', ' den ', ' ein ', ' eine ',
        'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil',
        'erfahrung', 'kenntnisse', 'bereich', 'abgeschlossenes', 'dienstort', 'gehalt',
        'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'anforderung', 'bieten wir',
        'unserem team', 'sowie', 'oder', 'nachhaltig'
    ]
    
    german_hits = sum(1 for w in german_words if w in text)
    
    # 3. English Vocabulary Words
    english_words = [
        ' the ', ' and ', ' with ', ' for ', ' you ', ' our ', ' team ', ' working ',
        ' experience ', ' role ', ' responsible ', ' requirements ', ' looking ', ' candidate ',
        ' skills ', ' remote ', ' location ', ' joining ', ' building ', ' developing '
    ]
    english_hits = sum(1 for w in english_words if w in text)
    
    # If German words dominate or title is German, reject
    if german_hits >= 2:
        return False
    if english_hits >= 1 or any(k in title.lower() for k in ['developer', 'engineer', 'analyst', 'manager', 'lead', 'architect', 'designer', 'specialist', 'intern']):
        return True
        
    return False

# Test against jobs.json
with open('data/jobs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

raw_jobs = data.get('jobs', [])
english_jobs = [j for j in raw_jobs if is_strictly_english(j['title'], j.get('description', ''))]

print(f'Total Raw Jobs: {len(raw_jobs)}')
print(f'Strictly English Jobs: {len(english_jobs)}')
print('\nSample Strictly English Jobs:')
for j in english_jobs[:8]:
    print(' -', j['title'], '|', j['company'], '|', j['location'])
