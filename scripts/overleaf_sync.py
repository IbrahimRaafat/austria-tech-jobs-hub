"""Bidirectional synchronization between local Overleaf Toolkit (Docker) and your master CV.

Usage:
    python scripts/overleaf_sync.py pull      # Pull latest main.tex from Overleaf MongoDB into master CV
    python scripts/overleaf_sync.py push      # Push master.tex into Overleaf MongoDB
    python scripts/overleaf_sync.py status    # Check Overleaf container and project status
    python scripts/overleaf_sync.py watch     # Continuously watch and sync
"""

import argparse
import json
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESUME_PATH = os.environ.get('RESUME_PATH', os.path.join(REPO_ROOT, 'resume', 'master.tex'))
DESKTOP_CV_PATH = os.path.expanduser(os.path.join('~', 'Desktop', 'CV', 'main.tex'))
OVERLEAF_TOOLKIT_DIR = os.path.expanduser(os.path.join('~', 'Desktop', 'CV', 'overleaf-toolkit'))
OVERLEAF_CONTAINER = os.environ.get('OVERLEAF_CONTAINER', 'sharelatex')
MONGO_CONTAINER = os.environ.get('OVERLEAF_MONGO_CONTAINER', 'mongo')


def check_docker():
    """Checks if Docker is responsive."""
    try:
        res = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


def get_running_containers():
    """Returns list of running container names."""
    try:
        res = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    except Exception:
        pass
    return []


def run_mongo_eval(js_code):
    """Executes a JS script in the Overleaf mongo container using mongosh or mongo."""
    containers = get_running_containers()
    mongo_name = next((c for c in containers if 'mongo' in c.lower()), None)
    if not mongo_name:
        return None, "Overleaf mongo container is not running. Start it with Overleaf Toolkit (bin/up -d)."

    # Try mongosh first, then mongo
    for cmd in ['mongosh', 'mongo']:
        try:
            res = subprocess.run(
                ['docker', 'exec', '-i', mongo_name, cmd, 'sharelatex', '--quiet', '--eval', js_code],
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode == 0:
                return res.stdout.strip(), None
        except Exception as e:
            return None, str(e)
    return None, "Failed to run mongo query inside container."


def pull_from_overleaf(target_path=None):
    """Pulls main.tex content from Overleaf MongoDB and saves it to master resume."""
    dest = target_path or RESUME_PATH
    js = """
    const doc = db.docs.findOne({ name: 'main.tex' });
    if (!doc) {
        print(JSON.stringify({ error: 'main.tex not found in Overleaf database' }));
    } else {
        print(JSON.stringify({ lines: doc.lines }));
    }
    """
    output, err = run_mongo_eval(js)
    if err:
        return False, err
    if not output:
        return False, "No response from Overleaf database."

    try:
        data = json.loads(output)
        if 'error' in data:
            return False, data['error']
        lines = data.get('lines', [])
        content = "\n".join(lines)
        if not content.strip():
            return False, "Overleaf main.tex is empty."

        # Write to master resume
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(content)

        # Also write to Desktop CV if separate
        if os.path.exists(DESKTOP_CV_PATH) and not os.path.samefile(dest, DESKTOP_CV_PATH):
            with open(DESKTOP_CV_PATH, 'w', encoding='utf-8') as f:
                f.write(content)

        return True, f"Successfully pulled {len(lines)} lines from Overleaf to {dest}"
    except Exception as e:
        return False, f"Failed to parse Overleaf doc: {e}"


def push_to_overleaf(source_path=None):
    """Pushes master.tex into Overleaf MongoDB doc collection."""
    src = source_path or RESUME_PATH
    if not os.path.exists(src):
        return False, f"Master resume not found at {src}"

    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    escaped_json = json.dumps(lines)

    js = f"""
    const res = db.docs.updateOne(
        {{ name: 'main.tex' }},
        {{ $set: {{ lines: {escaped_json} }} }}
    );
    print(JSON.stringify({{ matched: res.matchedCount, modified: res.modifiedCount }}));
    """
    output, err = run_mongo_eval(js)
    if err:
        return False, err

    try:
        data = json.loads(output)
        if data.get('matched', 0) == 0:
            return False, "Could not find a document named 'main.tex' in Overleaf. Create a project in Overleaf first."
        return True, f"Successfully pushed {len(lines)} lines from {src} to Overleaf"
    except Exception as e:
        return False, f"Failed to push to Overleaf: {e}"


def status():
    """Reports status of Overleaf toolkit and CV synchronization."""
    docker_ok = check_docker()
    containers = get_running_containers() if docker_ok else []
    overleaf_running = any('sharelatex' in c.lower() or 'overleaf' in c.lower() for c in containers)
    mongo_running = any('mongo' in c.lower() for c in containers)

    master_exists = os.path.exists(RESUME_PATH)
    desktop_exists = os.path.exists(DESKTOP_CV_PATH)
    hardlinked = False
    try:
        if master_exists and desktop_exists:
            hardlinked = os.path.samefile(RESUME_PATH, DESKTOP_CV_PATH)
    except Exception:
        pass

    return {
        'docker_available': docker_ok,
        'overleaf_running': overleaf_running,
        'mongo_running': mongo_running,
        'overleaf_url': 'http://localhost:80',
        'master_path': os.path.relpath(RESUME_PATH, REPO_ROOT),
        'desktop_path': DESKTOP_CV_PATH,
        'hardlinked': hardlinked,
        'toolkit_dir': OVERLEAF_TOOLKIT_DIR,
        'containers': containers
    }


def main():
    parser = argparse.ArgumentParser(description="Sync master CV with local Overleaf Toolkit")
    parser.add_argument('action', choices=['pull', 'push', 'status', 'watch'], help="Action to perform")
    parser.add_argument('--path', default=None, help="Custom master.tex path")
    args = parser.parse_args()

    if args.action == 'status':
        s = status()
        print("=== Overleaf & CV Synchronization Status ===")
        print(f"Docker available: {'Yes' if s['docker_available'] else 'No (start Docker Desktop)'}")
        print(f"Overleaf container: {'Running' if s['overleaf_running'] else 'Stopped'}")
        print(f"Mongo container: {'Running' if s['mongo_running'] else 'Stopped'}")
        print(f"Local Overleaf URL: {s['overleaf_url']}")
        print(f"Master resume: {s['master_path']}")
        print(f"Desktop CV: {s['desktop_path']}")
        print(f"Desktop & Master linked: {'Yes (instant sync)' if s['hardlinked'] else 'No'}")
        print("===========================================")
    elif args.action == 'pull':
        ok, msg = pull_from_overleaf(args.path)
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.action == 'push':
        ok, msg = push_to_overleaf(args.path)
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.action == 'watch':
        print("Watching Overleaf for CV updates (Ctrl+C to stop)...")
        last_pull = ""
        while True:
            time.sleep(5)
            ok, msg = pull_from_overleaf(args.path)
            if ok and msg != last_pull:
                print(f"[{time.strftime('%X')}] {msg}")
                last_pull = msg


if __name__ == '__main__':
    main()
