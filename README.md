# 🇦🇹 Austria Tech Jobs in English (Automated Aggregator)

An automated daily aggregator for English-friendly software, data, AI, frontend, backend, and cloud/DevOps jobs across Austria (Vienna, Graz, Linz, and Remote).

## 🚀 How it Works
1. **Daily Automation**: A GitHub Actions workflow runs every day at **08:00 AM Vienna time (06:00 UTC)**.
2. **Scraper**: Runs `scripts/fetch_jobs.py` to aggregate roles from Austria's top job sources (Karriere.at, Remotive, Jobicy, JobLeads.com, etc.).
3. **Data**: Saves formatted listings into `data/jobs.json`.
4. **Live Web Page**: `index.html` loads `data/jobs.json` to present a fast, searchable, filterable dashboard hosted free on **GitHub Pages**.

---

## ⚡ Deployment to GitHub Pages (2 Steps)

### Step 1: Create a GitHub Repository & Push
Open your terminal in `C:\Users\Ibrahim\Desktop\austria-tech-jobs-hub` and run:

```bash
git init
git add .
git commit -m "Initial commit: Austria Tech Jobs Hub"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/austria-tech-jobs-hub.git
git push -u origin main
```

### Step 2: Enable GitHub Pages
1. Go to your repository on GitHub: `https://github.com/YOUR_GITHUB_USERNAME/austria-tech-jobs-hub`
2. Click **Settings** > **Pages**.
3. Under **Build and deployment** > **Source**, select **Deploy from a branch**.
4. Set Branch to `main` / `/ (root)` and click **Save**.

Your live website will be accessible at:
`https://YOUR_GITHUB_USERNAME.github.io/austria-tech-jobs-hub/`

---

## 🛠 Local Testing
Install dependencies once (Playwright is used to render JobLeads.com, which requires a real browser):

```bash
pip install -r requirements.txt
playwright install chromium
```

Then run the scraper manually on your computer anytime:

```bash
python scripts/fetch_jobs.py
```

To view the dashboard locally, simply open `index.html` in your web browser.

---

## 🧠 Optional: Local AI Classifier (Ollama)
The 100% English-purity filter (`scripts/agent_classifier.py`) is always rule-based NLP — it was empirically tested and audited, and testing showed small LLMs (including local models) are unreliable at this specific judgment call (e.g. `llama3.2:1b`/`3b` both mislabeled genuinely English postings as German when the text mentioned "visa sponsorship" or "EU work permit"). So no LLM can ever cause a real English job to be silently dropped.

What an LLM *can* do, when run **locally**, is enrich metadata tags (seniority, visa/relocation, experience, city) on jobs that already passed the rule-based gate — no API key, no cloud calls, nothing sent off your machine.

1. Install [Ollama](https://ollama.com/download) (free, runs as a background service on Windows/Mac/Linux).
2. Pull the default model (~2GB):
   ```bash
   ollama pull llama3.2:3b
   ```
3. Just run the scraper as usual — `agent_classifier.py` detects `http://localhost:11434` automatically and uses it:
   ```bash
   python scripts/fetch_jobs.py
   ```

If Ollama isn't running (e.g. in the GitHub Actions daily automation), it silently falls back to rule-based keyword metadata extraction — no errors, no config needed.

Optional overrides via environment variables:
- `OLLAMA_MODEL` — use a different local model (default: `llama3.2:3b`)
- `OLLAMA_URL` — point at a different Ollama endpoint (default: `http://localhost:11434/api/generate`)

---

## ✨ AI Resume Tailor (local web app + CLI)
Tailors your LaTeX resume to any job on the board, or to any external posting (URL or pasted text), using a chain of AI agents:

1. **Analyst**: extracts requirements and scores your fit (match score, matched skills, gaps, recommendations)
2. **Tailor**: rewrites your resume sections to lead with relevant experience. It never invents skills, employers, dates or metrics.
3. **Fact-checker**: compares the tailored resume against your master resume. It sends unsupported claims back to the Tailor for one revision round and reports anything left over.
4. **Writer**: drafts a short, specific cover letter

Everything runs on your machine. Your resume is only sent to Google if you choose cloud mode.

### Setup
1. Create your master resume from the template (`resume/` is gitignored, so it never reaches GitHub):
   ```bash
   cp resume/master.example.tex resume/master.tex
   ```
   Wrap the sections the AI may edit in `% TAILOR:BEGIN <name>` / `% TAILOR:END`. The header, education and anything else outside the markers stay untouched. Without markers, the whole document body is tailored.
2. Pick a model (or both):
   - **Local**: install [Ollama](https://ollama.com/download), then `ollama pull qwen2.5:7b` (7B+ models handle LaTeX far better than 3B ones; set `TAILOR_OLLAMA_MODEL` to use another model)
   - **Cloud**: copy `.env.example` to `.env` and set `GEMINI_API_KEY` ([get one free](https://aistudio.google.com/apikey)). The default model is `gemini-3.8-flash` (override it with `GEMINI_MODEL`).
3. Optional, for PDF output: PDFs come from a local LaTeX engine ([Tectonic](https://tectonic-typesetting.github.io/) or MiKTeX) if one is installed. Otherwise the tailor compiles inside a running self-hosted **Overleaf Toolkit** container (`sharelatex`; set `OVERLEAF_CONTAINER` if yours is named differently), so Docker Desktop and the toolkit (`bin/up -d`) need to be running. With neither, you get `resume.tex` only.

### Use it
**Web UI:** run the dashboard locally with tailoring enabled:
```bash
python scripts/resume_server.py      # open http://localhost:8765
```
Each job card gets a **✨ Tailor resume** button, and a panel at the top accepts external URLs or pasted job descriptions. The public GitHub Pages site doesn't show any of this.

**My CVs dashboard** (`http://localhost:8765/cvs`): lists every tailored CV (match score, fact-check status, gaps, PDF preview, .tex, cover letter, report, delete) and your earlier CVs from `CV_ARCHIVE_DIR` (default `~/Desktop/CV`). Older `.tex` CVs can be built to PDF with one click; the PDFs go to `resume/archive_pdfs/`, and the archive folder itself is never modified.

**CLI:**
```bash
python scripts/tailor_resume.py --job karriere-10029847          # job id from data/jobs.json
python scripts/tailor_resume.py --url https://company.com/jobs/1  # external posting
python scripts/tailor_resume.py --text-file posting.txt --provider cloud
```
Options: `--provider local|cloud|auto` (auto = Ollama if running, else Gemini), `--model`, `--resume`, `--no-cover-letter`, `--no-pdf`.

Results go to `resume/output/<date>_<company>_<title>/`: `resume.tex` (+ `resume.pdf`), `cover_letter.md`, `report.md` (match/gap analysis and fact-check) and `result.json`.

**Reliability:** Gemini free-tier keys often get `503` (overloaded) or `429` (rate limit). Each call is retried with backoff (honoring Google's `retryDelay`) and then falls back through `GEMINI_FALLBACK_MODELS`. If the fact-check or cover letter still can't run, the tailored CV is saved anyway and marked **fact-check unchecked**. A local term check (no AI) always flags technology names that don't appear in your master resume.

> Always review the output before sending. The fact-checker catches most exaggerations, but it is an LLM too.
