import urllib.request
import re
import html
import os
import json
from collections import Counter

class JobClassifierAgent:
    """
    Custom Hybrid Agent (Targeted NLP + optional local Ollama LLM)
    Inspects full job posting content, strips website navigation templates,
    verifies 100% English language purity, and extracts metadata tags.

    The rule-based NLP English-purity check is always the authoritative gate: small LLMs
    (tested with llama3.2:1b and 3b) proved unreliable at this specific judgment, mislabeling
    genuinely English postings as German. An LLM is only used afterwards, to enrich metadata
    tags (seniority/relocation/experience/city) on jobs that already passed the gate:
      1. Local Ollama model (if a local Ollama server is reachable) - free, private, no API key.
      2. Rule-based keyword metadata extraction - always available, used in CI (GitHub Actions)
         where no local Ollama server exists.
    """

    # Strong German section headers in job body text
    GERMAN_STRONG_INDICATORS = [
        'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil', 'wir bieten', 'ihr angebot',
        'anforderungsprofil', 'unsere erwartungen', 'über das unternehmen',
        'brutto/monat', 'brutto/jahr', 'überzahlung', 'dienstort', 'vollzeit', 'teilzeit',
        'deutschkenntnisse', 'sehr gute deutschkenntnisse', 'deutsch in wort und schrift',
        'fliessend deutsch', 'fließend deutsch', 'deutsch c1', 'deutsch b2', 'abgeschlossene ausbildung'
    ]

    GERMAN_STOPWORDS = set([
        'und', 'die', 'der', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'einem', 'einen',
        'mit', 'für', 'auf', 'ist', 'sind', 'wir', 'ihre', 'ihrer', 'ihren', 'deine', 'deiner', 'deinen',
        'aufgaben', 'profil', 'anforderungen', 'bieten', 'gehalt', 'euro', 'brutto', 'rahmenbedingungen',
        'qualifikationen', 'deutsch', 'kenntnisse', 'dienstort', 'vollzeit', 'teilzeit', 'standort',
        'bewerbung', 'über', 'unternehmens', 'erfahrung', 'abgeschlossene', 'ausbildung', 'sowie', 'oder',
        'als', 'auch', 'bei', 'uns', 'dich', 'du', 'sie', 'ihr', 'diese', 'dieser', 'dieses', 'unsere',
        'unserer', 'unserem', 'unseren', 'nachhaltig', 'bereich', 'abteilung', 'vereinbarung',
        'mindestgehalt', 'kollektivvertrag', 'überzahlung', 'bereitschaft', 'marktkonform',
        'verstärkung', 'mitarbeiter', 'mitarbeiterin', 'suchen', 'freuen'
    ])

    SITE_NAV_PHRASES = [
        'zum seiteninhalt springen', 'jobs firmen lebenslauf', 'blog & tipps', 'über uns für arbeitgeber',
        'jetzt anmelden', 'neu hier? kostenlos registrieren', 'job-alarm merkliste', 'firmen-alarm',
        'nur für angemeldete bewerber', 'nachrichten , nur für angemeldete bewerber', 'lebenslauf bewerbungen'
    ]

    TECH_KEYWORDS = [
        'developer', 'engineer', 'engineering', 'data', 'software', 'ai', 'cloud', 'devops', 'backend', 'frontend',
        'fullstack', 'full-stack', 'architect', 'qa', 'sre', 'product owner', 'product manager',
        'tech', 'it', 'python', 'java', 'react', 'node', 'sql', 'sysadmin', 'scrum', 'cybersecurity',
        'machine learning', 'data science', 'analytics', 'infrastructure', 'platform',
        'business intelligence', 'geospatial', 'gis', 'ict', 'information systems',
        'information technology', 'programmer', 'database administrator'
    ]

    NON_TECH_TERMS = [
        'writer', 'copywriter', 'counsel', 'sales contractor', 'office assistant', 'recruiter', 'hr',
        'accountant', 'legal', 'finance manager', 'fp&a', 'customer success manager', 'event', 'digital marketing'
    ]

    def __init__(self, headers=None, ollama_url=None, ollama_model=None):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }

        self.ollama_url = ollama_url or os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/generate')
        self.ollama_model = ollama_model or os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')
        self._ollama_checked = False
        self._ollama_available = False

    def fetch_full_text(self, url):
        """Fetches job page HTML and strips site template nav/headers/footers."""
        if not url or not url.startswith('http'):
            return ""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_html = resp.read().decode('utf-8', errors='ignore')
            
            clean = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL)
            clean = re.sub(r'<style[^>]*>.*?</style>', ' ', clean, flags=re.DOTALL)
            clean = re.sub(r'<header[^>]*>.*?</header>', ' ', clean, flags=re.DOTALL)
            clean = re.sub(r'<footer[^>]*>.*?</footer>', ' ', clean, flags=re.DOTALL)
            clean = re.sub(r'<nav[^>]*>.*?</nav>', ' ', clean, flags=re.DOTALL)

            text = re.sub(r'<[^>]+>', ' ', clean)
            text = html.unescape(text)

            text_lower = text.lower()
            for phrase in self.SITE_NAV_PHRASES:
                text_lower = text_lower.replace(phrase, ' ')

            text = ' '.join(text_lower.split())
            return text
        except Exception:
            return ""

    def _ollama_is_running(self):
        """Cheap one-time check so we don't retry a dead local server for every job."""
        if self._ollama_checked:
            return self._ollama_available
        self._ollama_checked = True
        try:
            base = self.ollama_url.split('/api/')[0]
            urllib.request.urlopen(base, timeout=1)
            self._ollama_available = True
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def classify_with_ollama(self, title, text_content):
        """Calls a local Ollama server (e.g. `ollama run llama3.2:1b`) to evaluate
        language purity & extract metadata tags, fully offline and free."""
        if not self._ollama_is_running():
            return None

        prompt = (
            "Analyze this job posting from Austria:\n"
            f"Title: {title}\n"
            f"Content: {text_content[:2000]}\n\n"
            "Task:\n"
            "1. Is the job description written in English? (Set is_english to false if written in German or requires German).\n"
            "2. Determine Seniority (Junior, Mid-Level, Senior, Lead / Manager, Internship / Student).\n"
            "3. Determine Relocation & Visa support (Relocation Supported, Visa Sponsorship, EU Work Permit Required, Not Specified).\n"
            "4. Experience level (e.g. 0-2 years exp, 3-5 years exp, 5+ years exp).\n"
            "5. City in Austria (Vienna, Graz, Linz, Salzburg, Innsbruck, Carinthia, Remote, Austria).\n\n"
            "Respond ONLY in valid JSON format: {\"is_english\": true, \"reason\": \"Rationale\", \"seniority\": \"...\", \"relocation_support\": \"...\", \"experience_level\": \"...\", \"city\": \"...\"}"
        )

        payload = json.dumps({
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }).encode('utf-8')

        try:
            req = urllib.request.Request(self.ollama_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                data = json.loads(result['response'])
                return data
        except Exception:
            # Local model missing/slow/malformed output - fall through to next classifier
            return None

    def evaluate_language_purity(self, title, text_content):
        """Rule-based Targeted NLP language purity evaluator."""
        combined = (title + " " + text_content).lower()

        for indicator in self.GERMAN_STRONG_INDICATORS:
            if indicator in combined:
                return False, f"Matched German section header: '{indicator}'"

        words = [w.lower() for w in re.findall(r'\b[a-zA-ZäöüßÄÖÜ]+\b', combined)]
        if not words:
            return False, "Empty content"

        german_words_found = [w for w in words if w in self.GERMAN_STOPWORDS]
        german_count = len(german_words_found)
        ratio = german_count / len(words)

        if german_count > 25 or ratio > 0.04:
            top_found = Counter(german_words_found).most_common(5)
            return False, f"High German stopword density ({german_count} words, ratio {ratio:.2%}): {top_found}"

        return True, "Passed English Purity Check"

    def is_tech_job(self, title):
        title_lower = title.lower()
        if any(term in title_lower for term in self.NON_TECH_TERMS):
            return False
        for kw in self.TECH_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', title_lower):
                return True
        return False

    def extract_metadata(self, title, description):
        text = (title + " " + description).lower()

        seniority = "Mid-Level"
        if any(k in text for k in ["junior", "graduate", "entry level", "entry-level", "trainee", "associate"]):
            seniority = "Junior"
        elif any(k in text for k in ["senior", "sr.", "principal", "staff", "architect"]):
            seniority = "Senior"
        elif any(k in text for k in ["lead", "head of", "director", "manager", "team lead", "engineering manager"]):
            seniority = "Lead / Manager"
        elif any(k in text for k in ["intern", "internship", "working student", "werkstudent"]):
            seniority = "Internship / Student"

        relocation_support = "Not Specified"
        if any(k in text for k in ["relocation support", "relocation package", "relocation assistance", "will assist with relocation"]):
            relocation_support = "Relocation Supported"
        elif any(k in text for k in ["visa sponsorship", "visa support", "sponsorship available", "work permit support"]):
            relocation_support = "Visa Sponsorship"
        elif any(k in text for k in ["eu citizen", "valid work permit", "eligible to work in Austria", "austrian work permit"]):
            relocation_support = "EU Work Permit Required"

        exp_match = re.search(r'(\d+)\+?\s*(-|\s*to\s*)?\s*(\d+)?\s*years?', text)
        if exp_match:
            yrs = exp_match.group(1)
            experience = f"{yrs}+ years exp"
        elif "junior" in text or "entry" in text:
            experience = "0-2 years exp"
        elif "senior" in text:
            experience = "5+ years exp"
        else:
            experience = "2-5 years exp"

        city = "Austria (Other)"
        if any(k in text for k in ["vienna", "wien"]):
            city = "Vienna"
        elif "graz" in text:
            city = "Graz"
        elif "linz" in text:
            city = "Linz"
        elif "salzburg" in text:
            city = "Salzburg"
        elif "innsbruck" in text:
            city = "Innsbruck"
        elif any(k in text for k in ["klagenfurt", "villach"]):
            city = "Carinthia"
        elif "remote" in text or "anywhere" in text:
            city = "Remote"

        return {
            "seniority": seniority,
            "relocation_support": relocation_support,
            "experience_level": experience,
            "city": city
        }

    def process_job(self, job_dict, fetch_detail_if_needed=True):
        title = job_dict.get('title', '')
        snippet = job_dict.get('description', '')
        url = job_dict.get('url', '')

        if not self.is_tech_job(title):
            return None, "Not a tech job"

        full_text = snippet
        if fetch_detail_if_needed and url and 'karriere.at' in url:
            fetched = self.fetch_full_text(url)
            if fetched:
                full_text = fetched

        # 1. The rule-based English-purity check is always the authoritative language gate.
        # LLMs (small local ones especially) were tested and are unreliable here - e.g.
        # llama3.2:1b/3b both mislabeled genuinely English postings as German when the text
        # mentioned "visa sponsorship" or "EU work permit required". Never let an LLM silently
        # drop a real English job - it is only trusted below to enrich metadata tags.
        is_english, reason = self.evaluate_language_purity(title, full_text)
        if not is_english:
            return None, reason

        # 2. Try local Ollama model to enrich metadata tags (seniority/relocation/experience/city)
        ollama_res = self.classify_with_ollama(title, full_text)
        if ollama_res is not None:
            job_dict.update({
                "seniority": ollama_res.get('seniority', 'Mid-Level'),
                "relocation_support": ollama_res.get('relocation_support', 'Not Specified'),
                "experience_level": ollama_res.get('experience_level', '2-5 years exp'),
                "city": ollama_res.get('city', 'Vienna')
            })
            return job_dict, f"Accepted by Rule-based Filter + local Ollama metadata ({self.ollama_model})"

        # 3. Rule-based metadata extraction (always available - used in CI/GitHub Actions)
        meta = self.extract_metadata(title, snippet + " " + full_text)
        job_dict.update(meta)
        return job_dict, "Accepted by Rule-based NLP Agent"
