"""Local server for the dashboard with the AI resume tailor enabled.

    python scripts/resume_server.py            # then open http://localhost:8765
    python scripts/resume_server.py --port 9000

Serves the static dashboard plus a small JSON API used by app.js. It binds to 127.0.0.1 only and never
serves your master resume or .env - only the dashboard files and generated output under resume/output/.
The public GitHub Pages site has no API, so the tailor UI stays hidden there.
"""
import argparse
import json
import mimetypes
import os
import sys
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import REPO_ROOT, provider_status  # noqa: E402
import tailor_resume  # noqa: E402
import cv_library  # noqa: E402

STATIC_FILES = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/styles.css': 'styles.css',
                '/cvs': 'cvs.html', '/cvs.html': 'cvs.html', '/cvs.js': 'cvs.js'}
TASKS = {}
TASKS_LOCK = threading.Lock()


def output_url(path):
    rel = os.path.relpath(path, tailor_resume.OUTPUT_ROOT).replace(os.sep, '/')
    return '/tailored/' + rel


def run_task(task_id, params):
    task = TASKS[task_id]

    def on_step(key, status, detail):
        with TASKS_LOCK:
            task['steps'][key] = {'status': status, 'detail': detail}

    try:
        result = tailor_resume.run_pipeline(
            job_id=params.get('job_id'), url=params.get('url'), text=params.get('text'),
            provider=params.get('provider', 'auto'), cover_letter=params.get('cover_letter', True), on_step=on_step,
        )
        result['files'] = {k: output_url(v) for k, v in result['files'].items()}
        result['output_dir'] = os.path.relpath(result['output_dir'], REPO_ROOT)
        with TASKS_LOCK:
            task.update(status='done', result=result)
    except Exception as e:
        traceback.print_exc()
        with TASKS_LOCK:
            for step in task['steps'].values():
                if step['status'] == 'running':
                    step['status'] = 'error'
            task.update(status='error', error=str(e))


class Handler(BaseHTTPRequestHandler):
    def _host_ok(self):
        # Blocks DNS-rebinding attacks from websites open in your browser
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0]
        return host in ('localhost', '127.0.0.1', '[::1]')

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, download=False):
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if path.endswith(('.tex', '.md')):
            ctype = 'text/plain; charset=utf-8'
        with open(path, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(path)}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == '/api/tailor/status':
            resume = tailor_resume.DEFAULT_RESUME
            return self._send_json({
                'providers': provider_status(),
                'resume_found': os.path.exists(resume),
                'resume_path': os.path.relpath(resume, REPO_ROOT),
                'latex_engine': tailor_resume.detect_latex_engine(),
            })

        if path.startswith('/api/tailor/tasks/'):
            with TASKS_LOCK:
                task = TASKS.get(path.rsplit('/', 1)[-1])
                data = json.loads(json.dumps(task)) if task else None
            return self._send_json(data) if data else self._send_json({'error': 'unknown task'}, 404)

        if path == '/api/cvs':
            return self._send_json(cv_library.library())

        if path.startswith('/archive/'):
            parts = path.split('/')  # ['', 'archive', slug, 'source' | 'pdf']
            if len(parts) == 4:
                target = (cv_library.find_archive_file(parts[2]) if parts[3] == 'source'
                          else cv_library.archive_pdf_path(parts[2]) if parts[3] == 'pdf' else None)
                if target:
                    return self._send_file(target, download='download=1' in parsed.query or target.endswith('.docx'))
            return self.send_error(404)

        if path.startswith('/tailored/'):
            root = os.path.realpath(tailor_resume.OUTPUT_ROOT)
            target = os.path.realpath(os.path.join(root, path[len('/tailored/'):]))
            if target.startswith(root + os.sep) and os.path.isfile(target):
                return self._send_file(target, download='download=1' in parsed.query)
            return self.send_error(404)

        if path in STATIC_FILES:
            return self._send_file(os.path.join(REPO_ROOT, STATIC_FILES[path]))
        if path.startswith('/data/') and path.endswith('.json'):
            target = os.path.realpath(os.path.join(REPO_ROOT, path.lstrip('/')))
            if target.startswith(os.path.realpath(os.path.join(REPO_ROOT, 'data')) + os.sep) and os.path.isfile(target):
                return self._send_file(target)
        self.send_error(404)

    def do_POST(self):
        if not self._host_ok():
            return self.send_error(403)
        route = urlparse(self.path).path
        if route not in ('/api/tailor', '/api/cvs/compile', '/api/cvs/delete'):
            return self.send_error(404)
        # Requiring JSON forces a CORS preflight, so other websites cannot trigger actions
        if not (self.headers.get('Content-Type') or '').startswith('application/json'):
            return self._send_json({'error': 'Content-Type must be application/json'}, 415)
        try:
            length = int(self.headers.get('Content-Length') or 0)
            params = json.loads(self.rfile.read(min(length, 200_000)) or b'{}')
        except (ValueError, json.JSONDecodeError):
            return self._send_json({'error': 'invalid JSON body'}, 400)

        if route == '/api/cvs/compile':
            compile_fn = cv_library.compile_tailored if params.get('kind') == 'tailored' else cv_library.compile_archive
            pdf_url, message = compile_fn(str(params.get('id', '')))
            return self._send_json({'pdf_url': pdf_url, 'message': message}, 200 if pdf_url else 422)
        if route == '/api/cvs/delete':
            ok = cv_library.delete_tailored(str(params.get('id', '')))
            return self._send_json({'deleted': ok}, 200 if ok else 404)

        if not any(params.get(k) for k in ('job_id', 'url', 'text')):
            return self._send_json({'error': 'provide job_id, url or text'}, 400)

        task_id = uuid.uuid4().hex[:12]
        with TASKS_LOCK:
            TASKS[task_id] = {
                'id': task_id, 'status': 'running', 'error': None, 'result': None,
                'steps': {key: {'status': 'pending', 'detail': ''} for key, _ in tailor_resume.STEPS},
                'step_labels': dict(tailor_resume.STEPS),
            }
        threading.Thread(target=run_task, args=(task_id, params), daemon=True).start()
        self._send_json({'task_id': task_id}, 202)

    def log_message(self, fmt, *args):
        if '/api/tailor/tasks/' not in getattr(self, 'path', ''):  # skip progress-polling noise
            super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description="Serve the jobs dashboard locally with the AI resume tailor.")
    parser.add_argument('--port', type=int, default=int(os.environ.get('TAILOR_PORT', 8765)))
    args = parser.parse_args()

    status = provider_status()
    print(f"Resume tailor running at http://localhost:{args.port}  (your CVs: http://localhost:{args.port}/cvs)")
    print(f"  local : {status['local']['label']} - {'available' if status['local']['available'] else 'not running (ollama serve)'}")
    print(f"  cloud : {status['cloud']['label']} - {'available' if status['cloud']['available'] else 'no GEMINI_API_KEY'}")
    if not os.path.exists(tailor_resume.DEFAULT_RESUME):
        print(f"  WARNING: no master resume at {os.path.relpath(tailor_resume.DEFAULT_RESUME, REPO_ROOT)} "
              "(copy resume/master.example.tex)")
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
