"""AI resume tailor: adapts a master LaTeX resume to a specific job posting.

Pipeline (each step is a separate LLM "agent" call):
  1. Analyst      - extracts job requirements and scores the master resume against them (match / gap analysis)
  2. Tailor       - rewrites the editable LaTeX regions to emphasise relevant, *existing* experience
  3. Fact-checker - compares tailored vs. master resume and flags any claim not supported by the master;
                    flagged issues are sent back to the Tailor for one revision round
  4. Writer       - drafts a short cover letter grounded in the master resume

Then the tailored .tex is compiled to PDF if a LaTeX engine (tectonic, latexmk, pdflatex, xelatex) is installed.

Usage:
  python scripts/tailor_resume.py --job karriere-10029431          # a job from data/jobs.json
  python scripts/tailor_resume.py --url https://example.com/jobs/1 # any external posting
  python scripts/tailor_resume.py --text-file posting.txt          # pasted job description
Options: --provider local|cloud|auto, --model NAME, --resume PATH, --no-cover-letter, --no-pdf

By default the whole resume body (between \\begin{document} and \\end{document}) is tailored. To restrict
edits, wrap sections in your master resume with:
  % TAILOR:BEGIN summary
  ...
  % TAILOR:END
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import REPO_ROOT, LLMError, get_client, parse_json_response  # noqa: E402

JOBS_PATH = os.path.join(REPO_ROOT, 'data', 'jobs.json')
DEFAULT_RESUME = os.environ.get('RESUME_PATH', os.path.join(REPO_ROOT, 'resume', 'master.tex'))
OUTPUT_ROOT = os.path.join(REPO_ROOT, 'resume', 'output')
MAX_JOB_CHARS = 12000
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

STEPS = [
    ('job', 'Loading job posting'),
    ('analyze', 'Analyst: match / gap analysis'),
    ('tailor', 'Tailor: rewriting resume'),
    ('factcheck', 'Fact-checker: verifying claims'),
    ('cover', 'Writer: cover letter'),
    ('compile', 'Compiling PDF'),
]

TRUTH_RULES = (
    "Hard rules - never break them:\n"
    "- Never invent employers, job titles, dates, degrees, certifications, metrics, tools or skills.\n"
    "- Only use facts present in the MASTER RESUME. You may rephrase, reorder, condense and emphasise.\n"
    "- A job keyword may be used only if the master resume shows the same skill/tool (synonyms are fine).\n"
    "- Keep every number, date and name exactly as in the master resume.\n"
    "- Never name a tool the candidate has not used, not even as a comparison: no '(Django-equivalent)', "
    "'similar to X', 'X-like' or 'transferable to X'. Missing skills stay missing.\n"
)


# --------------------------------------------------------------------------------------------
# Job posting loading
# --------------------------------------------------------------------------------------------

def html_to_text(raw):
    """Converts HTML to readable text, keeping paragraph and list structure."""
    s = re.sub(r'<(script|style|header|footer|nav|noscript)[^>]*>.*?</\1>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<li[^>]*>', '\n- ', s, flags=re.IGNORECASE)
    s = re.sub(r'<(br|/p|/div|/h[1-6]|/li|/ul|/ol|/tr)[^>]*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    lines = [' '.join(line.split()) for line in s.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return re.sub(r'\n{3,}', '\n\n', text)


def _find_job_posting_ld(raw):
    """Returns the schema.org JobPosting object embedded in the page, if any (most job boards include one)."""
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', raw, flags=re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else data.get('@graph', [data])
        for item in items:
            if not isinstance(item, dict):
                continue
            types = item.get('@type')
            types = types if isinstance(types, list) else [types]
            if 'JobPosting' in types:
                return item
    return None


def fetch_job_page(url):
    """Fetches an external job posting. Returns dict(title, company, text)."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')

    posting = _find_job_posting_ld(raw)
    if posting and posting.get('description'):
        org = posting.get('hiringOrganization') or {}
        return {
            'title': html.unescape(posting.get('title') or ''),
            'company': html.unescape(org.get('name', '') if isinstance(org, dict) else str(org)),
            'text': html_to_text(posting['description']),
        }

    title_match = re.search(r'<title[^>]*>(.*?)</title>', raw, flags=re.DOTALL | re.IGNORECASE)
    return {
        'title': html.unescape(title_match.group(1).strip()) if title_match else '',
        'company': '',
        'text': html_to_text(raw),
    }


def load_jobs():
    if not os.path.exists(JOBS_PATH):
        return []
    with open(JOBS_PATH, encoding='utf-8') as f:
        return json.load(f).get('jobs', [])


def resolve_job(job_id=None, url=None, text=None):
    """Builds the job dict from a jobs.json id, an external URL, or pasted text."""
    warnings = []
    if text and text.strip():
        return {'title': '', 'company': '', 'url': url or '', 'text': text.strip()[:MAX_JOB_CHARS]}, warnings

    job = {}
    if job_id:
        job = next((j for j in load_jobs() if j.get('id') == job_id), None)
        if not job:
            raise ValueError(f"Job id '{job_id}' not found in data/jobs.json")
        url = job.get('url')

    if not url:
        raise ValueError("Provide a job id, a URL, or the job description text")

    fetched = {'title': '', 'company': '', 'text': ''}
    try:
        fetched = fetch_job_page(url)
    except Exception as e:
        warnings.append(f"Could not fetch {url}: {e}")

    result = {
        'title': job.get('title') or fetched['title'],
        'company': job.get('company') or fetched['company'],
        'location': job.get('location', ''),
        'url': url,
        'text': fetched['text'][:MAX_JOB_CHARS],
    }
    if len(result['text']) < 400:
        # JS-rendered pages or blocked requests: fall back to what the scraper stored
        fallback = job.get('description', '')
        result['text'] = (result['text'] + '\n' + fallback).strip()
        warnings.append("Job page returned little text; results may be generic. Paste the job description instead for better tailoring.")
    return result, warnings


# --------------------------------------------------------------------------------------------
# LaTeX handling
# --------------------------------------------------------------------------------------------

REGION_RE = re.compile(r'^[ \t]*%[ \t]*TAILOR:BEGIN[ \t]+(\S+)[^\n]*\n(.*?)^[ \t]*%[ \t]*TAILOR:END[^\n]*$',
                       flags=re.DOTALL | re.MULTILINE)


def split_document(tex):
    begin = tex.find('\\begin{document}')
    end = tex.rfind('\\end{document}')
    if begin == -1 or end == -1:
        raise ValueError("Master resume must contain \\begin{document} ... \\end{document}")
    begin += len('\\begin{document}')
    return tex[:begin], tex[begin:end], tex[end:]


def extract_regions(tex):
    """Returns ({name: content}, mode). Uses TAILOR markers when present, else the whole document body."""
    marked = {m.group(1): m.group(2) for m in REGION_RE.finditer(tex)}
    if marked:
        return marked, 'markers'
    _, body, _ = split_document(tex)
    return {'body': body}, 'body'


def apply_regions(tex, regions, mode):
    if mode == 'body':
        pre, _, post = split_document(tex)
        return pre + '\n' + regions['body'].strip('\n') + '\n' + post

    def replace(m):
        name = m.group(1)
        header = m.group(0).split('\n', 1)[0]
        footer = m.group(0).rsplit('\n', 1)[-1]
        return f"{header}\n{regions.get(name, m.group(2)).strip(chr(10))}\n{footer}"
    return REGION_RE.sub(replace, tex)


def strip_comments(tex):
    return re.sub(r'(?<!\\)%.*', '', tex)


def fix_common_escapes(fragment):
    """LLMs often write '30%' which LaTeX treats as a comment, silently truncating the line."""
    return re.sub(r'(\d)%', r'\1\\%', fragment)


def check_latex(fragment, original):
    """Cheap structural validation of a tailored LaTeX fragment. Returns a list of problems."""
    problems = []
    s = strip_comments(fragment).replace('\\\\', '  ')
    s = re.sub(r'\\[{}%&$#_]', '  ', s)

    depth = 0
    for ch in s:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth < 0:
                break
    if depth != 0:
        problems.append(f"unbalanced braces (net {depth:+d})")

    stack = []
    for kind, env in re.findall(r'\\(begin|end)\{([^}]+)\}', s):
        if kind == 'begin':
            stack.append(env)
        elif not stack or stack.pop() != env:
            problems.append(f"mismatched \\end{{{env}}}")
            break
    if stack and not problems:
        problems.append(f"unclosed environment(s): {', '.join(stack)}")

    for forbidden in ('\\documentclass', '\\begin{document}', '\\end{document}', '\\usepackage'):
        if forbidden in fragment and forbidden not in original:
            problems.append(f"must not contain {forbidden}")

    if len(fragment.strip()) < 0.4 * len(original.strip()):
        problems.append("output is far shorter than the original section - content was dropped")
    return problems


def resume_to_text(tex):
    """Rough plain-text view of a LaTeX resume for the analysis/fact-check prompts."""
    try:
        _, body, _ = split_document(tex)
    except ValueError:
        body = tex
    return '\n'.join(line.rstrip() for line in strip_comments(body).splitlines() if line.strip())


# --------------------------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------------------------

def job_block(job):
    header = ' | '.join(x for x in (job.get('title'), job.get('company'), job.get('location')) if x)
    return f"JOB POSTING{f' ({header})' if header else ''}:\n{job['text']}"


def agent_analyze(llm, job, resume_text):
    system = ("You are a senior technical recruiter in Austria. You assess candidate fit honestly and precisely. "
              "Respond with a single JSON object only.")
    prompt = (
        f"{job_block(job)}\n\nMASTER RESUME:\n{resume_text}\n\n"
        "Analyse the fit between the resume and the job. Return JSON with exactly these keys:\n"
        '{"job_title": str, "company": str,\n'
        ' "must_have": [str]  // the key hard requirements from the posting,\n'
        ' "nice_to_have": [str],\n'
        ' "keywords": [str]  // ATS keywords/technologies from the posting,\n'
        ' "matched": [str]  // requirements the resume clearly shows, each with brief evidence,\n'
        ' "gaps": [str]  // requirements the resume does not show,\n'
        ' "match_score": int  // 0-100, be realistic,\n'
        ' "recommendations": [str]  // how to tailor the resume using ONLY existing experience,\n'
        ' "summary": str  // 2-3 sentence honest verdict}'
    )
    data = parse_json_response(llm.generate(system, prompt, json_mode=True, temperature=0.2))
    data['match_score'] = max(0, min(100, int(data.get('match_score') or 0)))
    for key in ('must_have', 'nice_to_have', 'keywords', 'matched', 'gaps', 'recommendations'):
        value = data.get(key) or []
        data[key] = [str(v) for v in value] if isinstance(value, list) else [str(value)]
    return data


def _parse_region_output(text, names):
    out = {}
    for m in re.finditer(r'<<<REGION\s+(\S+?)>>>\s*\n(.*?)\n?<<<END>>>', text, flags=re.DOTALL):
        if m.group(1) in names:
            out[m.group(1)] = re.sub(r'^```(?:latex|tex)?\s*\n|\n```\s*$', '', m.group(2).strip('\n'))
    if not out and len(names) == 1:
        # Some models ignore the delimiters for a single region; accept a bare/fenced LaTeX answer
        fenced = re.search(r'```(?:latex|tex)?\s*\n(.*?)```', text, flags=re.DOTALL)
        out[names[0]] = (fenced.group(1) if fenced else text).strip('\n')
    return out


def agent_tailor(llm, job, analysis, regions, preamble, feedback=None):
    """Returns ({name: tailored_latex}, warnings). Invalid regions are retried once, then kept as original."""
    names = list(regions)
    system = (
        "You are an expert resume writer who edits LaTeX resumes. You tailor resumes to a job posting "
        "while staying 100% truthful to the candidate's real experience.\n\n" + TRUTH_RULES +
        "\nLaTeX rules:\n"
        "- Keep the exact same custom commands, macros and environments used in the original (they are defined in the preamble).\n"
        "- Keep the section structure. You may reorder bullets/skills and rewrite bullet text.\n"
        "- Escape special characters in text: \\% \\& \\# \\_ \\$.\n"
        "- Keep roughly the same length so the resume still fits its current page count.\n"
        "- Output only LaTeX inside the requested delimiters, no explanations."
    )
    regions_text = '\n\n'.join(f"<<<REGION {n}>>>\n{c.strip(chr(10))}\n<<<END>>>" for n, c in regions.items())
    prompt = (
        f"{job_block(job)}\n\n"
        f"ANALYSIS:\n- Must-have: {'; '.join(analysis['must_have'])}\n- Keywords: {', '.join(analysis['keywords'])}\n"
        f"- Matched: {'; '.join(analysis['matched'])}\n- Recommendations: {'; '.join(analysis['recommendations'])}\n\n"
        f"PREAMBLE (for reference only - macro definitions, do not output):\n{preamble[-4000:]}\n\n"
        f"MASTER RESUME SECTIONS TO TAILOR:\n{regions_text}\n\n"
    )
    if feedback:
        prompt += "A fact-checker rejected your previous draft. Fix ALL of these issues:\n" + '\n'.join(f"- {f}" for f in feedback) + "\n\n"
    prompt += (
        "Tailor each section for this job: lead the summary with the most relevant real experience, put the most "
        "relevant bullets first, mirror the posting's terminology where the resume genuinely supports it, and "
        "de-emphasise unrelated details. Return every section in the same format:\n"
        "<<<REGION name>>>\n...tailored LaTeX...\n<<<END>>>"
    )

    warnings = []
    result = _parse_region_output(llm.generate(system, prompt, temperature=0.4), names)
    retry = {}
    for name in names:
        if name not in result:
            retry[name] = ["section missing from output"]
            continue
        result[name] = fix_common_escapes(result[name])
        problems = check_latex(result[name], regions[name])
        if problems:
            retry[name] = problems

    for name, problems in retry.items():
        fix_prompt = (
            f"Your tailored LaTeX for section '{name}' has problems: {'; '.join(problems)}.\n\n"
            f"ORIGINAL SECTION:\n{regions[name]}\n\n"
            f"YOUR DRAFT:\n{result.get(name, '(missing)')}\n\n"
            f"Return the corrected tailored section only, as:\n<<<REGION {name}>>>\n...\n<<<END>>>"
        )
        fixed = _parse_region_output(llm.generate(system, fix_prompt, temperature=0.2), [name]).get(name)
        fixed = fix_common_escapes(fixed) if fixed else None
        if fixed and not check_latex(fixed, regions[name]):
            result[name] = fixed
        else:
            result[name] = regions[name]
            warnings.append(f"Section '{name}' kept unchanged: tailored LaTeX was invalid ({'; '.join(problems)})")
    return result, warnings


def agent_factcheck(llm, master_text, tailored_text):
    system = ("You are a meticulous fact-checker for resumes. You compare a tailored resume against the "
              "candidate's master resume, which is the only source of truth. Respond with a single JSON object only.")
    prompt = (
        f"MASTER RESUME (source of truth):\n{master_text}\n\n"
        f"TAILORED RESUME:\n{tailored_text}\n\n"
        "List every statement in the TAILORED resume that is not supported by the MASTER resume: invented or "
        "inflated skills, tools, metrics, titles, dates, employers, responsibilities or seniority. Rephrasing, "
        "reordering, summarising and removing content are fine and must NOT be flagged.\n"
        'Return JSON: {"issues": [{"claim": str, "problem": str, "severity": "high" | "low"}], "verdict": "pass" | "fail"}\n'
        '"high" = fabricated or materially exaggerated; "low" = slightly stretched wording.'
    )
    data = parse_json_response(llm.generate(system, prompt, json_mode=True, temperature=0.0))
    issues = [i for i in (data.get('issues') or []) if isinstance(i, dict) and i.get('claim')]
    return {'issues': issues, 'verdict': 'fail' if any(i.get('severity') == 'high' for i in issues) else 'pass'}


TERM_RE = re.compile(r'(?<![\\\w])[A-Za-z][A-Za-z0-9+#.]*[A-Za-z0-9+#]')


def _terms(text):
    return {part for token in TERM_RE.findall(text) for part in token.split('.') if part}


def new_terms(master_text, tailored_text):
    """Deterministic safety net (no LLM): tool-like terms in the tailored resume that never appear in the
    master, e.g. 'Django' sneaking in as '(Django-equivalent)'. Runs even when the fact-check model is down."""
    known = {t.lower() for t in _terms(master_text)}
    suspicious = {t for t in _terms(tailored_text)
                  if t.lower() not in known and (t[0].isupper() or re.search(r'[0-9+#]', t))}
    return sorted(suspicious)


def agent_cover_letter(llm, job, analysis, resume_text):
    system = ("You write concise, specific, non-generic cover letters for tech roles in Austria, in English. "
              + TRUTH_RULES + "- Avoid cliches like 'I am writing to express my interest' or 'passionate'.")
    prompt = (
        f"{job_block(job)}\n\nMASTER RESUME:\n{resume_text}\n\n"
        f"Strongest matches: {'; '.join(analysis['matched'][:6])}\n\n"
        "Write a cover letter of 200-300 words: a specific opening tied to the company/role, two short paragraphs "
        "connecting real experience to the key requirements, and a brief closing. Use the candidate's name from the "
        "resume for the sign-off. Output plain Markdown only (no subject line placeholders like [Date])."
    )
    return llm.generate(system, prompt, temperature=0.6).strip()


# --------------------------------------------------------------------------------------------
# PDF compilation
# --------------------------------------------------------------------------------------------

LOCAL_ENGINES = ('tectonic', 'latexmk', 'pdflatex', 'xelatex')
# Self-hosted Overleaf (overleaf-toolkit) runs TeX Live inside this container
OVERLEAF_CONTAINER = os.environ.get('OVERLEAF_CONTAINER', 'sharelatex')
RESOURCE_EXTS = ('.cls', '.sty', '.bst', '.png', '.jpg', '.jpeg', '.pdf', '.eps')


def overleaf_container_running():
    if not shutil.which('docker'):
        return False
    try:
        proc = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', OVERLEAF_CONTAINER],
                              capture_output=True, text=True, timeout=15)
        return proc.stdout.strip() == 'true'
    except (subprocess.SubprocessError, OSError):
        return False


def detect_latex_engine():
    """Name of the engine compile_pdf would use, or None."""
    local = next((e for e in LOCAL_ENGINES if shutil.which(e)), None)
    if local:
        return local
    return f"Overleaf ({OVERLEAF_CONTAINER} container)" if overleaf_container_running() else None


def _latex_errors(log_text):
    lines = log_text.splitlines()
    errors = []
    for i, line in enumerate(lines):
        if line.startswith('!'):
            errors.append(' '.join(line.strip() for line in lines[i:i + 2]))
    missing = re.findall(r"File `([^']+)\.(?:sty|cls)' not found", log_text)
    if missing:
        errors.append(f"missing LaTeX package(s): {', '.join(sorted(set(missing)))} - install with "
                      f"`docker exec {OVERLEAF_CONTAINER} tlmgr install <package>` (or MiKTeX package manager)")
    return ' | '.join(errors[:5]) or 'see resume.log in the output folder'


def _compile_in_overleaf(tex_path, resource_dir, unicode_engine):
    """Copies the resume into the running Overleaf container, runs latexmk there, and copies the PDF back."""
    out_dir = os.path.dirname(tex_path)
    stem = os.path.splitext(os.path.basename(tex_path))[0]
    work = f"/tmp/resume-tailor-{os.getpid()}-{int(datetime.datetime.now().timestamp())}"
    c = OVERLEAF_CONTAINER

    def docker(*args, timeout=60):
        return subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)

    try:
        docker('exec', c, 'mkdir', '-p', f'{work}/res')
        docker('cp', tex_path, f'{c}:{work}/{stem}.tex')
        for f in os.listdir(resource_dir):
            path = os.path.join(resource_dir, f)
            if os.path.isfile(path) and f.lower().endswith(RESOURCE_EXTS):
                docker('cp', path, f'{c}:{work}/res/')
        proc = docker('exec', '-w', work, '-e', f'TEXINPUTS={work}/res//:', c,
                      'latexmk', '-xelatex' if unicode_engine else '-pdf', '-interaction=nonstopmode',
                      '-halt-on-error', f'{stem}.tex', timeout=240)
        pdf = os.path.join(out_dir, f'{stem}.pdf')
        log_path = os.path.join(out_dir, f'{stem}.log')
        docker('cp', f'{c}:{work}/{stem}.log', log_path)
        if proc.returncode == 0:
            docker('cp', f'{c}:{work}/{stem}.pdf', pdf)
        if proc.returncode == 0 and os.path.exists(pdf):
            return pdf, f"Compiled with Overleaf ({c} container)"
        log = open(log_path, encoding='utf-8', errors='ignore').read() if os.path.exists(log_path) else proc.stdout + proc.stderr
        return None, f"Overleaf compile failed: {_latex_errors(log)}"
    except subprocess.TimeoutExpired:
        return None, "Overleaf compile timed out"
    finally:
        try:
            docker('exec', c, 'rm', '-rf', work)
        except (subprocess.SubprocessError, OSError):
            pass


def compile_pdf(tex_path, resource_dir):
    """Compiles with a local engine if installed, else the self-hosted Overleaf container.
    Returns (pdf_path or None, message)."""
    out_dir = os.path.dirname(tex_path)
    name = os.path.basename(tex_path)
    with open(tex_path, encoding='utf-8') as f:
        needs_unicode_engine = re.search(r'\\usepackage(\[[^\]]*\])?\{fontspec\}', f.read()) is not None

    env = dict(os.environ)
    env['TEXINPUTS'] = resource_dir + os.pathsep + env.get('TEXINPUTS', '')  # custom .cls/.sty/images next to master.tex
    candidates = [
        ('tectonic', ['tectonic', '-Z', f'search-path={resource_dir}', '--keep-logs', name]),
        ('latexmk', ['latexmk', '-xelatex' if needs_unicode_engine else '-pdf', '-interaction=nonstopmode', '-halt-on-error', name]),
        ('xelatex' if needs_unicode_engine else 'pdflatex', ['xelatex' if needs_unicode_engine else 'pdflatex', '-interaction=nonstopmode', '-halt-on-error', name]),
    ]
    for exe, cmd in candidates:
        if not shutil.which(exe):
            continue
        try:
            proc = subprocess.run(cmd, cwd=out_dir, env=env, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            return None, f"{exe} timed out"
        pdf = os.path.splitext(tex_path)[0] + '.pdf'
        if proc.returncode == 0 and os.path.exists(pdf):
            return pdf, f"Compiled with {exe}"
        return None, f"{exe} failed: {_latex_errors(proc.stdout + proc.stderr)}"

    if overleaf_container_running():
        return _compile_in_overleaf(tex_path, resource_dir, needs_unicode_engine)
    return None, ("No LaTeX engine found - start your Overleaf toolkit (bin/up -d) or install Tectonic/MiKTeX; "
                  "resume.tex can also be uploaded to Overleaf")


# --------------------------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------------------------

def slugify(text, max_len=40):
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')[:max_len].strip('-') or 'job'


def write_report(path, job, analysis, factcheck, warnings, llm_label):
    lines = [
        f"# {analysis.get('job_title') or job.get('title') or 'Job'} - {analysis.get('company') or job.get('company') or ''}",
        "",
        f"- Source: {job.get('url') or 'pasted text'}",
        f"- Model: {llm_label}",
        f"- Match score: **{analysis['match_score']}/100**",
        "",
        analysis.get('summary', ''),
        "",
        "## Matched", *[f"- {m}" for m in analysis['matched']], "",
        "## Gaps", *[f"- {g}" for g in analysis['gaps']], "",
        "## Recommendations", *[f"- {r}" for r in analysis['recommendations']], "",
        "## Keywords", ', '.join(analysis['keywords']), "",
        f"## Fact-check: {factcheck['verdict'].upper()}",
    ]
    lines += [f"- **{i.get('severity', 'low')}**: {i['claim']} - {i.get('problem', '')}" for i in factcheck['issues']] or ["- No unsupported claims found."]
    if warnings:
        lines += ["", "## Warnings", *[f"- {w}" for w in warnings]]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def run_pipeline(job_id=None, url=None, text=None, provider='auto', model=None, resume_path=None,
                 cover_letter=True, make_pdf=True, on_step=None):
    """Runs all agents and writes results to resume/output/<date>_<company>_<title>/. Returns a result dict."""
    def step(key, status, detail=''):
        if on_step:
            on_step(key, status, detail)

    resume_path = resume_path or DEFAULT_RESUME
    if not os.path.exists(resume_path):
        raise FileNotFoundError(f"Master resume not found at {resume_path}. Copy resume/master.example.tex to resume/master.tex and fill it in.")
    with open(resume_path, encoding='utf-8') as f:
        master_tex = f.read()
    preamble, _, _ = split_document(master_tex)
    regions, mode = extract_regions(master_tex)
    master_text = resume_to_text(master_tex)

    llm = get_client(provider, model)

    step('job', 'running')
    job, warnings = resolve_job(job_id, url, text)
    step('job', 'done', job.get('title') or job.get('url') or 'pasted description')

    step('analyze', 'running', llm.label)
    analysis = agent_analyze(llm, job, master_text)
    job['title'] = job.get('title') or analysis.get('job_title', '')
    job['company'] = job.get('company') or analysis.get('company', '')
    step('analyze', 'done', f"match {analysis['match_score']}/100")

    step('tailor', 'running')
    tailored_regions, tailor_warnings = agent_tailor(llm, job, analysis, regions, preamble)
    warnings += tailor_warnings
    tailored_tex = apply_regions(master_tex, tailored_regions, mode)
    step('tailor', 'done', f"{len(regions)} section(s)")

    # Fact-check and cover letter are best-effort: if the model is unavailable, the tailored
    # resume is still saved, with a warning to review it manually.
    step('factcheck', 'running')
    try:
        factcheck = agent_factcheck(llm, master_text, resume_to_text(tailored_tex))
    except (LLMError, ValueError) as e:
        factcheck = {'issues': [], 'verdict': 'unchecked'}
        warnings.append(f"Fact-check could not run ({e}). Review the tailored resume manually before sending.")
    if factcheck['verdict'] == 'fail':
        step('factcheck', 'running', 'sending issues back to Tailor for revision')
        feedback = [f"{i['claim']}: {i.get('problem', '')}" for i in factcheck['issues']]
        try:
            revised_regions, tailor_warnings = agent_tailor(llm, job, analysis, regions, preamble, feedback=feedback)
            revised_tex = apply_regions(master_tex, revised_regions, mode)
            recheck = agent_factcheck(llm, master_text, resume_to_text(revised_tex))
            warnings += tailor_warnings
            tailored_tex, factcheck = revised_tex, dict(recheck, revised=True)
        except (LLMError, ValueError) as e:
            warnings.append(f"Revision after fact-check could not run ({e}); the flagged issues below are still in the resume.")
    factcheck['issues'] += [
        {'claim': term, 'problem': 'not found anywhere in your master resume - make sure it is accurate',
         'severity': 'low', 'source': 'term-check'}
        for term in new_terms(master_text, resume_to_text(tailored_tex))
    ]
    if factcheck['verdict'] == 'unchecked':
        step('factcheck', 'error', 'model unavailable - review manually')
    else:
        step('factcheck', 'done', f"{factcheck['verdict']} ({len(factcheck['issues'])} issue(s))")

    date = datetime.date.today().isoformat()
    out_dir = os.path.join(OUTPUT_ROOT, f"{date}_{slugify(job.get('company'), 25)}_{slugify(job.get('title'))}")
    os.makedirs(out_dir, exist_ok=True)
    tex_path = os.path.join(out_dir, 'resume.tex')
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(tailored_tex)

    files = {'resume_tex': tex_path}
    if cover_letter:
        step('cover', 'running')
        try:
            letter = agent_cover_letter(llm, job, analysis, master_text)
            files['cover_letter'] = os.path.join(out_dir, 'cover_letter.md')
            with open(files['cover_letter'], 'w', encoding='utf-8') as f:
                f.write(letter + '\n')
            step('cover', 'done')
        except LLMError as e:
            warnings.append(f"Cover letter could not be generated ({e}).")
            step('cover', 'error', 'model unavailable')
    else:
        step('cover', 'skipped')

    pdf_message = 'skipped'
    if make_pdf:
        step('compile', 'running')
        pdf, pdf_message = compile_pdf(tex_path, os.path.dirname(os.path.abspath(resume_path)))
        if pdf:
            files['resume_pdf'] = pdf
        step('compile', 'done' if pdf else 'skipped', pdf_message)
    else:
        step('compile', 'skipped')

    files['report'] = os.path.join(out_dir, 'report.md')
    write_report(files['report'], job, analysis, factcheck, warnings, llm.label)

    result = {
        'job': {k: job.get(k) for k in ('title', 'company', 'location', 'url')},
        'model': llm.label,
        'analysis': analysis,
        'factcheck': factcheck,
        'warnings': warnings,
        'pdf': pdf_message,
        'output_dir': out_dir,
        'files': files,
    }
    with open(os.path.join(out_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def main():
    parser = argparse.ArgumentParser(description="Tailor your LaTeX resume to a job with AI agents (local Ollama or Gemini).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--job', help="job id from data/jobs.json (e.g. karriere-10029431)")
    source.add_argument('--url', help="external job posting URL")
    source.add_argument('--text-file', help="file containing the job description")
    parser.add_argument('--provider', default='auto', choices=['auto', 'local', 'cloud', 'ollama', 'gemini'])
    parser.add_argument('--model', help="override the model name")
    parser.add_argument('--resume', help=f"master resume .tex (default: {os.path.relpath(DEFAULT_RESUME, REPO_ROOT)})")
    parser.add_argument('--no-cover-letter', action='store_true')
    parser.add_argument('--no-pdf', action='store_true')
    args = parser.parse_args()

    text = None
    if args.text_file:
        with open(args.text_file, encoding='utf-8') as f:
            text = f.read()

    labels = dict(STEPS)

    def on_step(key, status, detail):
        print(f"  [{status:>7}] {labels[key]}{f' - {detail}' if detail else ''}", flush=True)

    try:
        result = run_pipeline(args.job, args.url, text, args.provider, args.model, args.resume,
                              cover_letter=not args.no_cover_letter, make_pdf=not args.no_pdf, on_step=on_step)
    except (LLMError, ValueError, FileNotFoundError) as e:
        sys.exit(f"Error: {e}")

    a = result['analysis']
    print(f"\nMatch score: {a['match_score']}/100 - {a.get('summary', '')}")
    if a['gaps']:
        print("Gaps: " + '; '.join(a['gaps'][:5]))
    for issue in result['factcheck']['issues']:
        print(f"Fact-check [{issue.get('severity')}]: {issue['claim']} - {issue.get('problem', '')}")
    for w in result['warnings']:
        print(f"Warning: {w}")
    print(f"\nOutput: {result['output_dir']}")


if __name__ == '__main__':
    main()
