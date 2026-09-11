# 🇦🇹 Austria Tech Jobs Hub — Progress & Next Plans

## 📌 Project Overview
An automated daily job aggregator and live web dashboard designed specifically for **English-speaking tech professionals and students in Austria**. It automatically scrapes, filters, categorizes, and publishes 100% English-written tech job listings every morning at **08:00 AM Vienna time**.

---

## ⚡ 1. Completed Progress

### 🛠 Scraper & Engine (`scripts/fetch_jobs.py`)
- [x] **Multi-Platform Scraping**: Aggregates live listings from **Karriere.at** (Austria's #1 portal), **Remotive**, **Jobicy**, and **Arbeitnow / Indeed Partner Networks**.
- [x] **Bulletproof English Language Filter**:
  - Scans raw titles and body text for German title nouns (`Entwickler`, `Mitarbeiter`, `Buchhalter`, `Planer`, `Berater`, `Projektleiter`, etc.) and German body vocabulary (`und`, `mit`, `für`, `deine aufgaben`, `ihre aufgaben`).
  - **Rejects German-written postings** so only postings originally written in English by employers are kept.
- [x] **Tech Domain Scoping**: Restricts collection strictly to IT, Software Engineering, Data & AI, Frontend, Backend, DevOps, and Cloud roles.
- [x] **Austria-Wide Location Coverage**: Scrapes roles across Vienna/Wien, Graz, Linz, Salzburg, Innsbruck, Klagenfurt, and Austria-eligible Remote positions.
- [x] **Deduplication**: Automatically removes duplicate postings across multiple portals using title and company keys.

### 🌐 Web Dashboard (`index.html`, `styles.css`, `app.js`)
- [x] **Live Interactive UI**: Dark-themed, responsive dashboard displaying job cards with company logos, titles, locations, category badges, tags, and direct application links.
- [x] **Real-Time Search**: Instant search filtering by keywords, technologies, titles, or company names.
- [x] **Category Filter Pills**: Filter by *All Roles*, *Data & AI*, *Software Engineering*, *Backend*, *Frontend*, and *DevOps & Cloud*.
- [x] **City / Region Filter**: Dropdown allowing users to isolate jobs by specific Austrian city (*Vienna, Graz, Linz, Salzburg, Innsbruck, Klagenfurt, Remote*).
- [x] **Cache-Busting Integration**: Added dynamic query parameters (`data/jobs.json?v=timestamp`) so visitors always receive fresh data without browser caching issues.

### ⏰ Automation & Hosting
- [x] **GitHub Actions Workflow** (`.github/workflows/daily-job-scraper.yml`):
  - Scheduled via `cron: '0 6 * * *'` (08:00 AM Vienna time).
  - Automatically runs the scraper in the cloud, updates `data/jobs.json`, and commits updates to GitHub.
- [x] **GitHub Pages Hosting**: Fully deployed and publicly live at:
  👉 **[https://ibrahimraafat.github.io/austria-tech-jobs-hub/](https://ibrahimraafat.github.io/austria-tech-jobs-hub/)**

---

## 🎯 2. Next Plans & Roadmap

### 🏷️ Feature 1: Rich Post Labels & Metadata Badges
Upgrade the scraper parser and job card UI to extract and display the following labels on every job post:

1. **Relocation Support**:
   - Label: `✈️ Supports Relocation`
   - Detects phrases like *relocation support*, *relocation package*, *visa & relocation assistance*.
2. **Work Permit / Visa Status**:
   - Label: `🛂 Visa Sponsorship / EU Work Permit` or `🇪🇺 EU Citizens / Valid Permit Only`
   - Scans description text for visa sponsorship availability or work permit restrictions.
3. **Seniority Level**:
   - Labels: `🐣 Junior` | `💻 Mid-Level` | `🚀 Senior` | `👑 Lead / Principal` | `🎓 Internship / Working Student`
   - Classifies jobs based on title and description keywords (e.g. *Junior*, *Senior*, *Internship*, *Werkstudent*, *Lead*).
4. **Years of Experience Required**:
   - Labels: `0-2 Years` | `3-5 Years` | `5+ Years`
   - Uses regex extraction to detect experience requirements (e.g. *3+ years of experience*, *5 years in Python*).
5. **Internship / Working Student Specific Filter**:
   - Add a dedicated category pill / toggle for **Internships & Student Jobs (20-25 h/week)**.

### 💡 Feature 2: Austrian Salary Transparency
- **Austrian Minimum Salary Disclosure**:
  - Austrian law requires job postings to state a minimum gross salary (e.g. *Gross salary EUR 2,619.73 / month*).
  - Extract salary numbers from job descriptions and display them as a clear `💰 Salary Range` badge on cards.

### 🔖 Feature 3: Bookmarks & Saved Jobs
- Add a "⭐ Save Job" button on cards so users can bookmark roles locally in `localStorage` and view a "Saved Jobs" tab.

### 🔔 Feature 4: Daily Email / Telegram Job Alerts
- Add an automated daily email or Telegram notification bot that sends new English Tech jobs posted that morning directly to your inbox/chat.

---

## 📊 Summary Status
| Feature | Status |
| :--- | :--- |
| English Tech Scraper | ✅ Completed |
| Karriere / Indeed / Stepstone Networks | ✅ Completed |
| 8:00 AM Daily GitHub Automation | ✅ Completed |
| Live GitHub Pages Website | ✅ Completed |
| City / Region Filters | ✅ Completed |
| Rich Job Labels (Seniority, Visa, Relocation, YOE) | ⏳ Planned Next |
| Austrian Minimum Salary Extraction | ⏳ Planned Next |
