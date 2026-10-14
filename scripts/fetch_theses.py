"""
Master Thesis Aggregator for Austria.
Fetches, enriches, categorizes, and normalizes Master's thesis opportunities
across Austrian research institutes (starting with AIT) and universities/companies.

Outputs to data/theses.json.
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.request
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "theses.json")


def clean_str(s):
    if not s:
        return ""
    s = html.unescape(s)
    # Normalize unicode quotes, spaces, and dashes
    s = s.replace('\u201c', '"').replace('\u201d', '"').replace('“', '"').replace('”', '"')
    s = s.replace('«', '"').replace('»', '"').replace('„', '"')
    s = s.replace('–', '-').replace('—', '-')
    s = s.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def categorize_thesis(title, text):
    combined = (title + " " + text).lower()
    if any(k in combined for k in ['cybersecurity', 'security', 'wireless', 'network', '5g', '6g', 'communication', 'sdr', 'antenna', 'propagation', 'sensing', 'cryptography']):
        return "Cybersecurity & Networks"
    if any(k in combined for k in ['world models', 'physical ai', 'computer vision', 'machine learning', 'deep learning', 'neural', 'artificial intelligence', 'nlp', 'data science', 'ai ']):
        return "AI & Data Science"
    if any(k in combined for k in ['motorcycle', 'vehicle', 'automotive', 'transport', 'traffic', 'mobility', 'uav', 'drone', 'driving dynamics']):
        return "Mobility & Autonomous Systems"
    if any(k in combined for k in ['biosensor', 'bioresources', 'health', 'medical', 'biological', 'biotech', 'nucleic']):
        return "Health & Biotech"
    if any(k in combined for k in ['robot', 'automation', 'embedded', 'sensor', 'hardware', 'iot', 'semiconductor']):
        return "Robotics & Hardware"
    return "Software & Systems"


def detect_language(title, text):
    sample = (title + " " + text[:400]).lower()
    german_indicators = ['masterarbeit', 'diplomarbeit', 'für die', 'über uns', 'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'voraussetzungen', 'unser ziel']
    german_hits = sum(1 for w in german_indicators if w in sample)
    if 'master thesis' in sample or 'master-thesis' in sample:
        return "English"
    if german_hits >= 1 or 'masterarbeit' in sample:
        return "German"
    return "English"


def extract_thesis_tags(title, text):
    vocab = [
        '5G/6G', 'AI', 'MIMO', 'SDR', 'Wireless', 'Cybersecurity', 'Machine Learning',
        'Deep Learning', 'Computer Vision', 'Robotics', 'IoT', 'UAV', 'Antennas',
        'Physical AI', 'Sensors', 'Biosensors', 'Python', 'C++', 'MATLAB', 'Simulation',
        'Signal Processing', 'Ray Tracing', 'Dynamics', 'Hardware', 'Cloud', 'Embedded'
    ]
    combined = (title + " " + text).lower()
    tags = []
    for word in vocab:
        w_low = word.lower()
        if re.search(r'\b' + re.escape(w_low) + r'\b', combined):
            tags.append(word)
    return tags[:6]


def parse_duration_and_workload(raw_text):
    duration = "6 months"
    workload = "20 hrs/week"
    compensation = "Paid (Collective Agreement)"

    # Clean tags from text first to avoid tag boundary splits like 1</strong><strong>027
    plain = re.sub(r'<[^>]+>', '', raw_text)
    plain = plain.replace('\xa0', ' ')

    # Duration match
    m_dur = re.search(r'(?:Duration|Dauer)(?:[^\n:]{0,40})?:\s*([^\n\.<]+)', plain, re.IGNORECASE)
    if m_dur:
        dur_val = clean_str(m_dur.group(1))
        # Ensure it looks like a duration
        if any(w in dur_val.lower() for w in ['month', 'monat', 'woche', 'week', 'jahr', 'year']):
            duration = dur_val

    # Salary / Compensation match
    m_sal = re.search(
        r'(?:EUR|€)\s*([\d\s\.,]+)\s*(?:gross|brutto)?\s*(?:per month|pro Monat)?(?:\s*(?:for|für)\s*(\d+)\s*(?:hours|Stunden))?',
        plain,
        re.IGNORECASE
    )
    if m_sal:
        amount_str = clean_str(m_sal.group(1)).replace(' ', '')
        hours = m_sal.group(2) or "20"
        if amount_str and amount_str != '1':
            compensation = f"€{amount_str} / month"
            workload = f"{hours} hrs/week"
    elif "1273" in plain:
        compensation = "€1,273 / month"
        workload = "20 hrs/week"
    elif "kollektivvertrag" in plain.lower() or "collective agreement" in plain.lower():
        compensation = "Paid (Collective Agreement)"

    return duration, workload, compensation


def fetch_ait_theses():
    """
    Fetches Master Thesis positions from AIT (Austrian Institute of Technology).
    Queries the dedicated Studierende profile view:
    https://jobs.ait.ac.at/Jobs?jobProfiles=Studierende
    and parses rich thesis metadata (research group, stipend, duration, tasks).
    """
    print("[Theses Scraper] Fetching AIT (Austrian Institute of Technology) thesis positions...")
    url = 'https://jobs.ait.ac.at/Jobs?jobProfiles=Studierende'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

    try:
        req = urllib.request.Request(url, headers=headers)
        page_html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching AIT jobs: {e}")
        return []

    m = re.search(r'new JobList\(\s*\$\("#jobListPlaceholder"\),\s*\$\("#jobListTemplate"\),\s*(\{.*?\})\s*\);', page_html, re.DOTALL)
    if not m:
        print("Error: could not locate embedded JobList JSON on AIT page")
        return []

    try:
        data = json.loads(m.group(1))
    except Exception as e:
        print(f"Error parsing AIT JSON: {e}")
        return []

    candidates = data.get('Jobs', [])
    theses = []

    for entry in candidates:
        jid = entry.get('Id')
        raw_title = entry.get('Title', '')
        title = clean_str(raw_title)
        center = clean_str(entry.get('SubTitle', ''))
        loc = clean_str(entry.get('Location', '')) or 'Vienna'

        # Must be a thesis or student research role
        is_thesis = any(k in title.lower() for k in ['thesis', 'masterarbeit', 'diplomarbeit', 'master-thesis', 'master thesis'])
        if not is_thesis:
            continue

        detail_url = f"https://jobs.ait.ac.at/Job/{jid}"
        detail_raw = ""
        soup = None
        main = None

        try:
            req_d = urllib.request.Request(detail_url, headers=headers)
            d_html = urllib.request.urlopen(req_d, timeout=15).read().decode('utf-8', errors='ignore')
            detail_raw = d_html
            soup = BeautifulSoup(d_html, 'html.parser')
            main = soup.find('main') or soup.find('div', id='content')
        except Exception as e:
            print(f"  Error fetching detail for AIT-{jid}: {e}")

        detail_text = main.get_text('\n', strip=True) if main else detail_raw
        duration, workload, compensation = parse_duration_and_workload(detail_raw or detail_text)

        # Extract research group
        research_group = ""
        m_group = re.search(r'in the\s+([A-Za-z0-9\s&/-]+?)\s+(?:research group|research team)', detail_text, re.IGNORECASE)
        if not m_group:
            m_group = re.search(r'(?:research group|Forschungsgruppe|Themenbereich)\s*[:“"„]?\s*([^,\.\n“"”]+)', detail_text, re.IGNORECASE)
        if m_group:
            research_group = clean_str(m_group.group(1))

        # Build clean description
        paragraphs = []
        if main:
            for p in main.find_all(['p', 'ul']):
                t = clean_str(p.get_text(' ', strip=True))
                if len(t) > 40 and not any(skip in t.lower() for skip in [
                    'cookies', 'javascript', 'apply now', 'austria\'s largest research',
                    'unsere internationalen teams', 'tomorrow today', 'skip to', 'sign in / sign up'
                ]):
                    paragraphs.append(t)
        desc = " ".join(paragraphs[:3])
        if not desc:
            desc = f"{title} master's thesis at AIT ({center}) in {loc}."

        lang = detect_language(title, desc)
        cat = categorize_thesis(title, desc)
        tags = extract_thesis_tags(title, desc)

        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        thesis = {
            "id": f"ait-thesis-{jid}",
            "title": title,
            "degree_level": "Master's Thesis",
            "institution": "AIT Austrian Institute of Technology",
            "institution_logo": "https://www.ait.ac.at/fileadmin/templates/img/logo_ait.svg",
            "department": center,
            "research_group": research_group,
            "location": loc,
            "duration": duration,
            "workload": workload,
            "compensation": compensation,
            "is_paid": "paid" in compensation.lower() or "€" in compensation or "eur" in compensation.lower(),
            "category": cat,
            "tags": tags,
            "language": lang,
            "description": desc[:600] + ("..." if len(desc) > 600 else ""),
            "url": detail_url,
            "source": "AIT (Austrian Institute of Technology)",
            "posted_at": today,
            "first_seen": today
        }
        theses.append(thesis)
        print(f"  + [{thesis['id']}] {thesis['title']} | {thesis['compensation']} | {thesis['duration']} | {thesis['language']}")

    return theses


# Extensible list of thesis sources across Austria
THESIS_SOURCES = [
    ("AIT Austrian Institute of Technology", fetch_ait_theses),
    # Future providers will plug in here (TU Wien, TU Graz, SAL, Joanneum Research, etc.)
]


def load_previous_theses(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f).get('theses', [])
    except (OSError, ValueError):
        return []


def main():
    print("=== Austrian Master Thesis Opportunities Aggregator ===")
    os.makedirs(DATA_DIR, exist_ok=True)
    previous = load_previous_theses(OUTPUT_PATH)
    prev_by_id = {t.get('id'): t for t in previous}

    all_theses = []
    for name, fetch in THESIS_SOURCES:
        try:
            theses = fetch()
            all_theses.extend(theses)
        except Exception as e:
            print(f"Scraper error for {name}: {e}")

    # Preserve first_seen from previous dataset
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    for t in all_theses:
        prev = prev_by_id.get(t['id'])
        if prev and prev.get('first_seen'):
            t['first_seen'] = prev['first_seen']

    output_data = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_count": len(all_theses),
        "theses": all_theses
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully saved {len(all_theses)} Master Thesis opportunities to {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
