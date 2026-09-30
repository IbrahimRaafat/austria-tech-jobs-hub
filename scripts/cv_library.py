"""CV library for the local dashboard: tailored runs from resume/output plus your older CVs.

Older CVs are read (never modified) from CV_ARCHIVE_DIR (default: ~/Desktop/CV). Their PDFs are
compiled on demand into resume/archive_pdfs/ so the archive folder itself stays untouched.
"""
import datetime
import json
import os
import re
import shutil

from llm_client import REPO_ROOT
import tailor_resume

ARCHIVE_DIR = os.path.expanduser(os.environ.get('CV_ARCHIVE_DIR', os.path.join('~', 'Desktop', 'CV')))
ARCHIVE_PDF_ROOT = os.path.join(REPO_ROOT, 'resume', 'archive_pdfs')
ARCHIVE_EXTS = ('.tex', '.pdf', '.docx')
MASTER_SLUG = '_master'  # slugify() never yields a leading underscore, so this cannot clash


def _iso(ts):
    return datetime.datetime.fromtimestamp(ts).isoformat(timespec='minutes')


def archive_slug(filename):
    return tailor_resume.slugify(os.path.splitext(filename)[0], 80) + os.path.splitext(filename)[1].lower().replace('.', '-')


def list_tailored():
    runs = []
    root = tailor_resume.OUTPUT_ROOT
    if not os.path.isdir(root):
        return runs
    for name in os.listdir(root):
        result_path = os.path.join(root, name, 'result.json')
        if not os.path.isfile(result_path):
            continue
        try:
            with open(result_path, encoding='utf-8') as f:
                result = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        run_dir = os.path.join(root, name)
        files = {key: f"/tailored/{name}/{fname}" for key, fname in (
            ('resume_tex', 'resume.tex'), ('resume_pdf', 'resume.pdf'),
            ('cover_letter', 'cover_letter.md'), ('report', 'report.md'),
        ) if os.path.isfile(os.path.join(run_dir, fname))}
        analysis = result.get('analysis', {})
        runs.append({
            'id': name,
            'created': _iso(os.path.getmtime(result_path)),
            'title': result.get('job', {}).get('title') or analysis.get('job_title') or 'Untitled job',
            'company': result.get('job', {}).get('company') or analysis.get('company') or '',
            'url': result.get('job', {}).get('url') or '',
            'match_score': analysis.get('match_score'),
            'gaps': analysis.get('gaps', [])[:4],
            'verdict': result.get('factcheck', {}).get('verdict'),
            'model': result.get('model', ''),
            'files': files,
        })
    return sorted(runs, key=lambda r: r['created'], reverse=True)


def _tailored_for(tex_path):
    """Reads the '% Tailored for: ...' comment many of the hand-made CVs carry."""
    try:
        with open(tex_path, encoding='utf-8', errors='ignore') as f:
            head = f.read(600)
    except OSError:
        return ''
    m = re.search(r'%\s*Tailored for:\s*(.+)', head)
    return m.group(1).strip() if m else ''


def list_archive():
    items = []
    if not os.path.isdir(ARCHIVE_DIR):
        return items
    for name in os.listdir(ARCHIVE_DIR):
        path = os.path.join(ARCHIVE_DIR, name)
        if not (os.path.isfile(path) and name.lower().endswith(ARCHIVE_EXTS)):
            continue
        slug = archive_slug(name)
        item = {
            'id': slug,
            'name': name,
            'modified': _iso(os.path.getmtime(path)),
            'kind': os.path.splitext(name)[1].lower().lstrip('.'),
            'source_url': f"/archive/{slug}/source",
            'tailored_for': _tailored_for(path) if name.lower().endswith('.tex') else '',
            'pdf_url': None,
        }
        if item['kind'] == 'pdf':
            item['pdf_url'] = item['source_url']
        elif item['kind'] == 'tex':
            cached = os.path.join(ARCHIVE_PDF_ROOT, slug, 'cv.pdf')
            if os.path.isfile(cached) and os.path.getmtime(cached) >= os.path.getmtime(path):
                item['pdf_url'] = f"/archive/{slug}/pdf"
        items.append(item)
    return sorted(items, key=lambda i: i['modified'], reverse=True)


def find_archive_file(slug):
    """Maps a slug back to a file directly inside ARCHIVE_DIR (no path traversal possible)."""
    if slug == MASTER_SLUG:
        return tailor_resume.DEFAULT_RESUME if os.path.isfile(tailor_resume.DEFAULT_RESUME) else None
    if not os.path.isdir(ARCHIVE_DIR):
        return None
    for name in os.listdir(ARCHIVE_DIR):
        path = os.path.join(ARCHIVE_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(ARCHIVE_EXTS) and archive_slug(name) == slug:
            return path
    return None


def archive_pdf_path(slug):
    path = os.path.join(ARCHIVE_PDF_ROOT, slug, 'cv.pdf')
    return path if os.path.isfile(path) else None


def compile_archive(slug):
    """Compiles an archived .tex into resume/archive_pdfs/<slug>/cv.pdf. Returns (pdf_url or None, message)."""
    source = find_archive_file(slug)
    if not source or not source.lower().endswith('.tex'):
        return None, 'CV not found'
    work = os.path.join(ARCHIVE_PDF_ROOT, slug)
    os.makedirs(work, exist_ok=True)
    shutil.copyfile(source, os.path.join(work, 'cv.tex'))
    pdf, message = tailor_resume.compile_pdf(os.path.join(work, 'cv.tex'), os.path.dirname(os.path.abspath(source)))
    return (f"/archive/{slug}/pdf" if pdf else None), message


def compile_tailored(run_id):
    run_dir = os.path.realpath(os.path.join(tailor_resume.OUTPUT_ROOT, run_id))
    tex = os.path.join(run_dir, 'resume.tex')
    if not run_dir.startswith(os.path.realpath(tailor_resume.OUTPUT_ROOT) + os.sep) or not os.path.isfile(tex):
        return None, 'Tailored CV not found'
    pdf, message = tailor_resume.compile_pdf(tex, os.path.dirname(os.path.abspath(tailor_resume.DEFAULT_RESUME)))
    return (f"/tailored/{run_id}/resume.pdf" if pdf else None), message


def delete_tailored(run_id):
    root = os.path.realpath(tailor_resume.OUTPUT_ROOT)
    run_dir = os.path.realpath(os.path.join(root, run_id))
    if not run_dir.startswith(root + os.sep) or not os.path.isfile(os.path.join(run_dir, 'result.json')):
        return False
    shutil.rmtree(run_dir)
    return True


def library():
    master = tailor_resume.DEFAULT_RESUME
    cached = os.path.join(ARCHIVE_PDF_ROOT, MASTER_SLUG, 'cv.pdf')
    master_pdf = os.path.isfile(master) and os.path.isfile(cached) and os.path.getmtime(cached) >= os.path.getmtime(master)
    return {
        'tailored': list_tailored(),
        'archive': list_archive(),
        'archive_dir': ARCHIVE_DIR,
        'master': {
            'exists': os.path.isfile(master),
            'path': os.path.relpath(master, REPO_ROOT),
            'modified': _iso(os.path.getmtime(master)) if os.path.isfile(master) else None,
            'id': MASTER_SLUG,
            'source_url': f"/archive/{MASTER_SLUG}/source",
            'pdf_url': f"/archive/{MASTER_SLUG}/pdf" if master_pdf else None,
        },
        'latex_engine': tailor_resume.detect_latex_engine(),
    }
