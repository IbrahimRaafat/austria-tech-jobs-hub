# 🇦🇹 Austria Tech Jobs Hub + AI Resume Tailor

Two tools in one repo:

1. **A public job board.** Every morning a scraper collects English-language tech jobs in Austria and publishes them to a searchable, filterable site on GitHub Pages. It runs for free and needs no server.
2. **A private AI resume tailor.** On your own computer you get a "✨ Tailor resume" button on every job, plus a box for any external posting. AI agents adapt your LaTeX resume to the job, check it for invented claims, write a cover letter, build a PDF, and keep everything on a **My CVs** dashboard.

Anyone can fork this repo and run both for themselves. **The repo contains no one's resume, API keys or tailored CVs.** Those files are gitignored and live only on the computer of whoever uses the tool.

---

## Contents
- [What runs where](#what-runs-where)
- [Requirements](#requirements)
- [Part 1: Your own public job board](#part-1-your-own-public-job-board)
- [Part 2: The resume tailor (local)](#part-2-the-resume-tailor-local)
- [Configuration reference](#configuration-reference)
- [Customize it for your needs](#customize-it-for-your-needs)
- [Privacy](#privacy)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)

---

## What runs where

| Component | Runs on | Who can see it |
|---|---|---|
| Source code and `data/jobs.json` (public job listings) | Your GitHub repo | Public |
| Daily scraper (`scripts/fetch_jobs.py`) | GitHub Actions, 06:00 UTC | Public logs |
| Job board website (`index.html`) | GitHub Pages | Public. The tailor UI is hidden there. |
| Tailor app, **My CVs** dashboard, APIs (`scripts/resume_server.py`) | Your computer, `http://localhost:8765` | Only you. It binds to 127.0.0.1 and rejects requests from other sites. |
| Your master resume, tailored CVs, PDFs, API key | Your computer (`resume/`, `.env`) | Only you. These paths are gitignored. |
| AI model | **Cloud:** Google Gemini API. **Local:** Ollama on your machine. | Cloud mode sends the job text and your resume to Google. Local mode keeps everything on your machine. |
| PDF compilation | Local LaTeX, or a self-hosted Overleaf container in Docker | Only you |

You can use Part 2 without Part 1. A plain clone is enough to tailor resumes, and you don't need a GitHub account.

---

## Requirements

| For | You need |
|---|---|
| Everything | [Python 3.10+](https://www.python.org/downloads/) and [Git](https://git-scm.com/downloads) |
| Running the scraper locally | `pip install -r requirements.txt` and `playwright install chromium` |
| Cloud AI (recommended) | A free [Google AI Studio API key](https://aistudio.google.com/apikey) |
| Local AI (optional) | [Ollama](https://ollama.com/download) and a 7B+ model. It needs a decent GPU or it will be very slow. |
| PDF output (optional) | One of: [Tectonic](https://tectonic-typesetting.github.io/), [MiKTeX](https://miktex.org/)/TeX Live, or the [Overleaf Toolkit](https://github.com/overleaf/toolkit) running in Docker |

The tailor itself only uses the Python standard library. There are no pip packages to install for it.

---

## Part 1: Your own public job board

1. **Fork** this repository on GitHub (the **Fork** button, top right).
2. **Enable Actions:** in your fork, open the **Actions** tab and click *"I understand my workflows, go ahead and enable them"*.
3. **Let the workflow push data:** go to **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**, and save.
4. **Enable Pages:** go to **Settings → Pages → Build and deployment**, choose *Deploy from a branch*, select branch `main` and folder `/ (root)`, and save.
5. **Run the scraper once:** open **Actions → Daily Austria Tech Jobs Scraper → Run workflow**.

Your board is now live at `https://<your-username>.github.io/<repo-name>/` and refreshes every day at 06:00 UTC. The fork starts with the original repo's `data/jobs.json` (public job listings only). Your first workflow run replaces it.

**Preview it locally** without the tailor: open `index.html` through any static server (for example `python -m http.server`), or use the tailor server from Part 2.

---

## Part 2: The resume tailor (local)

### How it works
Clicking **Tailor resume** runs four AI agents plus a safety check:

1. **Analyst** reads the full job posting and scores your fit from 0 to 100. It lists matched skills, gaps and recommendations.
2. **Tailor** rewrites only the resume sections you allow. It reorders and rephrases to lead with your relevant experience, and it is told never to invent tools, employers, dates or numbers. If its LaTeX output is broken, that section is kept unchanged.
3. **Fact-checker** compares the result against your master resume. Unsupported claims go back to the Tailor for one revision round.
4. **Writer** drafts a short cover letter using only facts from your resume.
5. **Term check** needs no AI and always runs. It flags any technology name in the tailored CV that never appears in your master resume.

Then the tailored `.tex` is compiled to PDF, if a LaTeX engine is available.

### Step 1: Get the code
```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

### Step 2: Create your master resume
```bash
cp resume/master.example.tex resume/master.tex       # Windows: copy resume\master.example.tex resume\master.tex
```
Replace the placeholder content with your real resume, or paste in your own LaTeX resume. Any pdflatex or xelatex template works.

Then mark the sections the AI is allowed to edit:
```latex
% TAILOR:BEGIN experience
\section{Experience}
...
% TAILOR:END
```
Everything outside the markers is never changed. Good candidates for markers are the summary or headline, skills, experience and projects. Keep your contact details and education outside them. Without any markers, the whole document body is tailored.

**Tips for good results:**
- Your master resume is the **only source of truth**. Put every skill, tool and achievement you'd ever want to show in it. The AI can emphasize and reorder, but it can't add anything.
- Keep the markers on their own lines, and keep each marked section's `\begin{...}` / `\end{...}` inside it.
- If your template uses custom `.cls`/`.sty` files or images, put them in `resume/` next to `master.tex`.

### Step 3: Choose an AI model
Create your private config file:
```bash
cp .env.example .env                                  # Windows: copy .env.example .env
```

**Cloud (recommended):** set your key in `.env`:
```
GEMINI_API_KEY=your-key-here
```
Free-tier keys work but are often rate-limited. The tailor retries automatically and falls back through several Gemini models (see [Troubleshooting](#troubleshooting)).

**Local (fully private):** install Ollama, then:
```bash
ollama pull qwen2.5:7b
ollama serve
```
Use a 7B or larger model; 3B models make a mess of LaTeX. On a laptop without a GPU, one run can take 30+ minutes.

### Step 4 (optional): PDF output
The tailor uses the first of these it finds:
1. **Local LaTeX:** `tectonic`, `latexmk`, `pdflatex` or `xelatex` on your PATH.
2. **Self-hosted Overleaf:** if Docker is running with the [Overleaf Toolkit](https://github.com/overleaf/toolkit) (`bin/up -d`), it compiles inside the `sharelatex` container. If your container has another name, set `OVERLEAF_CONTAINER`. If a package is missing, the report names it and shows the `tlmgr install` command.
3. **Neither:** you still get `resume.tex`, which you can upload to [overleaf.com](https://www.overleaf.com).

### Step 5: Run it
```bash
python scripts/resume_server.py
```
- **Job board with Tailor buttons:** http://localhost:8765. Click **✨ Tailor resume** on any job, or paste an external job URL or description into the panel at the top. This works for LinkedIn and other sites that block scrapers.
- **My CVs dashboard:** http://localhost:8765/cvs. It shows:
  - your **master resume**
  - every **tailored CV**, with match score, fact-check status, gaps, PDF preview, `.tex`, cover letter, report, a link to the job, and a delete button
  - your **earlier CVs** from a folder of your choice (`CV_ARCHIVE_DIR`, default `~/Desktop/CV`). Build any old `.tex` to PDF with one click. That folder is only read, never modified.

**Or use the command line:**
```bash
python scripts/tailor_resume.py --job karriere-10029847            # a job id from data/jobs.json
python scripts/tailor_resume.py --url https://company.com/jobs/123  # any job page
python scripts/tailor_resume.py --text-file posting.txt --provider cloud
```
Options: `--provider local|cloud|auto` (auto uses Ollama if it's running, otherwise Gemini), `--model`, `--resume`, `--no-cover-letter`, `--no-pdf`.

Each run is saved in `resume/output/<date>_<company>_<title>/`:

| File | Contents |
|---|---|
| `resume.tex` / `resume.pdf` | The tailored resume |
| `cover_letter.md` | The cover letter draft |
| `report.md` | Match score, matched skills, gaps, recommendations, keywords, fact-check results, warnings |
| `result.json` | The same data, machine-readable (the dashboard reads this) |

> **Always read the tailored CV before sending it.** The fact-checker and the term check catch most stretched claims, but you are responsible for what you submit.

---

## Configuration reference
All settings are optional environment variables, or lines in `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Enables cloud mode |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Preferred Gemini model |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.7-flash,gemini-3.5-flash,gemini-flash-latest,gemini-2.5-flash` | Models tried in order when the preferred one is overloaded, rate-limited or retired |
| `GEMINI_TIMEOUT` | `180` | Seconds per Gemini request |
| `TAILOR_OLLAMA_MODEL` | `$OLLAMA_MODEL` or `qwen2.5:7b` | Local model for tailoring |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama server |
| `TAILOR_TIMEOUT` | `1200` | Seconds per local model request |
| `RESUME_PATH` | `resume/master.tex` | Your master resume |
| `CV_ARCHIVE_DIR` | `~/Desktop/CV` | Folder of earlier CVs (`.tex`, `.pdf`, `.docx`) shown on the dashboard |
| `OVERLEAF_CONTAINER` | `sharelatex` | Docker container used for PDF compilation |
| `TAILOR_PORT` | `8765` | Local server port (or use `--port`) |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model the **scraper** uses for optional metadata tags |

To see which Gemini models your key can use:
```bash
curl -H "x-goog-api-key: $GEMINI_API_KEY" "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"
```

---

## Customize it for your needs

### A different country, city or language
| What | Where |
|---|---|
| Search URLs per job site (e.g. Karriere.at categories and cities) | The `fetch_*_jobs()` functions in `scripts/fetch_jobs.py` |
| "Is this a tech job?" keywords | `TECH_KEYWORDS` / `NON_TECH_TERMS` in `scripts/agent_classifier.py` |
| The English-only filter (rejects German postings) | `GERMAN_STRONG_INDICATORS`, `GERMAN_STOPWORDS` and `evaluate_language_purity()` in `scripts/agent_classifier.py`. Swap in your local language's words, or skip the check. |
| City, seniority and visa detection | `extract_metadata()` in `scripts/agent_classifier.py` |
| Filter dropdowns and category pills on the site | `index.html` (option values must match what `extract_metadata()` / `categorize_job()` produce) |
| Categories and technology tags | `categorize_job()` / `extract_tags()` in `scripts/fetch_jobs.py` |
| Titles and branding | `index.html`, `styles.css` (colors are CSS variables at the top) |
| Daily schedule | `cron` in `.github/workflows/daily-job-scraper.yml` (UTC) |

### Adding a job source
Write a `fetch_<site>_jobs()` function in `scripts/fetch_jobs.py` that returns a list of dicts in this shape, then add it to `main()`:
```python
{
    "id": "mysite-123",              # unique, prefixed with the source
    "title": "Backend Engineer",
    "company": "ACME GmbH",
    "company_logo": "",              # URL or empty
    "location": "Vienna",
    "category": categorize_job(title, description),
    "tags": extract_tags(title + " " + description),
    "description": "Short teaser…",
    "url": "https://mysite.com/jobs/123",
    "source": "MySite",
    "posted_at": "2026-09-30",
}
```
Pass each raw job through the shared classifier so it gets the same English/tech filter and metadata tags as the other sources:
```python
processed, reason = agent.process_job(raw_job, fetch_detail_if_needed=True)  # fetches the job page for the full text
if processed:            # None means rejected (not tech, or not in English); `reason` says why
    jobs.append(processed)
```
Jobs are de-duplicated by title plus company.

### Changing how the AI tailors
Everything is in `scripts/tailor_resume.py`:
- `TRUTH_RULES`: the honesty rules that every writing agent gets
- `agent_analyze`, `agent_tailor`, `agent_factcheck`, `agent_cover_letter`: one prompt each. Change the tone, the cover letter length or language, or what the analyst looks for.
- `check_latex()`: the structural checks every tailored section must pass
- `new_terms()`: the no-AI term check

To add another AI provider (OpenAI, Anthropic, etc.), add a client class to `scripts/llm_client.py` with `name`, `label`, `is_available()` and `generate(system, prompt, json_mode, temperature)`, then register it in `get_client()`.

---

## Privacy
- **Nothing personal is in the repo.** `.env`, `resume/*` (except the example template), `resume/output/` and `resume/archive_pdfs/` are all gitignored. Cloning or forking gives you the code and public job listings only.
- **Check before your first commit:** run `git status` and make sure `.env` and `resume/master.tex` don't appear.
- **API keys:** never paste a key into code, issues or chats. Google automatically disables keys it finds exposed publicly. If yours leaks, delete it in AI Studio and create a new one.
- **Cloud mode** sends the job text and the resume text to Google's Gemini API. Use local mode (Ollama) if that isn't acceptable.
- **The local server** only listens on `127.0.0.1`. It rejects requests with a foreign `Host` header and only accepts JSON POSTs, so other websites can't reach it. It serves only a fixed set of files: the dashboard, `data/*.json`, your generated output, your master resume and the CVs in `CV_ARCHIVE_DIR`. It never serves `.env` or any other file.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| No **Tailor resume** buttons | Open the board through `python scripts/resume_server.py` at `http://localhost:8765`, not GitHub Pages and not by double-clicking `index.html`. The buttons appear about a second after the page loads. |
| "All Gemini models are unavailable" / 503 / 429 | Google is overloaded, or your free-tier limit was reached. Wait a few minutes and try again. If the fact-check or cover letter fails, the CV is still saved and marked **fact-check unchecked**. |
| `HTTP 403 … API key was reported as leaked` | Create a new key and update `.env`. |
| `404 … model is no longer available` | Set `GEMINI_MODEL` to a current model (see the model-list command above). |
| A section says "kept unchanged: tailored LaTeX was invalid" | The model broke the LaTeX twice, so your original section was kept. Try again, or use a stronger model. |
| PDF: "No LaTeX engine found" | Install Tectonic or MiKTeX, or start Docker and your Overleaf Toolkit. |
| PDF: "missing LaTeX package(s)" | Run `docker exec sharelatex tlmgr install <package>`, or install it through MiKTeX's package manager. |
| Local mode times out | Your machine is too slow for that model. Use a smaller model, raise `TAILOR_TIMEOUT`, or use cloud mode. |
| Earlier CVs don't show up | Set `CV_ARCHIVE_DIR` to the folder containing your `.tex`/`.pdf`/`.docx` CVs (top level only). |
| Job page text is empty (JS-heavy sites, LinkedIn) | Paste the job description into the text box instead of the URL. |

---

## Project structure
```
index.html, app.js, styles.css     Job board (public). The tailor UI activates only on localhost.
cvs.html, cvs.js                   "My CVs" dashboard (local server only)
data/jobs.json                     Scraped jobs, updated daily by GitHub Actions
scripts/fetch_jobs.py              Scraper: one fetch_*_jobs() per source
scripts/agent_classifier.py        English/tech filter + metadata tags (optional Ollama enrichment)
scripts/tailor_resume.py           AI pipeline + CLI
scripts/llm_client.py              Gemini / Ollama clients with retry and fallback
scripts/resume_server.py           Local server: static files + tailor and CV APIs
scripts/cv_library.py              Lists tailored/earlier CVs, builds PDFs
resume/master.example.tex          Resume template with TAILOR markers (your real files in resume/ stay local)
.env.example                       Config template. Copy to .env.
.github/workflows/daily-job-scraper.yml   Daily scrape and commit
```

### Optional: local AI tags for the scraper
The English-only filter is always rule-based. In testing, small LLMs mislabeled genuine English postings, so no LLM can drop a job. If Ollama is running when you run `python scripts/fetch_jobs.py` locally, it adds seniority, visa, experience and city tags to jobs that already passed the filter (`ollama pull llama3.2:3b`; override with `OLLAMA_MODEL` / `OLLAMA_URL`). In GitHub Actions, it falls back to keyword rules automatically.
