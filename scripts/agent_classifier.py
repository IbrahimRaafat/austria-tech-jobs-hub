import urllib.request
import re
import html
import os
import json
from collections import Counter

class JobClassifierAgent:
    """
    Custom Hybrid Agent (Targeted NLP + optional Gemini API LLM Classifier)
    Inspects full job posting content, strips website navigation templates,
    verifies 100% English language purity, and extracts metadata tags.
    """

    # Strong German section headers in job body text (excluding site nav links)
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
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY', '')

    def fetch_full_text(self, url):
        """Fetches job page HTML and strips site template nav/headers/footers."""
        if not url or not url.startswith('http'):
            return ""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_html = resp.read().decode('utf-8', errors='ignore')
            
            # Remove scripts, styles, header, footer, nav elements
            clean = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL)
            clean = re.sub(r'<style[^>]*>.*?</style>', ' ', clean, flags=re.DOTALL)
            clean = re.sub(r'<header[^>]*>.*?</header>', ' ', clean, flags=re.DOTALL)
            clean = re.sub(r'<footer[^>]*>.*?</footer>', ' ', clean, flags=re.DOTALL)
            clean = re.sub(r'<nav[^>]*>.*?</nav>', ' ', clean, flags=re.DOTALL)

            text = re.sub(r'<[^>]+>', ' ', clean)
            text = html.unescape(text)

            # Strip standard site navigation text snippets
            text_lower = text.lower()
            for phrase in self.SITE_NAV_PHRASES:
                text_lower = text_lower.replace(phrase, ' ')

            text = ' '.join(text_lower.split())
            return text
        except Exception as e:
            return ""

    def classify_with_gemini(self, title, text_content):
        """Calls Gemini API to evaluate language purity & extract metadata tags."""
        if not self.gemini_api_key:
            return None

        prompt = f"""
Analyze this job posting from Austria and evaluate:
1. Is the job description 100% written in English? (Answer false if it is written in German or requires German as a mandatory work language).
2. What is the Seniority level? (Junior, Mid-Level, Senior, Lead / Manager, Internship / Student)
3. Relocation & Visa support? (Relocation Supported, Visa Sponsorship, EU Work Permit Required, Not Specified)
4. Experience level? (e.g. 0-2 years exp, 3-5 years exp, 5+ years exp)
5. City / Region in Austria? (Vienna, Graz, Linz, Salzburg, Innsbruck, Carinthia, Remote, Austria)

Title: {title}
Content: {text_content[:2500]}

Respond ONLY in JSON format:
{{
  "is_english": true/false,
  "reason": "short rationale",
  "seniority": "...",
  "relocation_support": "...",
  "experience_level": "...",
  "city": "..."
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }).encode('utf-8')

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode())
                text_resp = result['candidates'][0]['content']['parts'][0]['text']
                data = json.loads(text_resp)
                return data
        except Exception as e:
            print(f"Gemini API call skipped/failed: {e}")
            return None

    def evaluate_language_purity(self, title, text_content):
        """Rule-based Targeted NLP language purity evaluator."""
        combined = (title + " " + text_content).lower()

        # Check for explicit German body section headers
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

        # 1. Try Gemini API evaluation if key available
        gemini_res = self.classify_with_gemini(title, full_text)
        if gemini_res is not None:
            if not gemini_res.get('is_english'):
                return None, f"Gemini API: {gemini_res.get('reason', 'Not English')}"
            job_dict.update({
                "seniority": gemini_res.get('seniority', 'Mid-Level'),
                "relocation_support": gemini_res.get('relocation_support', 'Not Specified'),
                "experience_level": gemini_res.get('experience_level', '2-5 years exp'),
                "city": gemini_res.get('city', 'Vienna')
            })
            return job_dict, "Accepted by Gemini API"

        # 2. Targeted Rule-based NLP fallback
        is_english, reason = self.evaluate_language_purity(title, full_text)
        if not is_english:
            return None, reason

        meta = self.extract_metadata(title, snippet + " " + full_text)
        job_dict.update(meta)
        return job_dict, "Accepted by Targeted NLP Agent"
