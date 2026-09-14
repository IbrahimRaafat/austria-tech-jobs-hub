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

agent = JobClassifierAgent()

def categorize_job(title, description=""):
    text = (title + " " + description).lower()
    if any(k in text for k in ["data", "ai", "machine learning", "python", "analytics", "bi", "power bi", "llm", "geospatial", "gis"]):
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

def main():
    print("=== Custom Local Agent Job Aggregator & Purity Filter ===")

    karriere_jobs = fetch_karriere_jobs()
    arbeitnow_jobs = fetch_arbeitnow_jobs()
    jobicy_jobs = fetch_jobicy_jobs()
    remotive_jobs = fetch_remotive_jobs()
    jobleads_jobs = fetch_jobleads_jobs()
    unjobs_jobs = fetch_unjobs_jobs()

    all_jobs = karriere_jobs + arbeitnow_jobs + jobicy_jobs + remotive_jobs + jobleads_jobs + unjobs_jobs
    
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job['title'].lower().strip(), job['company'].lower().strip())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
            
    print(f"Collected {len(unique_jobs)} strictly 100% English Tech jobs in Austria.")
    
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
