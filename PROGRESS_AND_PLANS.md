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

### 💡 Feature 1: Austrian Salary Transparency
- **Austrian Minimum Salary Extraction**:
  - Austrian job postings legally must state a minimum gross salary (e.g. *EUR 2,619.73 gross / month*).
  - Extract salary numbers and display them as a clear `💰 Salary Range` badge on each card.

### 🔖 Feature 2: Bookmarks & Saved Jobs
- Add a "⭐ Save Job" button on cards to allow users to bookmark positions in `localStorage`.

### 🔔 Feature 3: Job Alerts (Telegram / Email)
- Automated daily summary alert sent to Telegram/Email for newly scraped English tech roles in Austria.

---

## 📊 Summary Status
| Feature | Status |
| :--- | :--- |
| English Tech Scraper | ✅ Completed |
| Full HTML Body Agent Classifier | ✅ Completed |
| 100% English Language Purity Filter | ✅ Completed |
| City / Seniority / Visa Filters | ✅ Completed |
| Rich Badges (Seniority, Visa, Relocation, Exp) | ✅ Completed |
| 8:00 AM Daily GitHub Automation | ✅ Completed |
| Live GitHub Pages Website | ✅ Completed |
| Austrian Minimum Salary Extraction | ⏳ Planned Next |
| Bookmarks & Saved Jobs | ⏳ Planned Next |
