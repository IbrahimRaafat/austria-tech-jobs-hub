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
