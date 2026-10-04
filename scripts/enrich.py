"""
Second pass over scraped jobs that visits each job's detail page once and:

- drops postings whose page is gone (HTTP 404/410),
- adds a `salary` dict (scripts/salary.py), preferring schema.org JobPosting `baseSalary`,
- fills in a real location when the list page only said "Austria"/"Österreich",
- replaces template descriptions ("Tech role at X in Y.") with the posting's own text,
- sets `cities` (every board region the job is in) and `city` (the first one).

Many career sites embed a schema.org JobPosting as JSON-LD, which is the most reliable
source for these fields; plain page text is the fallback.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from agent_classifier import JobClassifierAgent
from salary import extract_salary, format_salary, salary_from_jobposting

# devjobs.at answers HTTP 429 to requests that only send a User-Agent.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}
DEAD_STATUSES = {404, 410}

# Board regions (must match the City / Region <select> values in index.html).
CITY_KEYWORDS = [
    ("Vienna", ("vienna", "wien")),
    ("Graz", ("graz",)),
    ("Linz", ("linz",)),
    ("Salzburg", ("salzburg",)),
    ("Innsbruck", ("innsbruck",)),
    ("Carinthia", ("carinthia", "kärnten", "klagenfurt", "villach", "pörtschach", "lavamünd", "wolfsberg", "spittal")),
]
REMOTE_KEYWORDS = ("remote", "worldwide", "anywhere", "europe", "emea", "latam", "apac", "americas")
GENERIC_LOCATIONS = {"", "austria", "österreich", "at"}

_cleaner = JobClassifierAgent(headers=HEADERS)


def _find_cities(text):
    return [name for name, keywords in CITY_KEYWORDS
            if any(re.search(rf'\b{k}\b', text) for k in keywords)]


def is_generic_location(location):
    return (location or "").lower().strip(" ,") in GENERIC_LOCATIONS


def normalize_cities(location, fallback_text=""):
    """Board regions for a job, derived from its location field.

    The job text is only consulted when the location says nothing more than
    "Austria" - descriptions often mention other offices ("our Vienna HQ"), so
    trusting them for a job in Kronstorf would mislabel it.
    """
    loc = (location or "").lower()
    cities = _find_cities(loc)
    if any(k in loc for k in REMOTE_KEYWORDS):
        cities.append("Remote")
    if not cities and is_generic_location(location):
        cities = _find_cities((fallback_text or "").lower())
    return cities or ["Austria (Other)"]


def fetch_detail(url):
    """(HTTP status or None on network error, raw HTML or "")."""
    if not url or not url.startswith('http'):
        return None, ""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return None, ""


def parse_jobposting(raw_html):
    """First schema.org JobPosting object found in the page's JSON-LD, or None."""
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw_html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(block, strict=False)
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                types = item.get('@type')
                if types == 'JobPosting' or (isinstance(types, list) and 'JobPosting' in types):
                    return item
                stack.extend(item.get('@graph', []))
    return None


def jobposting_location(posting):
    places = posting.get('jobLocation') or []
    if isinstance(places, dict):
        places = [places]
    names = []
    for place in places:
        address = place.get('address') if isinstance(place, dict) else None
        name = address.get('addressLocality') if isinstance(address, dict) else None
        if name and name not in names:
            names.append(name.strip())
    return ", ".join(names)


def html_to_text(fragment):
    text = html.unescape(re.sub(r'<[^>]+>', ' ', fragment or ''))
    return ' '.join(text.replace('\xa0', ' ').split())


_GERMAN_STOPWORDS = {"wir", "und", "die", "der", "das", "unsere", "unser", "ist", "für", "mit", "sie", "du", "ihre", "deine"}


def _looks_german(words):
    return sum(1 for w in words if w.lower().strip('.,;:!?') in _GERMAN_STOPWORDS) >= 2


def _capitalized_ratio(words):
    alpha = [w for w in words if w[:1].isalpha()]
    return sum(1 for w in alpha if w[:1].isupper()) / max(len(alpha), 1)


def _strip_label_run(sentence):
    """Drop a leading run of 3+ Title Case words glued on from a page header
    ("Bezirk (Alsergrund) About SQUER We are ..." -> "We are ..."), keeping the
    run's last word, which starts the actual sentence."""
    words = sentence.split()
    run = 0
    while run < len(words) and (words[run][:1].isupper() or words[run][:1] in '(' or words[run][:1].isdigit()):
        run += 1
    if run >= 3 and run < len(words):
        return ' '.join(words[run - 1:])
    return sentence


def summarize(text, limit=280):
    """Short card description: the first run of real prose sentences in the text.

    Skips page-header fragments (job facts like "Employment type Full Time Salary ...")
    by only accepting sentences of 8-60 words that end in punctuation and read like
    English prose rather than Title Case labels (some pages are bilingual).
    """
    picked = []
    for sentence in re.split(r'(?<=[.!?])\s+', text or ''):
        words = sentence.split()
        good = (8 <= len(words) <= 60 and sentence[:1].isupper() and sentence[-1:] in '.!?'
                and '|' not in sentence and _capitalized_ratio(words) < 0.4 and not _looks_german(words))
        if good:
            picked.append(sentence if picked else _strip_label_run(sentence))
            if len(' '.join(picked)) >= 160:
                break
        elif picked:
            break
    summary = ' '.join(picked)
    if len(summary) > limit:
        summary = summary[:limit].rsplit(' ', 1)[0] + "..."
    return summary


def is_placeholder_description(job):
    """True for the template descriptions scrapers write when a list page has no teaser."""
    desc = (job.get('description') or '').strip()
    title = job.get('title', '')
    return (not desc
            or desc.startswith("Tech role at ")
            or (desc.startswith(f"{title} at ") and len(desc) < len(title) + 120))


def _visit(job, retries):
    status, page = None, ""
    for attempt in range(retries):
        status, page = fetch_detail(job.get('url', ''))
        if page or status in DEAD_STATUSES:
            break
        if attempt + 1 < retries:
            time.sleep(3)
    return status, page


def _dead_sources(jobs, statuses):
    """Sources where most links look dead - more likely blocking us than all expired."""
    total = Counter(job['source'] for job in jobs)
    dead = Counter(job['source'] for job, status in zip(jobs, statuses) if status in DEAD_STATUSES)
    return {src for src, n in dead.items() if total[src] >= 4 and n / total[src] > 0.5}


def enrich_jobs(jobs, workers=3, retries=2):
    """Returns the jobs that are still online, enriched in place (see module docstring)."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        visits = list(pool.map(lambda job: _visit(job, retries), jobs))

    suspicious = _dead_sources(jobs, [status for status, _ in visits])
    for src in suspicious:
        print(f"[Enrich] WARNING: most {src} links returned 404/410 - keeping them, the site may be blocking the scraper.")

    kept, dropped = [], 0
    for job, (status, page) in zip(jobs, visits):
        if status in DEAD_STATUSES and job['source'] not in suspicious:
            dropped += 1
            continue

        posting = parse_jobposting(page) if page else None
        page_text = _cleaner.clean_html(page) if page else ""

        if posting and is_generic_location(job.get('location')):
            job['location'] = jobposting_location(posting) or job.get('location', '')

        if is_placeholder_description(job):
            summary = summarize(html_to_text(posting.get('description'))) if posting else ""
            if summary:
                job['description'] = summary

        salary = (salary_from_jobposting(posting.get('baseSalary')) if posting else None) \
            or extract_salary(job.get('description', '')) \
            or extract_salary(page_text)
        if salary:
            salary['label'] = format_salary(salary)
            job['salary'] = salary

        job['cities'] = normalize_cities(job.get('location'), job.get('title', '') + ' ' + job.get('description', ''))
        job['city'] = job['cities'][0]
        kept.append(job)

    print(f"[Enrich] Dropped {dropped} expired postings; "
          f"{sum(1 for j in kept if 'salary' in j)}/{len(kept)} remaining jobs state a salary.")
    return kept
