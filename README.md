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
