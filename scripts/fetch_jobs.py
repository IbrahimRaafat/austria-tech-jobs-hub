import urllib.request
import re
import json
import os
import html
import datetime
import sys
from urllib.parse import urljoin

# Ensure scripts folder is on python path
sys.path.insert(0, os.path.dirname(__file__))

from agent_classifier import JobClassifierAgent
from enrich import enrich_jobs

agent = JobClassifierAgent()

def categorize_job(title, description=""):
    text = (title + " " + description).lower()
    # "ai"/"bi"/"gis" are short enough to false-match inside unrelated substrings
    # (e.g. "AIT" contains "ai", "logistics" contains "gis") - word-boundary these.
    data_ai_short_tokens = ["ai", "bi", "gis"]
    if (any(k in text for k in ["data", "machine learning", "python", "analytics", "power bi", "llm", "geospatial"])
            or any(re.search(r'\b' + kw + r'\b', text) for kw in data_ai_short_tokens)):
        return "Data & AI"
    elif any(k in text for k in ["frontend", "react", "vue", "angular", "ui/ux", "web"]):
        return "Frontend"
    elif any(k in text for k in ["backend", "node", "java", "c#", ".net", "golang", "ruby"]):
        return "Backend"
    elif any(k in text for k in ["devops", "cloud", "aws", "docker", "kubernetes", "sysadmin"]):
        return "DevOps & Cloud"
    else:
        return "Software Engineering"

def extract_tags(text):
    text_lower = text.lower()
    possible_tags = [
        "Python", "SQL", "TypeScript", "JavaScript", "React", "Next.js", "Node.js",
        "Docker", "AWS", "GCP", "Kubernetes", "PostgreSQL", "MongoDB", "Power BI",
        "Databricks", "Spark", "Git", "REST API", "Java", "C++", "C#", "Linux"
    ]
    matched = []
    for tag in possible_tags:
        if re.search(r'\b' + re.escape(tag.lower()) + r'\b', text_lower):
            matched.append(tag)
    return matched[:6]

def fetch_karriere_jobs():
    print("[Agent Classifier] Fetching and auditing Karriere.at job listings...")
    jobs = []
    urls = [
        'https://www.karriere.at/jobs/developer/austria',
        'https://www.karriere.at/jobs/data/austria',
        'https://www.karriere.at/jobs/software-engineer/austria',
        'https://www.karriere.at/jobs/ai/austria',
        'https://www.karriere.at/jobs/python/austria',
        'https://www.karriere.at/jobs/devops/austria',
        'https://www.karriere.at/jobs/graz',
        'https://www.karriere.at/jobs/linz',
        'https://www.karriere.at/jobs/salzburg'
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    seen_ids = set()
    # Karriere.at's page=2 returns ~3 additional distinct listings beyond page 1's 18,
    # but page=3+ just repeats page 2's content indefinitely, so 2 pages is the full set.
    max_pages = 2

    for url in urls:
        for page in range(1, max_pages + 1):
            page_url = url if page == 1 else f'{url}?page={page}'
            try:
                req = urllib.request.Request(page_url, headers=headers)
                html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8')
                m = re.search(r'window\.VUE_INITIAL_STATE\s*=\s*({.*?});\s*</script>', html, re.DOTALL)
                if not m:
                    continue
                data = json.loads(m.group(1))
                items = data.get('jobsSearchList', {}).get('activeItems', {}).get('items', [])

                for entry in items:
                    j = entry.get('jobsItem') or {}
                    if not j or not j.get('title'):
                        continue

                    job_id = j.get('id')
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title = j.get('title', '').strip()
                    company_info = j.get('company') or {}
                    company = company_info.get('name', 'Austria Tech Company')
                    logo = company_info.get('logoUrl', '')
                    if logo and logo.startswith('//'):
                        logo = 'https:' + logo

                    location_info = j.get('locations') or []
                    if isinstance(location_info, list):
                        locations = ", ".join([loc.get('name', '') for loc in location_info if isinstance(loc, dict)])
                    else:
                        locations = str(location_info)
                    if not locations:
                        locations = "Austria"

                    job_url = j.get('link') or ('https://www.karriere.at/jobs/' + str(job_id))
                    teaser = j.get('snippet', '') or j.get('teaser', '')

                    raw_job = {
                        "id": f"karriere-{job_id}",
                        "title": title,
                        "company": company,
                        "company_logo": logo,
                        "location": locations,
                        "category": categorize_job(title, teaser),
                        "tags": extract_tags(title + " " + teaser),
                        "description": teaser or f"Tech role at {company} in {locations}.",
                        "url": job_url,
                        "source": "Karriere.at",
                        "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
                    }

                    processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=True)
                    if processed:
                        jobs.append(processed)
                    else:
                        print(f"  [REJECTED Karriere.at ID {job_id}] Title: '{title}' -> Reason: {reason}")
            except Exception as e:
                print(f"Error fetching Karriere.at ({page_url}): {e}")

    return jobs

def fetch_arbeitnow_jobs():
    print("[Agent Classifier] Fetching and auditing Arbeitnow job listings...")
    jobs = []
    url = 'https://www.arbeitnow.com/api/job-board-api'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=8)
        data = json.loads(res.read().decode())
        for item in data.get('data', []):
            loc = item.get('location', '').lower()
            title = item.get('title', '')
            desc = item.get('description', '')
            if any(k in loc for k in ['austria', 'vienna', 'wien', 'graz', 'linz', 'salzburg', 'innsbruck']) or 'remote' in loc:
                raw_job = {
                    "id": f"arbeitnow-{item.get('slug')}",
                    "title": title,
                    "company": item.get('company_name', 'Tech Company'),
                    "company_logo": "",
                    "location": item.get('location', 'Austria'),
                    "category": categorize_job(title, desc),
                    "tags": item.get('tags', [])[:5] or extract_tags(title + " " + desc),
                    "description": re.sub(r'<[^>]+>', ' ', desc)[:280] + "...",
                    "url": item.get('url'),
                    "source": "Arbeitnow / Indeed Network",
                    "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
                }
                processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                if processed:
                    jobs.append(processed)
                else:
                    print(f"  [REJECTED Arbeitnow] Title: '{title}' -> Reason: {reason}")
    except Exception as e:
        print(f"Error fetching Arbeitnow: {e}")
    return jobs

def fetch_jobicy_jobs():
    print("[Agent Classifier] Fetching and auditing Jobicy listings...")
    jobs = []
    url = 'https://jobicy.com/api/v2/remote-jobs?count=50'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=8)
        data = json.loads(res.read().decode())
        for item in data.get('jobs', []):
            loc = item.get('jobGeo', '').lower()
            title = item.get('jobTitle', '')
            desc = item.get('jobExcerpt', '') or item.get('jobDescription', '')
            if any(k in loc for k in ['austria', 'vienna', 'wien', 'graz', 'linz', 'salzburg', 'innsbruck', 'europe', 'anywhere', 'worldwide']):
                raw_job = {
                    "id": f"jobicy-{item.get('id')}",
                    "title": title,
                    "company": item.get('companyName', 'Tech Company'),
                    "company_logo": item.get('companyLogo', ''),
                    "location": item.get('jobGeo', 'Remote (Austria/Europe)'),
                    "category": categorize_job(title, desc),
                    "tags": extract_tags(title + " " + desc),
                    "description": re.sub(r'<[^>]+>', ' ', desc)[:280] + "...",
                    "url": item.get('url'),
                    "source": "Jobicy / Stepstone Partner Network",
                    "posted_at": item.get('pubDate', '')[:10] or datetime.datetime.now().strftime("%Y-%m-%d")
                }
                processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                if processed:
                    jobs.append(processed)
                else:
                    print(f"  [REJECTED Jobicy] Title: '{title}' -> Reason: {reason}")
    except Exception as e:
        print(f"Error fetching Jobicy: {e}")
    return jobs

def fetch_remotive_jobs():
    """
    Fetches from Remotive's public jobs API. Note: Remotive's `category` query param
    was tested and found to be non-functional - every category slug (including a
    nonexistent one) returns the same fixed job set, so we fetch once and rely on
    location filtering + the tech-keyword gate instead of requesting multiple
    "categories" that would just be duplicate calls returning identical data.
    """
    print("[Agent Classifier] Fetching and auditing Remotive listings...")
    jobs = []
    url = 'https://remotive.com/api/remote-jobs'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=8)
        data = json.loads(res.read().decode())
        for item in data.get('jobs', []):
            loc = item.get('candidate_required_location', '').lower()
            if any(k in loc for k in ['austria', 'vienna', 'wien', 'graz', 'linz', 'europe', 'worldwide', 'anywhere']):
                title = item.get('title', '')
                desc = item.get('description', '')
                raw_job = {
                    "id": f"remotive-{item.get('id')}",
                    "title": title,
                    "company": item.get('company_name', 'Tech Company'),
                    "company_logo": item.get('company_logo_url', ''),
                    "location": item.get('candidate_required_location', 'Remote (Austria / Europe)'),
                    "category": categorize_job(title, desc),
                    "tags": extract_tags(title + " " + " ".join(item.get('tags', []))),
                    "description": re.sub(r'<[^>]+>', ' ', desc)[:280] + "...",
                    "url": item.get('url'),
                    "source": "Remotive",
                    "posted_at": item.get('publication_date', '')[:10] or datetime.datetime.now().strftime("%Y-%m-%d")
                }
                processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                if processed:
                    jobs.append(processed)
    except Exception as e:
        print(f"Error fetching Remotive: {e}")

    return jobs

def fetch_unjobs_jobs():
    """
    Fetches Vienna duty-station listings from UNjobs.org (UN/international-organization
    postings in Vienna: IAEA, UNODC, UNIDO, OSCE, OPEC Fund, ICMPD, etc.). Static HTML,
    just needs a browser User-Agent to avoid a bot-check 403. Paginates via
    /duty_stations/vie/<page> (page 1 has no suffix) until a page returns no listings.
    """
    print("[Agent Classifier] Fetching and auditing UNjobs.org (Vienna duty station) listings...")
    jobs = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    pattern = re.compile(
        r'class="jtitle" href="([^"]+)">([^<]+)</a><br>([^<]+)<br>Updated:\s*<time[^>]*datetime="([^"]+)"',
        re.DOTALL
    )
    max_pages = 5

    for page in range(1, max_pages + 1):
        url = 'https://unjobs.org/duty_stations/vie' if page == 1 else f'https://unjobs.org/duty_stations/vie/{page}'
        try:
            req = urllib.request.Request(url, headers=headers)
            page_html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            matches = pattern.findall(page_html)
            if not matches:
                break

            for job_url, title, org, updated in matches:
                title = html.unescape(title).strip()
                org = html.unescape(org).strip()

                if not agent.is_tech_job(title):
                    continue

                description = f"{title} at {org} in Vienna, Austria."
                raw_job = {
                    "id": f"unjobs-{job_url.rstrip('/').split('/')[-1]}",
                    "title": title,
                    "company": org,
                    "company_logo": "",
                    "location": "Vienna",
                    "category": categorize_job(title, description),
                    "tags": extract_tags(title),
                    "description": description,
                    "url": job_url,
                    "source": "UNjobs.org",
                    "posted_at": updated[:10] or datetime.datetime.now().strftime("%Y-%m-%d")
                }

                processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                if processed:
                    jobs.append(processed)
                else:
                    print(f"  [REJECTED UNjobs.org] Title: '{title}' -> Reason: {reason}")
        except Exception as e:
            print(f"Error fetching UNjobs.org (page {page}): {e}")
            break

    return jobs

def fetch_jobleads_jobs():
    """
    Fetches JobLeads listings via a headless browser. JobLeads renders its
    search results client-side and its SSR skips job data for bot traffic,
    so a plain HTTP request returns no listings - Playwright is required.
    """
    print("[Agent Classifier] Fetching and auditing JobLeads.com listings...")
    jobs = []
    search_terms = [
        'Software Engineer', 'Data Engineer', 'DevOps Engineer',
        'Frontend Developer', 'Backend Developer'
    ]
    search_urls = [
        f'https://www.jobleads.com/at/jobs/q/{urllib.parse.quote(term)}'
        for term in search_terms
    ]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error fetching JobLeads.com: playwright is not installed (pip install playwright && playwright install chromium)")
        return jobs

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for url in search_urls:
                    try:
                        page = browser.new_page(user_agent=user_agent)
                        page.goto(url, timeout=30000, wait_until='networkidle')
                        page.wait_for_timeout(4000)

                        cards = page.query_selector_all('[data-testid="search-job-card"]')
                        for card in cards:
                            link_el = card.query_selector('[data-testid="search-job-card-link"]')
                            title = link_el.inner_text().strip() if link_el else ""
                            href = link_el.get_attribute('href') if link_el else None
                            if not title or not href:
                                continue

                            company_el = card.query_selector('[data-testid="search-job-card-company-name"]')
                            company = company_el.inner_text().strip() if company_el else "Tech Company"

                            company_container = card.query_selector('[data-testid="search-job-card-company"]')
                            location = "Austria"
                            if company_container:
                                full_text = company_container.inner_text()
                                if '•' in full_text:
                                    location = full_text.split('•', 1)[1].strip() or "Austria"

                            work_setting_el = card.query_selector('[data-testid="job-card-chip-work-setting"]')
                            work_setting = work_setting_el.inner_text().strip() if work_setting_el else ""

                            salary_el = card.query_selector('[data-testid="job-card-chip-salary"]')
                            salary = salary_el.inner_text().strip() if salary_el else ""

                            benefit_els = card.query_selector_all('[data-testid^="job-card-chip-benefit-"]')
                            benefits = [b.inner_text().strip() for b in benefit_els if b.inner_text().strip()]

                            description_parts = [p for p in [work_setting, salary] + benefits if p]
                            description = f"{title} at {company} in {location}. " + ", ".join(description_parts)

                            job_url = urljoin(url, href)
                            job_id = href.rstrip('/').split('/')[-1]

                            raw_job = {
                                "id": f"jobleads-{job_id}",
                                "title": title,
                                "company": company,
                                "company_logo": "",
                                "location": location,
                                "category": categorize_job(title, description),
                                "tags": extract_tags(title + " " + description),
                                "description": description,
                                "url": job_url,
                                "source": "JobLeads.com",
                                "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
                            }

                            processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                            if processed:
                                jobs.append(processed)
                            else:
                                print(f"  [REJECTED JobLeads.com] Title: '{title}' -> Reason: {reason}")
                        page.close()
                    except Exception as e:
                        print(f"Error fetching JobLeads.com ({url}): {e}")
            finally:
                browser.close()
    except Exception as e:
        print(f"Error launching browser for JobLeads.com: {e}")

    return jobs

def fetch_thehub_jobs():
    """
    Fetches from thehub.io, a European startup job board. Job data is server-rendered
    into a `window.__NUXT__` state blob rather than exposed via a plain API, so this
    uses a headless browser to load each role's search page and evaluate that state
    directly (much cheaper than DOM-scraping cards, since it's already structured JSON).

    thehub.io has no dedicated Austria filter (locations are grouped into EU/Nordic
    countries/"Other Europe"/Remote), so each dev-focused role is fetched broadly and
    results are filtered down to Austria-relevant or remote listings afterward, the
    same pattern used for Jobicy/Remotive/Arbeitnow.
    """
    print("[Agent Classifier] Fetching and auditing thehub.io listings...")
    jobs = []
    roles = ['fullstackdeveloper', 'backenddeveloper', 'frontenddeveloper', 'devops', 'datascience']

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error fetching thehub.io: playwright is not installed (pip install playwright && playwright install chromium)")
        return jobs

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for role in roles:
                    url = f'https://thehub.io/jobs/?roles={role}'
                    try:
                        page = browser.new_page(user_agent=user_agent)
                        page.goto(url, timeout=30000, wait_until='networkidle')
                        state = page.evaluate("() => JSON.stringify(window.__NUXT__.state.jobs.jobs)")
                        page.close()

                        data = json.loads(state)
                        for doc in data.get('docs', []):
                            title = doc.get('title', '')
                            company = (doc.get('company') or {}).get('name', 'Tech Company')
                            location_info = doc.get('location') or {}
                            country = (location_info.get('country') or '').lower()
                            address = (location_info.get('address') or '')
                            is_remote = doc.get('isRemote', False)

                            if not (country == 'austria' or 'austria' in address.lower()
                                    or any(k in address.lower() for k in ['vienna', 'wien', 'graz', 'linz', 'salzburg', 'innsbruck'])
                                    or is_remote):
                                continue

                            job_id = doc.get('id')
                            description = f"{title} at {company}." + (" Remote." if is_remote else f" Located in {address}.")

                            raw_job = {
                                "id": f"thehub-{job_id}",
                                "title": title,
                                "company": company,
                                "company_logo": "",
                                "location": "Remote" if is_remote and not address else (address or "Austria"),
                                "category": categorize_job(title, description),
                                "tags": extract_tags(title),
                                "description": description,
                                "url": f"https://thehub.io/jobs/{job_id}",
                                "source": "TheHub.io",
                                "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
                            }

                            processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                            if processed:
                                jobs.append(processed)
                            else:
                                print(f"  [REJECTED thehub.io] Title: '{title}' -> Reason: {reason}")
                    except Exception as e:
                        print(f"Error fetching thehub.io (role={role}): {e}")
            finally:
                browser.close()
    except Exception as e:
        print(f"Error launching browser for thehub.io: {e}")

    return jobs

def fetch_ait_jobs():
    """
    Fetches from jobs.ait.ac.at (AIT Austrian Institute of Technology). The default
    /Jobs view already lists every category/section (AI, Research Engineering & Expert
    Advice, Science, Business Development, Lab & Technicians, Management, PhD, Support
    & Administration, Students, Internship, Unsolicited Application) in one response -
    no need for separate per-category requests.

    The job list itself is embedded as plain JSON in the static HTML (no browser
    needed for that part), but this is a mixed English/German feed and each job's real
    description is only rendered client-side - so for titles that already pass the
    tech-keyword gate, a headless browser fetches the rendered <main> content to give
    the language-purity check real body text instead of just a short title.
    """
    print("[Agent Classifier] Fetching and auditing jobs.ait.ac.at listings...")
    jobs = []
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    headers = {'User-Agent': user_agent}

    try:
        req = urllib.request.Request('https://jobs.ait.ac.at/Jobs', headers=headers)
        page_html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching jobs.ait.ac.at: {e}")
        return jobs

    m = re.search(r'new JobList\(\s*\$\("#jobListPlaceholder"\),\s*\$\("#jobListTemplate"\),\s*(\{.*?\})\s*\);', page_html, re.DOTALL)
    if not m:
        print("Error fetching jobs.ait.ac.at: could not locate embedded job list JSON")
        return jobs

    try:
        data = json.loads(m.group(1))
    except Exception as e:
        print(f"Error parsing jobs.ait.ac.at job list JSON: {e}")
        return jobs

    candidates = [entry for entry in data.get('Jobs', []) if entry.get('Title') and agent.is_tech_job(entry['Title'])]
    if not candidates:
        return jobs

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error fetching jobs.ait.ac.at details: playwright is not installed (pip install playwright && playwright install chromium)")
        return jobs

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for entry in candidates:
                    title = entry['Title'].strip()
                    job_id = entry.get('Id')
                    department = (entry.get('SubTitle') or '').strip()
                    location = (entry.get('Location') or '').strip() or 'Austria'
                    job_url = f"https://jobs.ait.ac.at/Job/{job_id}"

                    # A weak/empty fetch here silently falls back to title-only text for the
                    # purity check below, which can misjudge a borderline German posting -
                    # retry once before giving up, since timeouts on this site are common.
                    full_text = ""
                    last_error = None
                    for attempt in range(2):
                        try:
                            page = browser.new_page(user_agent=user_agent)
                            page.goto(job_url, timeout=25000, wait_until='load')
                            page.wait_for_timeout(2000)
                            main_el = page.query_selector('main')
                            full_text = (main_el.inner_text() if main_el else page.inner_text('body'))
                            page.close()
                            last_error = None
                            break
                        except Exception as e:
                            last_error = e
                    if last_error:
                        print(f"  Error fetching detail page for '{title}': {last_error}")

                    # Pass the fuller fetched text through for an accurate purity check;
                    # trim to a short display snippet only after classification below.
                    description = (full_text[:2000] if full_text else f"{title} at AIT ({department}) in {location}.")
                    raw_job = {
                        "id": f"ait-{job_id}",
                        "title": title,
                        "company": f"AIT - {department}" if department else "AIT Austrian Institute of Technology",
                        "company_logo": "",
                        "location": location,
                        "category": categorize_job(title, description),
                        "tags": extract_tags(title),
                        "description": description,
                        "url": job_url,
                        "source": "AIT Austrian Institute of Technology",
                        "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
                    }

                    processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
                    if processed:
                        desc = processed['description']
                        processed['description'] = desc[:280] + ("..." if len(desc) > 280 else "")
                        jobs.append(processed)
                    else:
                        print(f"  [REJECTED AIT] Title: '{title}' -> Reason: {reason}")
            finally:
                browser.close()
    except Exception as e:
        print(f"Error launching browser for jobs.ait.ac.at: {e}")

    return jobs

def fetch_prewave_jobs():
    """
    Fetches from prewave.jobs.personio.com (Prewave, a Vienna supply-chain-risk
    startup). Personio job boards expose a public XML feed at /xml with the full
    job list and rich-text descriptions already embedded (in CDATA), so no
    browser is needed - a plain HTTP request + regex parse is enough.
    """
    print("[Agent Classifier] Fetching and auditing prewave.jobs.personio.com listings...")
    jobs = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

    try:
        req = urllib.request.Request('https://prewave.jobs.personio.com/xml', headers=headers)
        xml = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching prewave.jobs.personio.com: {e}")
        return jobs

    positions = re.findall(r'<position>.*?</position>', xml, re.DOTALL)
    for pos in positions:
        def field(tag):
            m = re.search(rf'<{tag}>(.*?)</{tag}>', pos, re.DOTALL)
            return html.unescape(m.group(1).strip()) if m else ''

        title = field('name')
        if not title or not agent.is_tech_job(title):
            continue

        job_id = field('id')
        office = field('office') or 'Vienna'
        department = field('department')

        desc_values = re.findall(r'<value>\s*<!\[CDATA\[(.*?)\]\]>\s*</value>', pos, re.DOTALL)
        description_html = " ".join(desc_values)
        description = html.unescape(re.sub(r'<[^>]+>', ' ', description_html))
        description = re.sub(r'\s+', ' ', description).strip()
        if not description:
            description = f"{title} at Prewave in {office}."

        created_at = field('createdAt')[:10] or datetime.datetime.now().strftime("%Y-%m-%d")

        raw_job = {
            "id": f"prewave-{job_id}",
            "title": title,
            "company": f"Prewave - {department}" if department else "Prewave",
            "company_logo": "",
            "location": office,
            "category": categorize_job(title, description),
            "tags": extract_tags(title + " " + description),
            "description": description[:2000],
            "url": f"https://prewave.jobs.personio.com/job/{job_id}?language=en",
            "source": "Prewave (Personio)",
            "posted_at": created_at
        }

        processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
        if processed:
            desc = processed['description']
            processed['description'] = desc[:280] + ("..." if len(desc) > 280 else "")
            jobs.append(processed)
        else:
            print(f"  [REJECTED Prewave] Title: '{title}' -> Reason: {reason}")

    return jobs

def fetch_greenhouse_board_jobs(board_token, company_name, source_label):
    """
    Fetches from a Greenhouse job board (boards-api.greenhouse.io) - shared by any
    company using Greenhouse, regardless of whether their public careers page is
    hosted on job-boards.greenhouse.io or job-boards.eu.greenhouse.io, since both
    are backed by the same public JSON API with full job content available via
    ?content=true. No browser needed.

    These boards post jobs across multiple countries from one shared board, so
    (like Jobicy/Remotive/thehub.io) results are fetched in full and filtered
    down to Austria-based listings afterward.
    """
    print(f"[Agent Classifier] Fetching and auditing {source_label} (Greenhouse: {board_token}) listings...")
    jobs = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

    try:
        req = urllib.request.Request(f'https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true', headers=headers)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {source_label} (Greenhouse: {board_token}): {e}")
        return jobs

    for item in data.get('jobs', []):
        location = (item.get('location') or {}).get('name', '')
        if 'austria' not in location.lower():
            continue

        title = item.get('title', '').strip()
        if not title or not agent.is_tech_job(title):
            continue

        job_id = item.get('id')
        departments = item.get('departments') or []
        department = departments[0].get('name', '') if departments else ''

        content_html = html.unescape(item.get('content', '') or '')
        description = html.unescape(re.sub(r'<[^>]+>', ' ', content_html))
        description = re.sub(r'\s+', ' ', description).strip()
        if not description:
            description = f"{title} at {company_name} in {location}."

        raw_job = {
            "id": f"{board_token}-{job_id}",
            "title": title,
            "company": f"{company_name} - {department}" if department else company_name,
            "company_logo": "",
            "location": location or "Austria",
            "category": categorize_job(title, description),
            "tags": extract_tags(title + " " + description),
            "description": description[:2000],
            "url": item.get('absolute_url') or f"https://job-boards.greenhouse.io/{board_token}/jobs/{job_id}",
            "source": f"{source_label} (Greenhouse)",
            "posted_at": (item.get('first_published') or '')[:10] or datetime.datetime.now().strftime("%Y-%m-%d")
        }

        processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
        if processed:
            desc = processed['description']
            processed['description'] = desc[:280] + ("..." if len(desc) > 280 else "")
            jobs.append(processed)
        else:
            print(f"  [REJECTED {source_label}] Title: '{title}' -> Reason: {reason}")

    return jobs

def fetch_gropyus_jobs():
    return fetch_greenhouse_board_jobs('gropyus', 'GROPYUS', 'GROPYUS')

def fetch_gostudent_jobs():
    return fetch_greenhouse_board_jobs('gostudent', 'GoStudent', 'GoStudent')

def fetch_devjobs_jobs():
    """
    Fetches from en.devjobs.at, an Austrian dev-focused job board. Search results are
    server-rendered directly into the HTML (no separate API call), paginated via a
    &page=N query param, so a plain HTTP request + regex parse is enough (no browser
    needed). Scoped to the same filters as the site's own UI: based in Vienna
    ("wien-at"), English-language postings only ("englishOnly=on") - a plain HTTP
    request with only a generic User-Agent gets rate-limited (HTTP 429), so this also
    sends Accept / Accept-Language headers like the lifeatcanva.com fetcher does.

    Each job card is an <a href="/job/<id>">, but the site inconsistently renders an
    extra data-cy attribute before the class attribute on that tag between requests
    (no cache-buster/session difference observed - just varies), so splitting on a
    fixed "<a class=..." prefix silently returns zero cards on some fetches. Anchoring
    on the href itself and slicing up to the next href is stable across both variants.

    Unlike the other sources, this one skips the classifier's is_tech_job title gate and
    English-purity gate: the search URL itself already scopes results to English-language
    ("englishOnly=on") IT & Developer postings in Vienna, so every result here is already
    both English and tech-relevant by construction - re-filtering would just drop real
    listings (e.g. non-"developer/engineer"-worded titles) for no benefit. Metadata tags
    are still enriched via the classifier's rule-based extractor for consistency with the
    other sources.
    """
    print("[Agent Classifier] Fetching and auditing en.devjobs.at listings...")
    jobs = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    base_url = 'https://en.devjobs.at'
    search_url = f'{base_url}/jobs/search?osmState=wien-at&englishOnly=on&sort=relevance'
    max_pages = 15

    for page in range(1, max_pages + 1):
        page_url = search_url if page == 1 else f'{search_url}&page={page}'
        try:
            req = urllib.request.Request(page_url, headers=headers)
            page_html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Error fetching en.devjobs.at (page {page}): {e}")
            break

        link_matches = list(re.finditer(r'href="(/job/[a-f0-9]+)"', page_html))
        if not link_matches:
            break

        boundaries = [m.start() for m in link_matches] + [len(page_html)]
        for i, href_m in enumerate(link_matches):
            block = page_html[boundaries[i]:boundaries[i + 1]]
            title_m = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
            if not title_m:
                continue

            title = html.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))).replace('\xa0', ' ').strip()
            if not title:
                continue

            job_url = urljoin(base_url, href_m.group(1))
            job_id = href_m.group(1).rstrip('/').split('/')[-1]

            company_m = re.search(r'<p class="md:break-word[^"]*">([^<]+)</p>', block)
            company = html.unescape(company_m.group(1)).replace('\xa0', ' ').strip() if company_m else "Tech Company"

            loc_m = re.search(r'<span class="dark:text-dj-mono-dark-400 text-dj-mono-600 truncate text-ellipsis">([^<]+)</span>', block)
            location = html.unescape(loc_m.group(1)).replace('\xa0', ' ').strip() if loc_m else "Vienna"

            desc_m = re.search(r'<p class="text-dj-mono-500[^"]*line-clamp-2[^"]*">([^<]+)</p>', block)
            description = html.unescape(desc_m.group(1)).replace('\xa0', ' ').strip() if desc_m else f"{title} at {company} in {location}."

            raw_job = {
                "id": f"devjobs-{job_id}",
                "title": title,
                "company": company,
                "company_logo": "",
                "location": location,
                "category": categorize_job(title, description),
                "tags": extract_tags(title + " " + description),
                "description": description,
                "url": job_url,
                "source": "DEVjobs.at",
                "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
            }

            raw_job.update(agent.extract_metadata(title, description))
            jobs.append(raw_job)

    return jobs

def fetch_indie_jobs():
    """
    indie's internship openings (https://www.indie.inc/careers/internships/current-openings/)
    embed a Greenhouse job board widget (<div id="grnhse_app"> + boards.greenhouse.io/embed/job_board/js?for=indieinterns),
    same as gropyus/gostudent, so the shared Greenhouse helper covers it directly.
    """
    return fetch_greenhouse_board_jobs('indieinterns', 'indie', 'indie (Internships)')

def fetch_canva_jobs():
    """
    Fetches from lifeatcanva.com (Canva's careers site), which supports a
    server-rendered query-string search (?country=Austria&pagesize=100) - both the
    listing page and each job's full description are plain server-rendered HTML,
    so no browser is needed.
    """
    print("[Agent Classifier] Fetching and auditing lifeatcanva.com listings...")
    jobs = []
    # lifeatcanva.com's Cloudflare front-end silently ignores the ?country=Austria
    # filter (serving the full unfiltered international listing instead) unless the
    # request looks like a real browser - Accept/Accept-Language are required, a
    # User-Agent alone is not enough.
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    base_url = 'https://www.lifeatcanva.com'

    try:
        req = urllib.request.Request(
            f'{base_url}/en/jobs/?orderby=0&pagesize=100&page=1&radius=100&country=Austria',
            headers=headers
        )
        list_html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching lifeatcanva.com: {e}")
        return jobs

    for block in list_html.split('<div class="card card-job"')[1:]:
        id_m = re.search(r'data-id="(\d+)"', block)
        link_m = re.search(r'<a class="stretched-link js-view-job" href="([^"]+)">([^<]*)</a>', block, re.DOTALL)
        if not id_m or not link_m:
            continue

        job_id = id_m.group(1)
        title = html.unescape(link_m.group(2)).strip()
        if not title or not agent.is_tech_job(title):
            continue

        job_url = urljoin(base_url, link_m.group(1))

        meta_m = re.search(r'<ul class="list-unstyled job-meta">(.*?)</ul>', block, re.DOTALL)
        meta_items = re.findall(r'<li>\s*([^<]+?)\s*</li>', meta_m.group(1)) if meta_m else []
        location = html.unescape(meta_items[0]).strip() if meta_items else 'Austria'
        department = html.unescape(meta_items[1]).strip() if len(meta_items) > 1 else ''

        description = ""
        try:
            detail_req = urllib.request.Request(job_url, headers=headers)
            detail_html = urllib.request.urlopen(detail_req, timeout=10).read().decode('utf-8', errors='ignore')
            desc_m = re.search(r'<article class="cms-content">(.*?)</article>', detail_html, re.DOTALL)
            if desc_m:
                description = html.unescape(re.sub(r'<[^>]+>', ' ', desc_m.group(1)))
                description = re.sub(r'\s+', ' ', description).strip()
        except Exception as e:
            print(f"  Error fetching detail page for '{title}': {e}")

        if not description:
            description = f"{title} at Canva in {location}."

        raw_job = {
            "id": f"canva-{job_id}",
            "title": title,
            "company": f"Canva - {department}" if department else "Canva",
            "company_logo": "",
            "location": location or "Austria",
            "category": categorize_job(title, description),
            "tags": extract_tags(title + " " + description),
            "description": description[:2000],
            "url": job_url,
            "source": "Canva",
            "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
        }

        processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=False)
        if processed:
            desc = processed['description']
            processed['description'] = desc[:280] + ("..." if len(desc) > 280 else "")
            jobs.append(processed)
        else:
            print(f"  [REJECTED Canva] Title: '{title}' -> Reason: {reason}")

    return jobs

def main():
    print("=== Custom Local Agent Job Aggregator & Purity Filter ===")

    karriere_jobs = fetch_karriere_jobs()
    arbeitnow_jobs = fetch_arbeitnow_jobs()
    jobicy_jobs = fetch_jobicy_jobs()
    remotive_jobs = fetch_remotive_jobs()
    jobleads_jobs = fetch_jobleads_jobs()
    unjobs_jobs = fetch_unjobs_jobs()
    thehub_jobs = fetch_thehub_jobs()
    ait_jobs = fetch_ait_jobs()
    prewave_jobs = fetch_prewave_jobs()
    gropyus_jobs = fetch_gropyus_jobs()
    gostudent_jobs = fetch_gostudent_jobs()
    canva_jobs = fetch_canva_jobs()
    indie_jobs = fetch_indie_jobs()
    devjobs_jobs = fetch_devjobs_jobs()

    all_jobs = karriere_jobs + arbeitnow_jobs + jobicy_jobs + remotive_jobs + jobleads_jobs + unjobs_jobs + thehub_jobs + ait_jobs + prewave_jobs + gropyus_jobs + gostudent_jobs + canva_jobs + indie_jobs + devjobs_jobs
    
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job['title'].lower().strip(), job['company'].lower().strip())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
            
    print(f"Collected {len(unique_jobs)} strictly 100% English Tech jobs in Austria.")

    unique_jobs = enrich_jobs(unique_jobs)
    
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "jobs.json")
    
    meta_output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_count": len(unique_jobs),
        "jobs": unique_jobs
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(meta_output, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully saved to {out_path}")

if __name__ == "__main__":
    main()
