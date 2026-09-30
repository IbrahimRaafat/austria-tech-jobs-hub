let allJobs = [];
let activeCategory = 'All';
let searchQuery = '';
let activeLocation = 'All';
let activeSeniority = 'All';
let activeRelocation = 'All';
let tailorEnabled = false;

document.addEventListener('DOMContentLoaded', () => {
    loadJobs();
    setupEventListeners();
    initTailor();
});

async function loadJobs() {
    try {
        const response = await fetch('./data/jobs.json?v=' + Date.now());
        const data = await response.json();
        allJobs = data.jobs || [];
        
        if (data.updated_at) {
            const dt = new Date(data.updated_at);
            document.getElementById('last-updated').textContent = `Updated: ${dt.toLocaleDateString()} at ${dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
        }
        
        document.getElementById('count-all').textContent = allJobs.length;
        renderJobs();
    } catch (err) {
        console.error('Error loading jobs:', err);
        document.getElementById('jobs-container').innerHTML = `<p style="color: #ef4444;">Failed to load job listings. Please check back soon.</p>`;
    }
}

function setupEventListeners() {
    document.getElementById('search-input').addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase().trim();
        renderJobs();
    });

    document.getElementById('location-filter').addEventListener('change', (e) => {
        activeLocation = e.target.value;
        renderJobs();
    });

    document.getElementById('seniority-filter').addEventListener('change', (e) => {
        activeSeniority = e.target.value;
        renderJobs();
    });

    document.getElementById('relocation-filter').addEventListener('change', (e) => {
        activeRelocation = e.target.value;
        renderJobs();
    });

    document.getElementById('category-pills').addEventListener('click', (e) => {
        const target = e.target.closest('.pill');
        if (!target) return;
        
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        target.classList.add('active');
        
        activeCategory = target.dataset.category;
        renderJobs();
    });
}

function renderJobs() {
    const container = document.getElementById('jobs-container');
    const filtered = allJobs.filter(job => {
        if (activeCategory !== 'All' && job.category !== activeCategory) {
            return false;
        }

        if (activeSeniority !== 'All' && job.seniority !== activeSeniority) {
            return false;
        }

        if (activeRelocation !== 'All' && job.relocation_support !== activeRelocation) {
            return false;
        }

        if (activeLocation !== 'All') {
            const jobLoc = (job.location || '').toLowerCase();
            const jobCity = (job.city || '').toLowerCase();
            const filterLoc = activeLocation.toLowerCase();
            
            if (filterLoc === 'vienna') {
                if (!jobLoc.includes('vienna') && !jobLoc.includes('wien') && !jobCity.includes('vienna')) return false;
            } else if (filterLoc === 'remote') {
                if (!jobLoc.includes('remote') && !jobCity.includes('remote')) return false;
            } else {
                if (!jobLoc.includes(filterLoc) && !jobCity.includes(filterLoc)) return false;
            }
        }

        if (searchQuery) {
            const text = (
                job.title + ' ' +
                job.company + ' ' +
                job.location + ' ' +
                (job.seniority || '') + ' ' +
                (job.relocation_support || '') + ' ' +
                (job.tags || []).join(' ') + ' ' +
                job.description
            ).toLowerCase();
            if (!text.includes(searchQuery)) {
                return false;
            }
        }

        return true;
    });

    document.getElementById('jobs-count-title').textContent = `${filtered.length} Tech Jobs Found`;

    if (filtered.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 48px; color: var(--text-secondary);">
                <h3>No matching jobs found</h3>
                <p>Try broadening your search criteria or resetting city/seniority filters.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(job => createJobCardHTML(job)).join('');
}

function createJobCardHTML(job) {
    const logoHTML = job.company_logo 
        ? `<img class="company-logo" src="${job.company_logo}" alt="${job.company}" onerror="this.onerror=null; this.outerHTML='<div class=\\'company-logo\\'>${job.company ? job.company[0] : 'T'}</div>';">`
        : `<div class="company-logo">${job.company ? job.company[0] : 'T'}</div>`;

    const tagsHTML = (job.tags || []).map(tag => `<span class="tag">${tag}</span>`).join('');

    const seniorityBadge = job.seniority 
        ? `<span class="meta-badge seniority-badge">${job.seniority}</span>` 
        : '';
        
    const relocationBadge = (job.relocation_support && job.relocation_support !== 'Not Specified')
        ? `<span class="meta-badge relocation-badge">✈️ ${job.relocation_support}</span>` 
        : '';

    const expBadge = job.experience_level
        ? `<span class="meta-badge exp-badge">⏳ ${job.experience_level}</span>`
        : '';

    return `
        <div class="job-card">
            <div>
                <div class="card-top">
                    ${logoHTML}
                    <div class="job-meta">
                        <h3 class="job-title">${job.title}</h3>
                        <div class="company-name">${job.company}</div>
                    </div>
                </div>

                <div class="badges-row">
                    ${seniorityBadge}
                    ${expBadge}
                    ${relocationBadge}
                </div>

                <div class="details-row">
                    <span class="detail-item">📍 ${job.location}</span>
                    <span class="detail-item">📂 ${job.category}</span>
                </div>

                ${tagsHTML ? `<div class="tags-row">${tagsHTML}</div>` : ''}

                <p class="description-text">${job.description}</p>
            </div>

            <div class="card-bottom">
                <span class="source-badge">via ${job.source}</span>
                ${tailorEnabled ? `<button type="button" class="tailor-btn" data-job-id="${escapeHTML(job.id)}">✨ Tailor resume</button>` : ''}
                <a href="${job.url}" target="_blank" rel="noopener noreferrer" class="apply-btn">Apply Now ↗</a>
            </div>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// AI Resume Tailor (only active when served by scripts/resume_server.py)
// ---------------------------------------------------------------------------

const STEP_ICONS = { pending: '○', running: '◌', done: '●', skipped: '–', error: '✕' };

function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function initTailor() {
    if (!['localhost', '127.0.0.1'].includes(location.hostname)) return;
    let status;
    try {
        const response = await fetch('/api/tailor/status', { cache: 'no-store' });
        if (!response.ok) return;
        status = await response.json();
    } catch {
        return; // static hosting (GitHub Pages) - feature stays hidden
    }

    tailorEnabled = true;
    document.getElementById('tailor-panel').hidden = false;
    document.getElementById('nav-links').hidden = false;

    const select = document.getElementById('tailor-provider');
    const { local, cloud } = status.providers;
    select.innerHTML = `
        <option value="auto">Auto (local first)</option>
        <option value="local" ${local.available ? '' : 'disabled'}>Local · ${escapeHTML(local.label)}${local.available ? '' : ' (not running)'}</option>
        <option value="cloud" ${cloud.available ? '' : 'disabled'}>Cloud · ${escapeHTML(cloud.label)}${cloud.available ? '' : ' (no API key)'}</option>`;
    let saved = null;
    try { saved = localStorage.getItem('tailorProvider'); } catch {}
    if (saved && !select.querySelector(`option[value="${saved}"]`)?.disabled) select.value = saved;
    select.addEventListener('change', () => {
        try { localStorage.setItem('tailorProvider', select.value); } catch {}
    });

    const alerts = [];
    if (!status.resume_found) alerts.push(`No master resume found at <code>${escapeHTML(status.resume_path)}</code>. Copy <code>resume/master.example.tex</code> there and fill it in.`);
    if (!local.available && !cloud.available) alerts.push('No model available: start Ollama (<code>ollama serve</code>) or set <code>GEMINI_API_KEY</code> in <code>.env</code>, then restart the server.');
    if (!status.latex_engine) alerts.push('No LaTeX engine found, so you will get <code>.tex</code> only. Start your Overleaf toolkit (<code>bin/up -d</code>) or install Tectonic/MiKTeX for PDFs, then reload.');
    const alertEl = document.getElementById('tailor-alert');
    alertEl.innerHTML = alerts.join('<br>');
    alertEl.hidden = alerts.length === 0;

    document.getElementById('tailor-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const url = document.getElementById('tailor-url').value.trim();
        const text = document.getElementById('tailor-text').value.trim();
        if (!url && !text) return;
        startTailor({ url, text }, 'External job');
    });

    document.getElementById('jobs-container').addEventListener('click', (e) => {
        const btn = e.target.closest('.tailor-btn');
        if (!btn) return;
        const job = allJobs.find(j => j.id === btn.dataset.jobId);
        startTailor({ job_id: btn.dataset.jobId }, job ? `${job.title} · ${job.company}` : 'Job');
    });

    const modal = document.getElementById('tailor-modal');
    document.getElementById('tailor-close').addEventListener('click', () => { modal.hidden = true; });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.hidden = true; });

    renderJobs(); // re-render cards with the Tailor button
}

async function startTailor(params, title) {
    const modal = document.getElementById('tailor-modal');
    const body = document.getElementById('tailor-modal-body');
    document.getElementById('tailor-modal-title').textContent = title;
    body.innerHTML = '<p class="tailor-hint">Starting…</p>';
    modal.hidden = false;

    try {
        const response = await fetch('/api/tailor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...params, provider: document.getElementById('tailor-provider').value }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || response.statusText);
        pollTailorTask(data.task_id);
    } catch (err) {
        body.innerHTML = `<p class="tailor-error">${escapeHTML(err.message)}</p>`;
    }
}

async function pollTailorTask(taskId) {
    const body = document.getElementById('tailor-modal-body');
    let task;
    try {
        task = await (await fetch(`/api/tailor/tasks/${taskId}`, { cache: 'no-store' })).json();
    } catch (err) {
        body.innerHTML = `<p class="tailor-error">Lost connection to the local server: ${escapeHTML(err.message)}</p>`;
        return;
    }

    const stepsHTML = Object.entries(task.steps).map(([key, step]) => `
        <li class="step step-${step.status}">
            <span class="step-icon">${STEP_ICONS[step.status] || '○'}</span>
            <span>${escapeHTML(task.step_labels[key])}</span>
            ${step.detail ? `<span class="step-detail">${escapeHTML(step.detail)}</span>` : ''}
        </li>`).join('');

    body.innerHTML = `<ul class="tailor-steps">${stepsHTML}</ul>`
        + (task.status === 'error' ? `<p class="tailor-error">${escapeHTML(task.error)}</p>` : '')
        + (task.status === 'done' ? renderTailorResult(task.result) : '');

    if (task.status === 'running') setTimeout(() => pollTailorTask(taskId), 1500);
}

function renderTailorResult(result) {
    const a = result.analysis;
    const fc = result.factcheck;
    const list = (items) => items.length ? `<ul>${items.map(i => `<li>${escapeHTML(i)}</li>`).join('')}</ul>` : '<p class="tailor-hint">None</p>';
    const scoreClass = a.match_score >= 70 ? 'good' : a.match_score >= 45 ? 'ok' : 'low';
    const f = result.files;
    const links = [
        f.resume_pdf && `<a class="apply-btn" href="${f.resume_pdf}" target="_blank">Resume PDF ↗</a>`,
        `<a class="tailor-link" href="${f.resume_tex}?download=1">resume.tex ⤓</a>`,
        f.cover_letter && `<a class="tailor-link" href="${f.cover_letter}" target="_blank">Cover letter ↗</a>`,
        `<a class="tailor-link" href="${f.report}" target="_blank">Full report ↗</a>`,
    ].filter(Boolean).join('');

    const issues = fc.issues.length
        ? `<ul>${fc.issues.map(i => `<li><span class="sev sev-${escapeHTML(i.severity)}">${escapeHTML(i.severity)}</span> ${escapeHTML(i.claim)} — ${escapeHTML(i.problem || '')}</li>`).join('')}</ul>`
        : '<p class="tailor-hint">No unsupported claims found.</p>';

    return `
        <div class="tailor-result">
            <div class="score-row">
                <div class="score score-${scoreClass}">${a.match_score}<small>/100</small></div>
                <p>${escapeHTML(a.summary)}</p>
            </div>
            <div class="tailor-links">${links}</div>
            <div class="tailor-cols">
                <div><h3>Matched</h3>${list(a.matched)}</div>
                <div><h3>Gaps</h3>${list(a.gaps)}</div>
            </div>
            <h3>Fact-check: <span class="verdict verdict-${fc.verdict}">${fc.verdict.toUpperCase()}</span>${fc.revised ? ' <span class="tailor-hint">(after one revision)</span>' : ''}</h3>
            ${issues}
            ${result.warnings.length ? `<h3>Warnings</h3>${list(result.warnings)}` : ''}
            <p class="tailor-hint">${escapeHTML(result.model)} · PDF: ${escapeHTML(result.pdf)} · saved to <code>${escapeHTML(result.output_dir)}</code> · <a href="/cvs">All my CVs →</a></p>
        </div>`;
}
