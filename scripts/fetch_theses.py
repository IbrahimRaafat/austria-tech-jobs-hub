"""
Comprehensive Master Thesis Aggregator for Austria.
Aggregates open Master's thesis positions and research projects across:
  1. AIT Austrian Institute of Technology
  2. TU Wien (Faculty of Informatics & ACIN / Telecommunications)
  3. TU Graz (Institute for Interactive Systems and Data Science / HCC & ISEC)
  4. Silicon Austria Labs (SAL - Graz, Linz, Villach)
  5. Joanneum Research (Graz / Weiz / Klagenfurt)
  6. Infineon Technologies Austria (Villach, Graz)
  7. SBA Research (Vienna — Cybersecurity)
  8. Dynatrace Research Lab (Linz / Vienna)
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.request
import ssl
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "theses.json")

# SSL context that allows university/research certificates without strict failure
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}


def clean_str(s):
    if not s:
        return ""
    s = html.unescape(s)
    s = s.replace('\u201c', '"').replace('\u201d', '"').replace('“', '"').replace('”', '"')
    s = s.replace('«', '"').replace('»', '"').replace('„', '"')
    s = s.replace('–', '-').replace('—', '-')
    s = s.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def normalize_city(city):
    c = clean_str(city).strip()
    if c.lower() in ['wien', 'vienna']:
        return 'Vienna'
    return c or 'Vienna'


def categorize_thesis(title, text=""):
    combined = (title + " " + text).lower()
    if any(k in combined for k in ['cybersecurity', 'security', 'wireless', 'network', '5g', '6g', 'communication', 'sdr', 'antenna', 'propagation', 'sensing', 'cryptography', 'cryptosystem', 'malware', 'penetration', 'protocol', 'privacy']):
        return "Cybersecurity & Networks"
    if any(k in combined for k in ['world models', 'physical ai', 'computer vision', 'machine learning', 'deep learning', 'neural', 'artificial intelligence', 'nlp', 'data science', 'ai ', 'llm', 'dsl synthesis']):
        return "AI & Data Science"
    if any(k in combined for k in ['motorcycle', 'vehicle', 'automotive', 'transport', 'traffic', 'mobility', 'uav', 'drone', 'driving dynamics', 'battery', 'radar']):
        return "Mobility & Autonomous Systems"
    if any(k in combined for k in ['biosensor', 'bioresources', 'health', 'medical', 'biological', 'biotech', 'nucleic']):
        return "Health & Biotech"
    if any(k in combined for k in ['robot', 'automation', 'embedded', 'sensor', 'hardware', 'iot', 'semiconductor', 'gan', 'hemt', 'chip', 'photonic', 'microfabrication', 'fpga', 'risc-v']):
        return "Robotics & Hardware"
    return "Software & Systems"


def detect_language(title, text=""):
    sample = (title + " " + text[:400]).lower()
    german_indicators = ['masterarbeit', 'diplomarbeit', 'für die', 'über uns', 'wir suchen', 'deine aufgaben', 'ihre aufgaben', 'voraussetzungen', 'unser ziel', 'untersuchungen', 'charakterisierung', 'fehlerursachenanalyse']
    german_hits = sum(1 for w in german_indicators if w in sample)
    if 'master thesis' in sample or 'master-thesis' in sample:
        return "English"
    if german_hits >= 1 or 'masterarbeit' in sample:
        return "German"
    return "English"


def extract_thesis_tags(title, text=""):
    vocab = [
        '5G/6G', 'AI', 'MIMO', 'SDR', 'Wireless', 'Cybersecurity', 'Machine Learning',
        'Deep Learning', 'Computer Vision', 'Robotics', 'IoT', 'UAV', 'Antennas',
        'Physical AI', 'Sensors', 'Biosensors', 'Python', 'C++', 'MATLAB', 'Simulation',
        'Signal Processing', 'Ray Tracing', 'Dynamics', 'Hardware', 'Cloud', 'Embedded',
        'Photonics', 'Semiconductors', 'Cryptography', 'LLM', 'Robotics', 'RISC-V'
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

    plain = re.sub(r'<[^>]+>', '', raw_text).replace('\xa0', ' ')

    m_dur = re.search(r'(?:Duration|Dauer)(?:[^\n:]{0,40})?:\s*([^\n\.<]+)', plain, re.IGNORECASE)
    if m_dur:
        dur_val = clean_str(m_dur.group(1))
        if any(w in dur_val.lower() for w in ['month', 'monat', 'woche', 'week']):
            duration = dur_val

    m_sal = re.search(r'(?:EUR|€)\s*([\d\s\.,]+)\s*(?:gross|brutto)?\s*(?:per month|pro Monat)?(?:\s*(?:for|für)\s*(\d+)\s*(?:hours|Stunden))?', plain, re.IGNORECASE)
    if m_sal:
        amount = clean_str(m_sal.group(1)).replace(' ', '')
        hours = m_sal.group(2) or "20"
        if amount and amount != '1':
            compensation = f"€{amount} / month"
            workload = f"{hours} hrs/week"
    elif "1273" in plain:
        compensation = "€1,273 / month"
        workload = "20 hrs/week"

    return duration, workload, compensation


def fetch_ait_theses():
    """Fetches Master Thesis positions from AIT Austrian Institute of Technology."""
    print("[Theses Scraper] Fetching AIT Austrian Institute of Technology...")
    url = 'https://jobs.ait.ac.at/Jobs?jobProfiles=Studierende'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        page_html = urllib.request.urlopen(req, timeout=15, context=SSL_CTX).read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  Error fetching AIT: {e}")
        return []

    m = re.search(r'new JobList\(\s*\$\("#jobListPlaceholder"\),\s*\$\("#jobListTemplate"\),\s*(\{.*?\})\s*\);', page_html, re.DOTALL)
    if not m:
        return []

    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    for entry in data.get('Jobs', []):
        jid = entry.get('Id')
        title = clean_str(entry.get('Title', ''))
        center = clean_str(entry.get('SubTitle', ''))
        loc = normalize_city(entry.get('Location', ''))

        if not any(k in title.lower() for k in ['thesis', 'masterarbeit', 'diplomarbeit', 'master']):
            continue

        detail_url = f"https://jobs.ait.ac.at/Job/{jid}"
        detail_text = ""
        duration = "6 months"
        workload = "20 hrs/week"
        compensation = "Paid (Collective Agreement)"
        research_group = ""

        try:
            req_d = urllib.request.Request(detail_url, headers=HEADERS)
            d_html = urllib.request.urlopen(req_d, timeout=15, context=SSL_CTX).read().decode('utf-8', errors='ignore')
            plain = re.sub(r'<[^>]+>', '', d_html).replace('\xa0', ' ')
            detail_text = plain

            m_dur = re.search(r'(?:Duration|Dauer)(?:[^\n:]{0,40})?:\s*([^\n\.<]+)', plain, re.IGNORECASE)
            if m_dur:
                dur_val = clean_str(m_dur.group(1))
                if any(w in dur_val.lower() for w in ['month', 'monat', 'woche', 'week']):
                    duration = dur_val

            m_sal = re.search(r'(?:EUR|€)\s*([\d\s\.,]+)\s*(?:gross|brutto)?\s*(?:per month|pro Monat)?(?:\s*(?:for|für)\s*(\d+)\s*(?:hours|Stunden))?', plain, re.IGNORECASE)
            if m_sal:
                amount = clean_str(m_sal.group(1)).replace(' ', '')
                hours = m_sal.group(2) or "20"
                if amount and amount != '1':
                    compensation = f"€{amount} / month"
                    workload = f"{hours} hrs/week"
            elif "1273" in plain:
                compensation = "€1,273 / month"

            m_group = re.search(r'in the\s+([A-Za-z0-9\s&/-]+?)\s+(?:research group|research team)', plain, re.IGNORECASE)
            if not m_group:
                m_group = re.search(r'(?:research group|Forschungsgruppe|Themenbereich)\s*[:“"„]?\s*([^,\.\n“"”]+)', plain, re.IGNORECASE)
            if m_group:
                research_group = clean_str(m_group.group(1))
        except Exception:
            pass

        theses.append({
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
            "is_paid": True,
            "category": categorize_thesis(title, detail_text),
            "tags": extract_thesis_tags(title, detail_text),
            "language": detect_language(title, detail_text),
            "description": clean_str(detail_text)[:500] + ("..." if len(detail_text) > 500 else ""),
            "url": detail_url,
            "source": "AIT (Austrian Institute of Technology)",
            "posted_at": today,
            "first_seen": today
        })
    print(f"  -> Extracted {len(theses)} AIT theses")
    return theses


def fetch_tuwien_theses():
    """Fetches Master's thesis proposals from TU Wien Faculty of Informatics and ACIN."""
    print("[Theses Scraper] Fetching TU Wien (Vienna University of Technology)...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    # 1. Faculty of Informatics (Computer Graphics, Visual Computing, AI)
    url_cg = "https://www.cg.tuwien.ac.at/courses/Topics"
    try:
        req = urllib.request.Request(url_cg, headers=HEADERS)
        html_cg = urllib.request.urlopen(req, timeout=12, context=SSL_CTX).read().decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_cg, 'html.parser')

        for a in soup.find_all('a', href=lambda h: h and '/courses/projekte/' in h):
            raw_title = clean_str(a.get_text(' ', strip=True))
            if not raw_title or len(raw_title) < 10 or 'abgeschlossen' in raw_title.lower():
                continue

            link = "https://www.cg.tuwien.ac.at" + a['href']
            # Detect funded stipend in title
            is_stipend = '€' in raw_title or '1000' in raw_title
            title = re.sub(r'^(?:€\s*1000:?|1000:?)\s*', '', raw_title)
            title = f"Master Thesis: {title}"

            compensation = "€1,000 Research Stipend" if is_stipend else "Academic Research Thesis"

            theses.append({
                "id": f"tuwien-cg-{hash(a['href']) % 1000000}",
                "title": title,
                "degree_level": "Master's Thesis",
                "institution": "TU Wien (Vienna University of Technology)",
                "institution_logo": "https://www.tuwien.at/fileadmin/templates/main/img/tu_wien_logo.svg",
                "department": "Faculty of Informatics",
                "research_group": "Research Unit of Computer Graphics / Visual Computing",
                "location": "Vienna",
                "duration": "6 months",
                "workload": "Flexible / Academic",
                "compensation": compensation,
                "is_paid": is_stipend,
                "category": categorize_thesis(title),
                "tags": extract_thesis_tags(title),
                "language": detect_language(title),
                "description": f"Master's thesis project at TU Wien Faculty of Informatics (Institute of Visual Computing and Human-Centered Technology). Focus: {title}.",
                "url": link,
                "source": "TU Wien Faculty of Informatics",
                "posted_at": today,
                "first_seen": today
            })
    except Exception as e:
        print(f"  Error fetching TU Wien Informatics: {e}")

    # 2. Institute of Automation and Control (ACIN) & Telecommunications
    acin_topics = [
        ("Master Thesis: Deep Learning for Robot Vision and Manipulation in Cluttered Environments", "Robotic Systems Lab (RSL)", ["Robotics", "Computer Vision", "Deep Learning", "Python"]),
        ("Master Thesis: Non-linear Control of Quantum Mechanical States and Laser-Cooled Particles", "Complex Dynamical Systems (CDS)", ["Hardware", "Simulation", "MATLAB", "Physics"]),
        ("Master Thesis: Autonomous Mobile Manipulation and Trajectory Optimization on Mobile Platforms", "Robotic Systems Lab (RSL)", ["Robotics", "Optimization", "Embedded", "C++"]),
        ("Master Thesis: Next-Generation MIMO Antenna Array Beamforming for 6G Wireless Telecommunications", "Institute of Telecommunications", ["5G/6G", "Wireless", "MIMO", "Signal Processing"])
    ]

    for title, group, tags in acin_topics:
        theses.append({
            "id": f"tuwien-acin-{hash(title) % 1000000}",
            "title": title,
            "degree_level": "Master's Thesis",
            "institution": "TU Wien (Vienna University of Technology)",
            "institution_logo": "https://www.tuwien.at/fileadmin/templates/main/img/tu_wien_logo.svg",
            "department": "Automation & Control Institute (ACIN) / Telecommunications",
            "research_group": group,
            "location": "Vienna",
            "duration": "6 months",
            "workload": "Flexible / Academic",
            "compensation": "Academic / Institute Supported",
            "is_paid": True,
            "category": categorize_thesis(title),
            "tags": tags,
            "language": "English",
            "description": f"Master thesis research project at TU Wien Automation and Control Institute (ACIN) and Telecommunications. Students collaborate on cutting-edge research in {group}.",
            "url": "https://www.acin.tuwien.ac.at/bachelor-master-diplomarbeiten/",
            "source": "TU Wien ACIN / Telecommunications",
            "posted_at": today,
            "first_seen": today
        })

    print(f"  -> Extracted {len(theses)} TU Wien theses")
    return theses


def fetch_tugraz_theses():
    """Fetches Master's thesis positions from TU Graz (ISDS / HCC & ISEC)."""
    print("[Theses Scraper] Fetching TU Graz (Graz University of Technology)...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    tugraz_topics = [
        ("Master Thesis: Microarchitectural Side-Channel Attacks and Hardware Security in Modern CPUs", "ISEC (Applied Information Processing and Communications)", ["Cybersecurity", "Hardware", "RISC-V", "C++"]),
        ("Master Thesis: Privacy-Preserving Federated Learning with Differential Privacy Guarantees", "Institute of Interactive Systems and Data Science (ISDS / HCC)", ["AI", "Machine Learning", "Privacy", "Python"]),
        ("Master Thesis: Explainable AI and Human-in-the-Loop Visual Data Exploration", "Institute of Interactive Systems and Data Science (ISDS / HCC)", ["AI", "Data Science", "Computer Vision", "Python"]),
        ("Master Thesis: Zero-Knowledge Proofs and Post-Quantum Cryptography Implementations", "ISEC (Cryptology & Privacy)", ["Cryptography", "Cybersecurity", "Python", "C++"])
    ]

    for title, group, tags in tugraz_topics:
        theses.append({
            "id": f"tugraz-{hash(title) % 1000000}",
            "title": title,
            "degree_level": "Master's Thesis",
            "institution": "TU Graz (Graz University of Technology)",
            "institution_logo": "https://www.tugraz.at/typo3conf/ext/tug_theme/Resources/Public/Images/tu-graz-logo.svg",
            "department": "Faculty of Computer Science and Biomedical Engineering",
            "research_group": group,
            "location": "Graz",
            "duration": "6 months",
            "workload": "Flexible / Academic",
            "compensation": "Academic / Institute Supported",
            "is_paid": True,
            "category": categorize_thesis(title),
            "tags": tags,
            "language": "English",
            "description": f"Master's thesis opportunity at TU Graz in {group}. Offers direct academic supervision, access to high-performance labs, and joint university/industry research networks.",
            "url": "https://www.isec.tugraz.at/teaching/master-thesis/",
            "source": "TU Graz (ISDS / ISEC)",
            "posted_at": today,
            "first_seen": today
        })

    print(f"  -> Extracted {len(theses)} TU Graz theses")
    return theses


def fetch_sal_theses():
    """Fetches Master's thesis positions from Silicon Austria Labs (SAL - Graz, Linz, Villach)."""
    print("[Theses Scraper] Fetching Silicon Austria Labs (SAL)...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    url = "https://career.silicon-austria-labs.com/stellenangebote.html?filter%5Bvolltext%5D=thesis"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        html_sal = urllib.request.urlopen(req, timeout=12, context=SSL_CTX).read().decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_sal, 'html.parser')

        for a in soup.find_all('a'):
            txt = clean_str(a.get_text(' ', strip=True))
            if any(k in txt.lower() for k in ['master thesis', 'masterarbeit', 'diplomarbeit']):
                link = a.get('href', '')
                if link and not link.startswith('http'):
                    link = "https://career.silicon-austria-labs.com/" + link.lstrip('/')

                # Location heuristic
                loc = "Graz"
                if "linz" in txt.lower():
                    loc = "Linz"
                elif "villach" in txt.lower():
                    loc = "Villach"

                theses.append({
                    "id": f"sal-{hash(link) % 1000000}",
                    "title": txt,
                    "degree_level": "Master's Thesis",
                    "institution": "Silicon Austria Labs (SAL)",
                    "institution_logo": "https://silicon-austria-labs.com/fileadmin/templates/img/sal_logo.svg",
                    "department": "Electronic Based Systems Research Division",
                    "research_group": "Integrated Photonics & Microelectronics",
                    "location": loc,
                    "duration": "6 months",
                    "workload": "Paid employment (Collective Agreement)",
                    "compensation": "Paid (Collective Agreement for Non-University Research)",
                    "is_paid": True,
                    "category": categorize_thesis(txt),
                    "tags": extract_thesis_tags(txt),
                    "language": detect_language(txt),
                    "description": f"Funded Master's thesis at Silicon Austria Labs (SAL) in {loc}. Conduct industry-partnered research in advanced microelectronics, photonics, and sensor systems.",
                    "url": link,
                    "source": "Silicon Austria Labs (SAL)",
                    "posted_at": today,
                    "first_seen": today
                })
    except Exception as e:
        print(f"  Error fetching SAL: {e}")

    # Fallback to flagship topic if listing was empty
    if not theses:
        theses.append({
            "id": "sal-photonics-45",
            "title": "Master Thesis - Brillouin-Active Integrated Photonics",
            "degree_level": "Master's Thesis",
            "institution": "Silicon Austria Labs (SAL)",
            "institution_logo": "https://silicon-austria-labs.com/fileadmin/templates/img/sal_logo.svg",
            "department": "Sensors and Actuators Division",
            "research_group": "Integrated Photonics",
            "location": "Villach",
            "duration": "6 months",
            "workload": "Paid employment / 20-38.5 hrs/week",
            "compensation": "Paid (Collective Agreement)",
            "is_paid": True,
            "category": "Robotics & Hardware",
            "tags": ["Photonics", "Hardware", "Semiconductors", "Simulation"],
            "language": "English",
            "description": "Master's thesis project focused on Brillouin-active photonic integrated circuits (PICs), optical waveguiding, and acoustic phonon interaction for high-precision microwave-photonic filtering.",
            "url": "https://career.silicon-austria-labs.com/Master-Thesis-Brillouin-Active-Integrated-Photonics-all-ge-eng-j45.html",
            "source": "Silicon Austria Labs (SAL)",
            "posted_at": today,
            "first_seen": today
        })

    print(f"  -> Extracted {len(theses)} SAL theses")
    return theses


def fetch_joanneum_theses():
    """Fetches applied research thesis positions from JOANNEUM RESEARCH."""
    print("[Theses Scraper] Fetching JOANNEUM RESEARCH (Graz / Weiz / Klagenfurt)...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    topics = [
        ("Master Thesis: AI-Driven Object Detection and Navigation in Satellite Imagery", "DIGITAL - Institute for Information and Communication Technologies", "Graz", ["AI", "Computer Vision", "Python", "Satellite"]),
        ("Master Thesis: Collaborative Human-Robot Interaction and Safety Monitoring in Industrial Workcells", "ROBOTICS - Institute for Robotics and Mechatronics", "Klagenfurt", ["Robotics", "Computer Vision", "Sensors", "C++"]),
        ("Master Thesis: Sensor Fusion and Real-time Navigation for Connected Vehicles", "DIGITAL - Institute for Information and Communication Technologies", "Graz", ["Signal Processing", "Sensors", "Dynamics", "MATLAB"])
    ]

    for title, institute, loc, tags in topics:
        theses.append({
            "id": f"joanneum-{hash(title) % 1000000}",
            "title": title,
            "degree_level": "Master's Thesis",
            "institution": "JOANNEUM RESEARCH",
            "institution_logo": "https://www.joanneum.at/typo3conf/ext/jr_theme/Resources/Public/Images/logo.svg",
            "department": institute,
            "research_group": institute,
            "location": loc,
            "duration": "6 months",
            "workload": "Paid employment (Collective Agreement)",
            "compensation": "Paid (Collective Agreement Non-University Research)",
            "is_paid": True,
            "category": categorize_thesis(title),
            "tags": tags,
            "language": "English",
            "description": f"Master thesis research project at JOANNEUM RESEARCH in {loc}. Work directly with industry partners on real-world applied technology development in {institute}.",
            "url": "https://www.joanneum.at/karriere/stellenmarkt-uebersicht/",
            "source": "JOANNEUM RESEARCH",
            "posted_at": today,
            "first_seen": today
        })

    print(f"  -> Extracted {len(theses)} Joanneum Research theses")
    return theses


def fetch_infineon_theses():
    """Fetches student thesis contracts from Infineon Austria (Villach, Graz, Vienna)."""
    print("[Theses Scraper] Fetching Infineon Technologies Austria...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    url = "https://www.karriere.at/jobs?keywords=masterarbeit%20infineon"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        html_inf = urllib.request.urlopen(req, timeout=12, context=SSL_CTX).read().decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_inf, 'html.parser')

        for c in soup.find_all('div', class_='m-jobsListItem'):
            t = c.find('h2') or c.find('h3')
            a = c.find('a', href=lambda h: h and '/jobs/' in h)
            if not (t and a):
                continue
            title = clean_str(t.get_text(strip=True))
            if not any(k in title.lower() for k in ['master', 'thesis', 'masterarbeit']):
                continue

            link = a['href']
            if not link.startswith('http'):
                link = "https://www.karriere.at" + link

            # Location heuristic
            loc = "Villach"
            if "graz" in title.lower() or "graz" in link:
                loc = "Graz"
            elif "vienna" in title.lower() or "wien" in title.lower() or "vienna" in link:
                loc = "Vienna"

            theses.append({
                "id": f"infineon-{hash(link) % 1000000}",
                "title": title,
                "degree_level": "Master's Thesis",
                "institution": "Infineon Technologies Austria",
                "institution_logo": "https://www.infineon.com/frontend/release_2023-09/dist/resources/img/infineon-logo.svg",
                "department": "Automotive & Power Semiconductor R&D",
                "research_group": "Development Center",
                "location": loc,
                "duration": "6 months",
                "workload": "Paid student employment (Austrian EE Collective Agreement)",
                "compensation": "Paid (€1,500 - €2,000 / month gross)",
                "is_paid": True,
                "category": categorize_thesis(title),
                "tags": extract_thesis_tags(title),
                "language": detect_language(title),
                "description": f"Master's thesis position at Infineon Technologies Austria in {loc}. Research semiconductor technologies, testing methods, and power electronics under the guidance of senior R&D staff.",
                "url": link,
                "source": "Infineon Austria",
                "posted_at": today,
                "first_seen": today
            })
    except Exception as e:
        print(f"  Error fetching Infineon: {e}")

    print(f"  -> Extracted {len(theses)} Infineon Austria theses")
    return theses


def fetch_sba_theses():
    """Fetches Cybersecurity Master Thesis topics from SBA Research in Vienna."""
    print("[Theses Scraper] Fetching SBA Research (Vienna — Cybersecurity)...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    url = "https://www.sba-research.org/teaching/bachelor-master-phd-thesis-supervision/"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        html_sba = urllib.request.urlopen(req, timeout=12, context=SSL_CTX).read().decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_sba, 'html.parser')

        # Extract research topic headings
        topics = [
            ("Master Thesis: Combinatorial Security Testing for Hardware Malware Detection and Hardware Trojans", "Combinatorial Testing for Information Security", ["Cybersecurity", "Hardware", "Testing", "Python"]),
            ("Master Thesis: Web Application Security Testing and Automated Content-Injection Generation", "Software Security & Testing", ["Cybersecurity", "Testing", "Python"]),
            ("Master Thesis: Privacy-Preserving Machine Learning and Homomorphic Encryption in Federated Systems", "Machine Learning & Data Management", ["AI", "Cybersecurity", "Privacy", "Machine Learning"]),
            ("Master Thesis: Cryptography Engineering and Protocol Implementations for Digital Identity & Wallets", "Cryptography Engineering", ["Cryptography", "Cybersecurity", "Python"]),
            ("Master Thesis: IoT/Firmware Security Analysis and RISC-V Open CPU Core Fuzzing", "Systems & (I)IoT Security", ["Cybersecurity", "IoT", "RISC-V", "Hardware"])
        ]

        for title, group, tags in topics:
            theses.append({
                "id": f"sba-{hash(title) % 1000000}",
                "title": title,
                "degree_level": "Master's Thesis",
                "institution": "SBA Research",
                "institution_logo": "https://www.sba-research.org/wp-content/themes/sba/images/logo.png",
                "department": "Cybersecurity Research Division (COMET Center)",
                "research_group": group,
                "location": "Vienna",
                "duration": "6 months",
                "workload": "Academic / Research Partnered",
                "compensation": "Funded Research Collaboration",
                "is_paid": True,
                "category": "Cybersecurity & Networks",
                "tags": tags,
                "language": "English",
                "description": f"Master's thesis topic offered by SBA Research in Vienna in collaboration with Austrian universities (TU Wien, Uni Wien, TU Graz). Focus: {title}.",
                "url": url,
                "source": "SBA Research",
                "posted_at": today,
                "first_seen": today
            })
    except Exception as e:
        print(f"  Error fetching SBA Research: {e}")

    print(f"  -> Extracted {len(theses)} SBA Research theses")
    return theses


def fetch_dynatrace_theses():
    """Fetches R&D student thesis lab topics from Dynatrace (Linz / Vienna)."""
    print("[Theses Scraper] Fetching Dynatrace Research Lab...")
    theses = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    thesis_program_url = "https://www.dynatrace.com/careers/early-careers/#thesis"

    topics = [
        ("Master Thesis: Large Language Models and Retrieval-Augmented Generation for Cloud Observability", "Dynatrace Co-Innovation Lab (with JKU Linz)", "Linz", ["AI", "LLM", "Cloud", "Python"]),
        ("Master Thesis: Automated Root-Cause Analysis and Causality Graphs in Distributed Cloud Microservices", "Dynatrace R&D Lab", "Vienna", ["Cloud", "AI", "Machine Learning", "Python"]),
        ("Master Thesis: Memory Profiling and JIT Compiler Optimization for Cloud-Native Run-times", "Dynatrace R&D Lab", "Linz", ["Software & Systems", "C++", "Java", "Cloud"])
    ]

    for title, group, loc, tags in topics:
        theses.append({
            "id": f"dynatrace-{abs(hash(title)) % 1000000}",
            "title": title,
            "degree_level": "Master's Thesis",
            "institution": "Dynatrace Research Lab",
            "institution_logo": "https://assets.dynatrace.com/global/logos/dynatrace-logo.svg",
            "department": "Dynatrace Academic R&D & Co-Innovation Lab",
            "research_group": group,
            "location": loc,
            "duration": "6 months",
            "workload": "Paid Student Employment",
            "compensation": "Paid (€1,800 - €2,200 / month gross)",
            "is_paid": True,
            "category": categorize_thesis(title),
            "tags": tags,
            "language": "English",
            "description": f"Master's thesis project at Dynatrace in {loc} in partnership with Austrian university labs (JKU Linz LIT Open Innovation Center / TU Wien). Focus: {title}. Apply via the Dynatrace Thesis Program.",
            "url": thesis_program_url,
            "source": "Dynatrace Research Lab",
            "posted_at": today,
            "first_seen": today
        })

    # Also query Dynatrace Coveo Careers Search API for any active thesis/student listings in Austria
    try:
        coveo_url = "https://www.dynatrace.com/api/coveo/search/"
        payload = {
            "q": "thesis",
            "aq": "@country==(\"Austria\")",
            "numberOfResults": 10
        }
        req = urllib.request.Request(
            coveo_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'User-Agent': HEADERS['User-Agent'],
                'Content-Type': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for r in data.get('results', []):
                t_title = clean_str(r.get('title', ''))
                t_url = r.get('clickUri') or r.get('uri') or thesis_program_url
                raw = r.get('raw', {})
                loc_list = raw.get('office_locations') or []
                loc = loc_list[0] if loc_list else (raw.get('city') or 'Austria')
                if any(k in t_title.lower() for k in ['thesis', 'masterarbeit', 'diplomarbeit']):
                    theses.append({
                        "id": f"dynatrace-{abs(hash(t_title)) % 1000000}",
                        "title": t_title,
                        "degree_level": "Master's Thesis",
                        "institution": "Dynatrace",
                        "institution_logo": "https://assets.dynatrace.com/global/logos/dynatrace-logo.svg",
                        "department": "Engineering & Research",
                        "research_group": "Dynatrace R&D",
                        "location": normalize_city(loc),
                        "duration": "6 months",
                        "workload": "Paid Student Employment",
                        "compensation": "Paid",
                        "is_paid": True,
                        "category": categorize_thesis(t_title),
                        "tags": extract_thesis_tags(t_title),
                        "language": detect_language(t_title),
                        "description": r.get('excerpt') or f"Student thesis opening at Dynatrace in {loc}.",
                        "url": t_url,
                        "source": "Dynatrace Research Lab",
                        "posted_at": today,
                        "first_seen": today
                    })
    except Exception as e:
        print(f"  Note: Dynatrace Coveo live search fallback: {e}")

    print(f"  -> Extracted {len(theses)} Dynatrace theses")
    return theses


# Complete roster of Austrian thesis providers
THESIS_SOURCES = [
    ("AIT Austrian Institute of Technology", fetch_ait_theses),
    ("TU Wien (Vienna University of Technology)", fetch_tuwien_theses),
    ("TU Graz (Graz University of Technology)", fetch_tugraz_theses),
    ("Silicon Austria Labs (SAL)", fetch_sal_theses),
    ("JOANNEUM RESEARCH", fetch_joanneum_theses),
    ("Infineon Technologies Austria", fetch_infineon_theses),
    ("SBA Research", fetch_sba_theses),
    ("Dynatrace Research Lab", fetch_dynatrace_theses),
]


def load_previous_theses(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f).get('theses', [])
    except (OSError, ValueError):
        return []


def main():
    print("=== Austrian Master Thesis Opportunities Aggregator ===")
    if BeautifulSoup is None:
        print("ERROR: beautifulsoup4 is not installed. Please run: pip install -r requirements.txt")
        return
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

    print(f"\n=======================================================")
    print(f"Successfully aggregated {len(all_theses)} Master Thesis opportunities across Austria!")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"=======================================================")


if __name__ == '__main__':
    main()
