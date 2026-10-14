"""
Telegram alert for jobs that are new since the previous scrape.

    python scripts/send_alerts.py --previous previous_jobs.json [--dry-run]

Environment:
  TELEGRAM_BOT_TOKEN  bot token from @BotFather (GitHub secret)
  TELEGRAM_CHAT_ID    your chat id, see README (GitHub secret)
  ALERT_FILTERS       optional JSON (GitHub variable), every key optional:
                      {"cities": ["Vienna", "Remote"], "min_salary": 50000,
                       "include_no_salary": false, "seniority": ["Junior", "Mid-Level"],
                       "categories": ["Data & AI"], "keywords": ["python", "data"],
                       "exclude_keywords": ["sap"]}
  BOARD_URL           link at the end of the message (default: this repo's GitHub Pages)

"New" means: in data/jobs.json but not in --previous (the last committed copy), so
re-running the workflow on the same day does not repeat alerts. Without TELEGRAM_*
the script prints the message and exits successfully, so forks without a bot still work.
"""
import argparse
import html
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from job_store import load_previous  # noqa: E402

JOBS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'jobs.json')
TELEGRAM_LIMIT = 4096
MAX_JOBS_LISTED = 25


def new_jobs(current, previous):
    seen = {j.get('id') for j in previous}
    return [j for j in current if j.get('id') not in seen]


def matches(job, filters):
    cities = filters.get('cities')
    if cities and not set(cities) & set(job.get('cities') or [job.get('city')]):
        return False
    if filters.get('seniority') and job.get('seniority') not in filters['seniority']:
        return False
    if filters.get('categories') and job.get('category') not in filters['categories']:
        return False
    min_salary = filters.get('min_salary')
    if min_salary:
        salary = job.get('salary')
        if salary is None and not filters.get('include_no_salary'):
            return False
        if salary is not None and salary['annual_max'] < min_salary:
            return False
    text = ' '.join([job.get('title', ''), job.get('description', ''), ' '.join(job.get('tags') or [])]).lower()
    if filters.get('keywords') and not any(k.lower() in text for k in filters['keywords']):
        return False
    if any(k.lower() in text for k in filters.get('exclude_keywords') or []):
        return False
    return True


def describe_filters(filters):
    parts = []
    if filters.get('cities'):
        parts.append('/'.join(filters['cities']))
    if filters.get('min_salary'):
        parts.append(f"€{filters['min_salary'] // 1000}k+")
    for key in ('seniority', 'categories', 'keywords'):
        if filters.get(key):
            parts.append('/'.join(filters[key]))
    return ' · '.join(parts)


def _job_entry(job):
    e = html.escape
    facts = [f"📍 {e(job.get('location', ''))}"]
    if job.get('salary'):
        facts.append(f"💰 {e(job['salary']['label'])}")
    if job.get('seniority'):
        facts.append(e(job['seniority']))
    return (f"<b>{e(job.get('title', ''))}</b> — {e(job.get('company', ''))}\n"
            f"{' · '.join(facts)}\n"
            f"<a href=\"{e(job.get('url', ''), quote=True)}\">View posting</a>")


def build_messages(jobs, filters, board_url):
    """Telegram messages (HTML), split to stay under the message size limit."""
    shown = jobs[:MAX_JOBS_LISTED]
    header = f"🇦🇹 <b>{len(jobs)} new tech job{'s' if len(jobs) != 1 else ''} in Austria</b>"
    if describe_filters(filters):
        header += f"\nFilters: {html.escape(describe_filters(filters))}"
    footer = ""
    if len(jobs) > len(shown):
        footer += f"+{len(jobs) - len(shown)} more. "
    if board_url:
        footer += f"<a href=\"{html.escape(board_url, quote=True)}\">Open the board →</a>"

    messages, current = [], header
    for entry in [_job_entry(j) for j in shown] + ([footer] if footer else []):
        if len(current) + 2 + len(entry) > TELEGRAM_LIMIT:
            messages.append(current)
            current = entry
        else:
            current += "\n\n" + entry
    messages.append(current)
    return messages


def send_telegram(token, chat_id, text):
    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        if not json.load(resp).get('ok'):
            raise RuntimeError("Telegram rejected the message")


def default_board_url():
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if '/' not in repo:
        return ''
    owner, name = repo.split('/', 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--previous', required=True, help='jobs.json from the previous run')
    parser.add_argument('--dry-run', action='store_true', help='print instead of sending')
    args = parser.parse_args()

    if not os.path.exists(args.previous):
        print(f"[Alerts] No previous jobs file at {args.previous} - skipping so a first run doesn't alert on every job.")
        return
    try:
        filters = json.loads(os.environ.get('ALERT_FILTERS') or '{}')
    except ValueError:
        sys.exit("[Alerts] ALERT_FILTERS is not valid JSON")

    fresh = [j for j in new_jobs(load_previous(JOBS_PATH), load_previous(args.previous)) if matches(j, filters)]
    if not fresh:
        print("[Alerts] No new jobs match the alert filters.")
        return
    messages = build_messages(fresh, filters, os.environ.get('BOARD_URL') or default_board_url())

    token, chat_id = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if args.dry_run or not (token and chat_id):
        if not args.dry_run:
            print("[Alerts] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set - printing instead of sending.")
        print('\n\n----------\n\n'.join(messages))
        return
    try:
        for text in messages:
            send_telegram(token, chat_id, text)
    except Exception as e:  # HTTPError's message does not include the URL, so the token stays out of logs
        sys.exit(f"[Alerts] Sending to Telegram failed: {e}")
    print(f"[Alerts] Sent {len(fresh)} new jobs in {len(messages)} Telegram message(s).")


if __name__ == '__main__':
    main()
