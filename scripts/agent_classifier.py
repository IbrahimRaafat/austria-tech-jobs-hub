import urllib.request
import re
import html
from collections import Counter

class JobClassifierAgent:
    """
    Custom Local Agent for inspecting full job post HTML, verifying 100% English language purity,
    and extracting metadata tags (Seniority, Relocation, Work Permit, Experience Level, City).
    """

    GERMAN_STRONG_INDICATORS = [
        'deine aufgaben', 'ihre aufgaben', 'dein profil', 'ihr profil', 'wir bieten', 'ihr angebot',
        'anforderungsprofil', 'unsere erwartungen', 'über uns', 'über das unternehmen',
        'gehalt', 'mindestgehalt', 'brutto/monat', 'brutto/jahr', 'kollektivvertrag', 'überzahlung',
        'dienstort', 'vollzeit', 'teilzeit', 'standort', 'bewerbung', 'deutschkenntnisse',
        'sehr gute deutschkenntnisse', 'deutsch in wort und schrift', 'fliessend deutsch',
        'fließend deutsch', 'deutsch c1', 'deutsch b2', 'gut ausgebildet', 'abgeschlossene ausbildung'
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
        'verstärkung', 'mitarbeiter', 'mitarbeiterin', 'suchen', 'freuen', 'uns'
    ])

    TECH_KEYWORDS = [
        'developer', 'engineer', 'data', 'software', 'ai', 'cloud', 'devops', 'backend', 'frontend',
        'fullstack', 'full-stack', 'architect', 'qa', 'sre', 'product owner', 'product manager',
        'tech', 'it', 'python', 'java', 'react', 'node', 'sql', 'sysadmin', 'scrum', 'cybersecurity',
        'machine learning', 'data science', 'analytics', 'infrastructure', 'platform'
    ]

    NON_TECH_TERMS = [
        'writer', 'copywriter', 'counsel', 'sales contractor', 'office assistant', 'recruiter', 'hr',
        'accountant', 'legal', 'finance manager', 'fp&a', 'customer success manager', 'event', 'digital marketing'
    ]

    def __init__(self, headers=None):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }

    def fetch_full_text(self, url):
        """Fetches and cleans the main body text from a job page URL."""
        if not url or not url.startswith('http'):
            return ""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_html = resp.read().decode('utf-8', errors='ignore')
            
            # Clean scripts, styles, and html tags
            clean = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL)
            clean = re.sub(r'<style[^>]*>.*?</style>', ' ', clean, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', clean)
            text = html.unescape(text)
            text = ' '.join(text.split())
            return text
        except Exception as e:
            return ""

    def evaluate_language_purity(self, title, text_content):
        """
        Evaluates whether a job post is 100% English.
        Returns (is_english, reason).
        """
        combined = (title + " " + text_content).lower()

        # Check for explicit German section headers or requirements
        for indicator in self.GERMAN_STRONG_INDICATORS:
            if indicator in combined:
                return False, f"Matched German indicator: '{indicator}'"

        # Word tokenization for stopword count
        words = [w.lower() for w in re.findall(r'\b[a-zA-ZäöüßÄÖÜ]+\b', combined)]
        if not words:
            return False, "Empty content"

        german_words_found = [w for w in words if w in self.GERMAN_STOPWORDS]
        
        german_count = len(german_words_found)
        ratio = german_count / len(words)

        if german_count > 18 or ratio > 0.03:
            top_found = Counter(german_words_found).most_common(5)
            return False, f"High German stopword density ({german_count} words, ratio {ratio:.2%}): {top_found}"

        return True, "Passed English Purity Check"

    def is_tech_job(self, title):
        """Checks if the title indicates a genuine tech role."""
        title_lower = title.lower()
        
        if any(term in title_lower for term in self.NON_TECH_TERMS):
            return False

        for kw in self.TECH_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', title_lower):
                return True

        return False

    def extract_metadata(self, title, description):
        """Extracts Seniority, Relocation/Visa, Experience, and City tags."""
        text = (title + " " + description).lower()

        # 1. Seniority
        seniority = "Mid-Level"
        if any(k in text for k in ["junior", "graduate", "entry level", "entry-level", "trainee", "associate"]):
            seniority = "Junior"
        elif any(k in text for k in ["senior", "sr.", "principal", "staff", "architect"]):
            seniority = "Senior"
        elif any(k in text for k in ["lead", "head of", "director", "manager", "team lead", "engineering manager"]):
            seniority = "Lead / Manager"
        elif any(k in text for k in ["intern", "internship", "working student", "werkstudent"]):
            seniority = "Internship / Student"

        # 2. Relocation & Visa Support
        relocation_support = "Not Specified"
        if any(k in text for k in ["relocation support", "relocation package", "relocation assistance", "will assist with relocation"]):
            relocation_support = "Relocation Supported"
        elif any(k in text for k in ["visa sponsorship", "visa support", "sponsorship available", "work permit support"]):
            relocation_support = "Visa Sponsorship"
        elif any(k in text for k in ["eu citizen", "valid work permit", "eligible to work in Austria", "austrian work permit"]):
            relocation_support = "EU Work Permit Required"

        # 3. Experience Level
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

        # 4. City Normalization
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
        """
        Main entry point for agent evaluation.
        Returns (evaluated_job_dict, status_string).
        """
        title = job_dict.get('title', '')
        snippet = job_dict.get('description', '')
        url = job_dict.get('url', '')

        if not self.is_tech_job(title):
            return None, "Not a tech job"

        # If karriere.at or url provided, fetch full page to inspect body
        full_text = snippet
        if fetch_detail_if_needed and url and 'karriere.at' in url:
            fetched = self.fetch_full_text(url)
            if fetched:
                full_text = fetched

        is_english, reason = self.evaluate_language_purity(title, full_text)
        if not is_english:
            return None, reason

        meta = self.extract_metadata(title, snippet + " " + full_text)
        job_dict.update(meta)
        return job_dict, "Accepted"
