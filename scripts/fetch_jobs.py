import urllib.request
import re
import json
import os
import datetime

def categorize_job(title, description=""):
    text = (title + " " + description).lower()
    if any(k in text for k in ["data", "ai", "machine learning", "python", "analytics", "bi", "power bi", "llm"]):
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

def is_english_friendly(title, description=""):
    text = (title + " " + description).lower()
    english_keywords = [
        "english", "developer", "engineer", "data", "software", "fullstack",
        "frontend", "backend", "senior", "junior", "intern", "automation", "lead", "architect"
    ]
    if "english" in text or any(k in title.lower() for k in english_keywords):
        return True
    return False

def fetch_karriere_jobs():
    jobs = []
    urls = [
        'https://www.karriere.at/jobs/developer/wien',
        'https://www.karriere.at/jobs/data/wien',
        'https://www.karriere.at/jobs/software-engineer/austria',
        'https://www.karriere.at/jobs/ai/austria',
        'https://www.karriere.at/jobs/python/austria',
        'https://www.karriere.at/jobs/devops/austria'
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
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
                    locations = "Vienna, Austria"
                    
                job_url = j.get('link') or ('https://www.karriere.at/jobs/' + str(j.get('id')))
                teaser = j.get('snippet', '') or j.get('teaser', '') or f"Exciting tech role at {company} in {locations}."
                
                if is_english_friendly(title, teaser):
                    jobs.append({
                        "id": f"karriere-{j.get('id')}",
                        "title": title,
                        "company": company,
                        "company_logo": logo,
                        "location": locations,
                        "category": categorize_job(title, teaser),
                        "tags": extract_tags(title + " " + teaser),
                        "description": teaser,
                        "url": job_url,
                        "source": "Karriere.at",
                        "posted_at": datetime.datetime.now().strftime("%Y-%m-%d")
                    })
        except Exception as e:
            print(f"Error fetching Karriere.at ({url}): {e}")
            
    return jobs

def fetch_arbeitnow_jobs():
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
            if any(k in loc for k in ['austria', 'vienna', 'wien', 'graz', 'linz']) or 'remote' in loc:
                if is_english_friendly(title, desc):
                    jobs.append({
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
                    })
    except Exception as e:
        print(f"Error fetching Arbeitnow: {e}")
    return jobs

def fetch_jobicy_jobs():
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
            if any(k in loc for k in ['austria', 'vienna', 'wien', 'europe', 'anywhere']):
                if is_english_friendly(title, desc):
                    jobs.append({
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
                    })
    except Exception as e:
        print(f"Error fetching Jobicy: {e}")
    return jobs

def fetch_remotive_jobs():
    jobs = []
    urls = [
        'https://remotive.com/api/remote-jobs?category=software-dev',
        'https://remotive.com/api/remote-jobs?category=data'
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            res = urllib.request.urlopen(req, timeout=8)
            data = json.loads(res.read().decode())
            for item in data.get('jobs', []):
                loc = item.get('candidate_required_location', '').lower()
                if any(k in loc for k in ['austria', 'vienna', 'wien', 'europe', 'worldwide', 'anywhere']):
                    title = item.get('title', '')
                    desc = item.get('description', '')
                    jobs.append({
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
                    })
        except Exception as e:
            print(f"Error fetching Remotive ({url}): {e}")
            
    return jobs

def main():
    print("Fetching English tech jobs in Austria across Karriere.at, Stepstone Partner Network, Indeed Network, Remotive & Jobicy...")
    
    karriere_jobs = fetch_karriere_jobs()
    arbeitnow_jobs = fetch_arbeitnow_jobs()
    jobicy_jobs = fetch_jobicy_jobs()
    remotive_jobs = fetch_remotive_jobs()
    
    all_jobs = karriere_jobs + arbeitnow_jobs + jobicy_jobs + remotive_jobs
    
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job['title'].lower().strip(), job['company'].lower().strip())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
            
    print(f"Collected {len(unique_jobs)} unique English tech jobs in Austria.")
    
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
