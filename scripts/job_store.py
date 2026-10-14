"""
Run-to-run bookkeeping for data/jobs.json: deduplication across sources, `first_seen`
dates carried over from the previous run, and a per-source health report.
"""
import json
import os
import re
from collections import Counter

# Gender/inclusivity markers Austrian and German ads append to titles: (m/w/d), (f/m/x),
# m/f/d, (all genders), (w/m/d) ... They vary between boards for the same job.
_GENDER_MARKER_RE = re.compile(
    r'\(\s*(?:[mwfdx*]\s*/\s*){1,3}[mwfdx*]\s*\)|\b(?:[mwfdx]\s*/\s*){2,3}[mwfdx]\b|\(\s*all genders?\s*\)',
    re.IGNORECASE,
)
_COMPANY_SUFFIX_RE = re.compile(
    r'\b(?:gmbh|ag|kg|og|se|ltd|limited|inc|llc|e\.?\s?u\.?|co\.?|& co\.?|holding)\b\.?',
    re.IGNORECASE,
)


def _normalize(text):
    text = re.sub(r'[^\w]+', ' ', text.lower())
    return ' '.join(text.split())


def dedup_key(job):
    title = _GENDER_MARKER_RE.sub(' ', job.get('title', ''))
    company = _COMPANY_SUFFIX_RE.sub(' ', job.get('company', ''))
    return _normalize(title), _normalize(company)


def dedupe(jobs):
    """One job per (title, company) after normalisation, keeping the copy with the
    longest description (list-page teasers vary a lot between boards)."""
    best = {}
    order = []
    for job in jobs:
        key = dedup_key(job)
        if key not in best:
            order.append(key)
            best[key] = job
        elif len(job.get('description', '')) > len(best[key].get('description', '')):
            best[key] = job
    return [best[key] for key in order]


def load_previous(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f).get('jobs', [])
    except (OSError, ValueError):
        return []


def stamp_first_seen(jobs, previous, today):
    """Sets `first_seen` (YYYY-MM-DD): carried over when the job was in the previous run,
    else today. Jobs from runs before this field existed fall back to their posted_at."""
    by_id = {j.get('id'): j for j in previous}
    by_key = {dedup_key(j): j for j in previous}
    for job in jobs:
        prev = by_id.get(job.get('id')) or by_key.get(dedup_key(job))
        job['first_seen'] = (prev.get('first_seen') or prev.get('posted_at') or today) if prev else today


def source_report(jobs, previous, min_previous=3):
    """Prints jobs per source and returns warnings for sources that went from
    `min_previous`+ jobs last run to none - usually a changed page layout or a block."""
    now = Counter(j.get('source', '?') for j in jobs)
    before = Counter(j.get('source', '?') for j in previous)
    print("[Sources] jobs this run (last run):")
    for source in sorted(set(now) | set(before)):
        print(f"  {source:<45} {now[source]:>4} ({before[source]})")
    return [f"{source} returned 0 jobs (had {before[source]} last run) - check its scraper"
            for source in sorted(before) if before[source] >= min_previous and now[source] == 0]


def emit_warnings(warnings):
    """Prints warnings; inside GitHub Actions they also show up as run annotations."""
    in_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    for w in warnings:
        print(f"::warning::{w}" if in_actions else f"WARNING: {w}")
