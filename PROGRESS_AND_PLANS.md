# 🇦🇹 Austria Tech Jobs Hub — Progress & Next Plans

## 📌 Project Overview
An automated daily job aggregator and live web dashboard designed specifically for **English-speaking tech professionals and students in Austria**. It automatically scrapes, filters, categorizes, and publishes 100% English-written tech job listings every morning at **08:00 AM Vienna time**.

---

## ⚡ 1. Completed Progress

### 🤖 Custom Local Agent Job Classifier (`scripts/agent_classifier.py` & `scripts/fetch_jobs.py`)
- [x] **Full Job Body Inspection**:
  - Automatically fetches the full HTML page of candidate listings (especially Karriere.at detail pages `/jobs/<id>`) instead of relying solely on titles or search teasers.
- [x] **Multi-Layer English Purity Filter**:
  - Scans full page text for German section headers (`deine aufgaben`, `ihre aufgaben`, `dein profil`, `ihr profil`, `wir bieten`, `über uns`, `gehalt`, `kollektivvertrag`, `überzahlung`, `bewerbung`, `deutschkenntnisse`, etc.).
  - Performs statistical word tokenization and stopword analysis (`du`, `wir`, `mit`, `für`, `die`, `der`, `das`, `sowie`, `dienstort`, `vollzeit`, `ausbildung`, etc.).
  - Automatically rejects any job post containing German section headers or exceeding German stopword density thresholds.
  - **Empirically Tested & Audited**: Flagged URLs (`10030545` and `10029024`) are now 100% caught and rejected by the agent classifier!

### 🏷️ Rich Post Labels & Metadata Badges
- [x] **Seniority Level Classification**:
  - Classifies listings into `Junior`, `Mid-Level`, `Senior`, `Lead / Manager`, or `Internship / Student`.
- [x] **Relocation & Visa Support Tracking**:
  - Detects `Relocation Supported`, `Visa Sponsorship`, or `EU Work Permit Required`.
- [x] **Experience Level Tagging**:
  - Extracts years of experience (e.g. `0-2 years exp`, `3-5 years exp`, `5+ years exp`).
- [x] **City Normalization**:
  - Categorizes postings into `Vienna`, `Graz`, `Linz`, `Salzburg`, `Innsbruck`, `Carinthia`, `Remote`, or `Austria`.

### 🌐 Web Dashboard UI (`index.html`, `styles.css`, `app.js`)
- [x] **Interactive Multi-Filter Bar**:
  - Filters for **City / Region**, **Seniority Level**, and **Relocation / Visa Status**.
- [x] **Visual Metadata Badges**:
  - Job cards present color-coded badges for Seniority (`🎓 Senior`), Experience (`⏳ 5+ years exp`), and Relocation/Visa (`✈️ Relocation Supported` / `Visa Sponsorship`).
- [x] **Cache-Busting Integration**: `data/jobs.json?v=timestamp` ensures fresh data on every visit.

### ⏰ Automation & Deployment
- [x] **Daily GitHub Actions Workflow** (`.github/workflows/daily-job-scraper.yml`): Runs daily at 08:00 AM Vienna time (06:00 UTC).
- [x] **Live GitHub Pages Site**:
  👉 **[https://ibrahimraafat.github.io/austria-tech-jobs-hub/](https://ibrahimraafat.github.io/austria-tech-jobs-hub/)**

---

## 🎯 2. Next Plans & Roadmap

### ✅ Feature 1: Austrian Salary Transparency (done)
- `scripts/salary.py` parses the legally required gross salary from each job's detail page and normalises it to gross/year (monthly × 14 for EUR). Tests: `python -m unittest tests/test_salary.py`.
- Cards show a `💰` badge; the board has a salary filter (€40k+ … €80k+) and a "Highest Salary" sort.

### ✅ Feature 2: Saved Jobs & Application Tracker (done)
- ☆ on each card saves a job; a status dropdown tracks it through Saved → Applied → Interview → Offer / Rejected.
- "My Jobs" filter with per-status counts. Stored in `localStorage` with a snapshot of each job, so tracked jobs stay visible after the posting expires.
- On the local server, cards with a tailored CV show a `📄 Tailored CV · NN%` badge linking to My CVs.

### ✅ Data quality pass (`scripts/enrich.py`, done)
- Visits every job's detail page once: drops expired postings (HTTP 404/410, unless most of a source fails, which suggests blocking), reads schema.org JobPosting JSON-LD for salary/location, and replaces template descriptions with the posting's own summary.
- `cities` (multi-valued, from the location field) replaces the old text-guessed `city`, which mislabelled most Vienna jobs.

### ✅ Feature 3: Job Alerts (Telegram, done)
- `scripts/send_alerts.py` runs after the daily scrape and messages jobs that are new since the previous run, filtered by the `ALERT_FILTERS` repo variable. Setup: README → "Daily Telegram alerts". Email is still open.

### ✅ Feature 4: Master Thesis Opportunities in Austria (`theses.html`, done)
- Dedicated portal (`theses.html` & `theses.js`) aggregating funded Master's thesis positions across Austrian research centres, universities, and industry R&D labs.
- **8 Active Sources Aggregated (56 live opportunities)**:
  - **TU Wien (Faculty of Informatics & ACIN/Telecommunications)**: Visual computing, 3D/NeRF, LLM DSL synthesis, Robotic Systems Lab (RSL), complex dynamical control (29 topics).
  - **AIT Austrian Institute of Technology**: 5G/6G wireless, SDR, bi-static drone sensing, physical AI world models, biosensors (6 topics).
  - **Infineon Technologies Austria (Villach, Graz, Vienna)**: Battery modeling, GaN HEMTs, AI failure root-cause analysis, analog chip test coverage (5 topics).
  - **SBA Research (Vienna)**: Hardware Trojan detection, web application fuzzing, privacy-preserving ML, digital identity cryptography, RISC-V IoT firmware (5 topics).
  - **TU Graz (ISDS / HCC & ISEC)**: CPU microarchitectural side-channels, federated learning, explainable AI, post-quantum zero-knowledge proofs (4 topics).
  - **JOANNEUM RESEARCH (Graz / Weiz / Klagenfurt)**: Satellite AI navigation, industrial robot-human workcells, connected vehicle sensor fusion (3 topics).
  - **Dynatrace Research Lab (Linz / Vienna)**: LLM cloud observability, distributed tracing causality graphs, JKU LIT lab run-time profiling (3 topics).
  - **Silicon Austria Labs (SAL - Villach, Graz, Linz)**: Brillouin-active photonic integrated circuits (PICs), optical waveguiding, sensor systems (1 topic).
- Rich data extraction: parses research groups, durations (e.g. 6 months), weekly workload (e.g. 20h/week), collective agreement stipends (e.g. €1,379.60/month, €1,500–€2,000/month at Infineon, €1,000 TU Wien stipends), research field categorization, technical tags, and language (English / German).
- Custom **Thesis Tracker** in `localStorage`: tracks applications from *Saved* → *Contacted Supervisor* → *Interview* → *Offered* / *Declined*.
- Scraper: `scripts/fetch_theses.py` with 48 unit tests in `tests/test_fetch_theses.py`.

### ✅ Reliability & Security Hardening (done)
- `first_seen` per job (🆕 badge, "Newest" sort), smarter cross-source dedupe, per-source counts with warnings when a source drops to 0, one crashing source no longer kills the run, unit tests run in CI before scraping.
- Scraped text is HTML-escaped and links restricted to http(s) on the board (prevents XSS vulnerabilities across the localhost resume server).

---

## 🚀 3. Next Roadmap: Personalized & Turnkey Career Hub (Planned)
*Complete architectural plan documented in [`personalized_hub_plan.md`](./personalized_hub_plan.md).*

### 📋 Milestone 1: Unified Profile Schema & Setup Wizard
- Centralize all user preferences into `config/profile.json` (skills, target roles, preferred Austrian cities, minimum salary, thesis topics, notification channels).
- Interactive setup script: `python scripts/configure.py` (interviews the user and auto-extracts skills from their master resume).

### 📋 Milestone 2: Automated Match Scoring & "🎯 For You" Feed
- Fast deterministic rule engine (`scripts/match_scorer.py`) evaluating skill overlap, seniority alignment, and location fit.
- Computes `0–100% Match Scores` with visual breakdowns (`🎯 92% Match: Matched Python, Docker · Gap: Kubernetes`).
- Adds a "🎯 For You" tab on both Jobs and Master Theses dashboards.

### 📋 Milestone 3: Executive Daily Briefing & Multichannel Alerts
- AI-generated morning digest (3 concise highlights delivered to phone every morning at 08:00 AM).
- Support for **Discord Webhooks** (zero-bot setup, rich embed cards) alongside Telegram.

### 📋 Milestone 4: Portable Application Tracker (Cross-Device Sync)
- Export / Import tracker backup (JSON & CSV).
- Optional lightweight cloud sync (GitHub Private Gist or Supabase) syncing phone browsers with local desktop.

### 📋 Milestone 5: 1-Click Fork Template
- GitHub *"Use this template"* button with automated onboarding Action issue.

---

## 📊 Summary Status
| Feature | Status |
| :--- | :--- |
| English Tech Scraper (14 job sources) | ✅ Completed |
| Master Theses Portal & Scraper (8 institutions, 56 topics) | ✅ Completed |
| Full HTML Body Agent Classifier & Purity Filter | ✅ Completed |
| City / Seniority / Visa / Salary Filters | ✅ Completed |
| Rich Badges (Seniority, Visa, Relocation, Exp, Stipends) | ✅ Completed |
| Daily 08:00 AM GitHub Action Automation | ✅ Completed |
| Telegram Daily New-Job Alerts | ✅ Completed |
| Saved Jobs & Thesis Application Trackers | ✅ Completed |
| AI Resume Tailor (local Ollama / Gemini, LaTeX, PDF) | ✅ Completed |
| Full Test Suite (48 unit tests) | ✅ Passing |
| Personalized Career Hub & Setup Wizard | 📋 Planned (Milestones 1–5) |
