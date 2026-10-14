// Master Theses Dashboard - Austria Tech Jobs Hub

let allTheses = [];
let selectedCategory = 'All';
let selectedCity = 'All';
let selectedPaid = 'All';
let selectedLang = 'All';
let selectedSort = 'default';
let searchQuery = '';
let trackerOnly = false;
let trackerStatus = 'all';
let tailorEnabled = false;

const TRACKER_KEY = 'tracked_theses_v1';
const STATUS_OPTIONS = [
    { value: 'saved', label: 'Saved' },
    { value: 'contacted', label: 'Contacted Supervisor' },
    { value: 'interview', label: 'Interview' },
    { value: 'offer', label: 'Offer Received' },
    { value: 'declined', label: 'Declined' }
];

function loadTracker() {
    try {
        return JSON.parse(localStorage.getItem(TRACKER_KEY) || '{}');
    } catch {
        return {};
    }
}

function saveTracker(tracker) {
    try {
        localStorage.setItem(TRACKER_KEY, JSON.stringify(tracker));
    } catch {}
}

function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function safeURL(url) {
    return /^https?:\/\//i.test(String(url ?? '').trim()) ? String(url).trim() : '';
}

function daysSince(isoDate) {
    if (!isoDate) return 999;
    const [y, m, d] = isoDate.split('-').map(Number);
    const then = new Date(y, m - 1, d);
    const now = new Date();
    return Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - then) / 86400000);
}

function isNewThesis(thesis) {
    return Boolean(thesis.first_seen) && daysSince(thesis.first_seen) <= 1;
}

document.addEventListener('DOMContentLoaded', () => {
    initTheses();
    initFilters();
    initTailor();

    document.addEventListener('error', (e) => {
        if (e.target && e.target.matches && e.target.matches('img.company-logo')) {
            const initial = e.target.dataset.initial || 'AUT';
            const fallback = document.createElement('div');
            fallback.className = 'company-logo';
            fallback.textContent = initial;
            e.target.replaceWith(fallback);
        }
    }, true);
});

async function initTheses() {
    const container = document.getElementById('theses-container');
    container.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Loading Master Thesis opportunities...</p></div>`;

    try {
        const res = await fetch(`data/theses.json?v=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        allTheses = data.theses || [];

        if (data.updated_at) {
            const dt = new Date(data.updated_at);
            document.getElementById('last-updated').textContent = `Updated ${dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`;
        }

        populateCityDropdown();
        renderTheses();
        updateCategoryCounts();
        updateTrackerCounts();
    } catch (e) {
        container.innerHTML = `
            <div class="empty-state">
                <p>Could not load thesis opportunities (${escapeHTML(e.message)}).</p>
            </div>`;
    }
}

function populateCityDropdown() {
    const select = document.getElementById('city-filter');
    const cities = new Set();
    allTheses.forEach(t => { if (t.location) cities.add(t.location); });
    const sorted = Array.from(cities).sort();
    sorted.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        select.appendChild(opt);
    });
}

function updateCategoryCounts() {
    document.getElementById('count-all').textContent = allTheses.length;
}

function updateTrackerCounts() {
    const tracker = loadTracker();
    const count = Object.keys(tracker).length;
    document.getElementById('tracker-count').textContent = count;

    let counts = { all: count, saved: 0, contacted: 0, interview: 0, offer: 0, declined: 0 };
    Object.values(tracker).forEach(t => {
        if (counts[t.status] !== undefined) counts[t.status]++;
    });

    for (const [st, num] of Object.entries(counts)) {
        const el = document.getElementById(`cnt-st-${st}`);
        if (el) el.textContent = num;
    }
}

function initFilters() {
    // Search
    const searchInput = document.getElementById('search-input');
    let debounce;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            searchQuery = searchInput.value.trim().toLowerCase();
            renderTheses();
        }, 150);
    });

    // Category pills
    document.getElementById('category-pills').addEventListener('click', (e) => {
        const pill = e.target.closest('.pill');
        if (!pill) return;
        document.querySelectorAll('#category-pills .pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        selectedCategory = pill.dataset.category;
        renderTheses();
    });

    // Dropdowns
    document.getElementById('city-filter').addEventListener('change', (e) => {
        selectedCity = e.target.value;
        renderTheses();
    });

    document.getElementById('paid-filter').addEventListener('change', (e) => {
        selectedPaid = e.target.value;
        renderTheses();
    });

    document.getElementById('lang-filter').addEventListener('change', (e) => {
        selectedLang = e.target.value;
        renderTheses();
    });

    document.getElementById('sort-select').addEventListener('change', (e) => {
        selectedSort = e.target.value;
        renderTheses();
    });

    // Tracker toggle
    const trackerBtn = document.getElementById('my-theses-toggle');
    const trackerBar = document.getElementById('tracker-bar');
    trackerBtn.addEventListener('click', () => {
        trackerOnly = !trackerOnly;
        trackerBtn.classList.toggle('active', trackerOnly);
        trackerBar.hidden = !trackerOnly;
        renderTheses();
    });

    // Tracker sub-status pills
    document.getElementById('tracker-status-pills').addEventListener('click', (e) => {
        const pill = e.target.closest('.pill');
        if (!pill) return;
        document.querySelectorAll('#tracker-status-pills .pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        trackerStatus = pill.dataset.status;
        renderTheses();
    });

    // Delegated actions on thesis cards (bookmark, tracker status, tag click)
    const container = document.getElementById('theses-container');
    container.addEventListener('click', (e) => {
        const saveBtn = e.target.closest('.save-btn');
        if (saveBtn) {
            toggleTrackThesis(saveBtn.dataset.thesisId);
            return;
        }

        const tag = e.target.closest('.tag');
        if (tag) {
            searchInput.value = tag.textContent.trim();
            searchQuery = searchInput.value.toLowerCase();
            renderTheses();
            searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        const tailorBtn = e.target.closest('.tailor-btn');
        if (tailorBtn) {
            openTailorModal(tailorBtn.dataset.thesisId);
            return;
        }
    });

    container.addEventListener('change', (e) => {
        const select = e.target.closest('.track-status-select');
        if (select) {
            updateThesisStatus(select.dataset.thesisId, select.value);
        }
    });
}

function toggleTrackThesis(id) {
    const tracker = loadTracker();
    if (tracker[id]) {
        delete tracker[id];
    } else {
        const thesis = allTheses.find(t => t.id === id);
        tracker[id] = {
            id,
            status: 'saved',
            saved_at: new Date().toISOString(),
            snapshot: thesis || null
        };
    }
    saveTracker(tracker);
    updateTrackerCounts();
    renderTheses();
}

function updateThesisStatus(id, newStatus) {
    const tracker = loadTracker();
    if (!tracker[id]) return;
    tracker[id].status = newStatus;
    tracker[id].updated_at = new Date().toISOString();
    saveTracker(tracker);
    updateTrackerCounts();
    renderTheses();
}

function renderTheses() {
    const container = document.getElementById('theses-container');
    const tracker = loadTracker();

    let list = allTheses.slice();

    // If tracker view is enabled, also include any archived tracked theses not in allTheses
    if (trackerOnly) {
        const presentIds = new Set(list.map(t => t.id));
        for (const [id, item] of Object.entries(tracker)) {
            if (!presentIds.has(id) && item.snapshot) {
                list.push(item.snapshot);
            }
        }
        list = list.filter(t => tracker[t.id]);
        if (trackerStatus !== 'all') {
            list = list.filter(t => tracker[t.id]?.status === trackerStatus);
        }
    }

    // Category filter
    if (selectedCategory !== 'All') {
        list = list.filter(t => t.category === selectedCategory);
    }

    // City filter
    if (selectedCity !== 'All') {
        list = list.filter(t => t.location === selectedCity);
    }

    // Paid filter
    if (selectedPaid === 'paid') {
        list = list.filter(t => t.is_paid);
    }

    // Language filter
    if (selectedLang !== 'All') {
        list = list.filter(t => t.language === selectedLang);
    }

    // Search query
    if (searchQuery) {
        list = list.filter(t => {
            const hay = [
                t.title,
                t.institution,
                t.department,
                t.research_group,
                t.description,
                ...(t.tags || [])
            ].join(' ').toLowerCase();
            return hay.includes(searchQuery);
        });
    }

    // Sort
    if (selectedSort === 'newest') {
        list.sort((a, b) => (b.first_seen || '').localeCompare(a.first_seen || ''));
    } else if (selectedSort === 'title') {
        list.sort((a, b) => a.title.localeCompare(b.title));
    }

    document.getElementById('visible-count').textContent = list.length;
    document.getElementById('total-count').textContent = allTheses.length;

    if (list.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No master thesis opportunities match your selected filters.</p>
                <button type="button" class="reset-btn" onclick="resetFilters()">Reset filters</button>
            </div>`;
        return;
    }

    container.innerHTML = list.map(t => createThesisCardHTML(t, tracker[t.id])).join('');
}

function resetFilters() {
    selectedCategory = 'All';
    selectedCity = 'All';
    selectedPaid = 'All';
    selectedLang = 'All';
    searchQuery = '';
    trackerOnly = false;
    document.getElementById('search-input').value = '';
    document.getElementById('city-filter').value = 'All';
    document.getElementById('paid-filter').value = 'All';
    document.getElementById('lang-filter').value = 'All';
    document.getElementById('my-theses-toggle').classList.remove('active');
    document.getElementById('tracker-bar').hidden = true;
    document.querySelectorAll('#category-pills .pill').forEach(p => {
        p.classList.toggle('active', p.dataset.category === 'All');
    });
    renderTheses();
}

function createThesisCardHTML(t, tracked) {
    const e = escapeHTML;
    const initial = e((t.institution || 'AUT').replace(/[^a-zA-Z]/g, '').slice(0, 3).toUpperCase() || 'AUT');
    const logoURL = safeURL(t.institution_logo);
    const logoHTML = logoURL
        ? `<img class="company-logo" src="${e(logoURL)}" alt="${e(t.institution)}" data-initial="${initial}">`
        : `<div class="company-logo">${initial}</div>`;

    const tagsHTML = (t.tags || []).map(tag => `<span class="tag">${e(tag)}</span>`).join('');

    const newBadge = isNewThesis(t) ? '<span class="meta-badge new-badge">🆕 New</span>' : '';
    const degreeBadge = `<span class="meta-badge thesis-badge">🎓 ${e(t.degree_level || "Master's Thesis")}</span>`;
    const compBadge = t.compensation ? `<span class="meta-badge paid-badge">💰 ${e(t.compensation)}</span>` : '';
    const durationBadge = t.duration ? `<span class="meta-badge duration-badge">⏱️ ${e(t.duration)}</span>` : '';
    const workloadBadge = t.workload ? `<span class="meta-badge workload-badge">💼 ${e(t.workload)}</span>` : '';
    const langBadge = `<span class="meta-badge lang-badge">${t.language === 'English' ? '🇬🇧 English' : '🇩🇪 German'}</span>`;

    const rgHTML = t.research_group
        ? `<div class="thesis-research-group">🔬 Research Group: ${e(t.research_group)}</div>`
        : '';

    const trackRow = tracked ? `
        <div class="track-row">
            <label class="track-label">
                <span>Status:</span>
                <select class="track-status-select" data-thesis-id="${e(t.id)}">
                    ${STATUS_OPTIONS.map(o => `
                        <option value="${o.value}" ${tracked.status === o.value ? 'selected' : ''}>${o.label}</option>
                    `).join('')}
                </select>
            </label>
            <span class="tailor-hint">Tracked</span>
        </div>
    ` : '';

    return `
        <div class="job-card" id="card-${e(t.id)}">
            <div>
                <div class="card-top">
                    ${logoHTML}
                    <div class="job-meta">
                        <h3 class="job-title">${e(t.title)}</h3>
                        <div class="company-name">${e(t.institution)} · ${e(t.department)}</div>
                        ${rgHTML}
                    </div>
                    <button type="button" class="save-btn${tracked ? ' saved' : ''}" data-thesis-id="${e(t.id)}"
                        aria-pressed="${tracked ? 'true' : 'false'}" aria-label="${tracked ? 'Remove from saved' : 'Save'} ${e(t.title)}"
                        title="${tracked ? 'Stop tracking' : 'Save thesis'}">
                        ${tracked ? '★' : '☆'}
                    </button>
                </div>

                ${trackRow}

                <div class="badges-row">
                    ${newBadge}
                    ${degreeBadge}
                    ${compBadge}
                    ${durationBadge}
                    ${workloadBadge}
                    ${langBadge}
                </div>

                <div class="details-row">
                    <span class="detail-item">📍 ${e(t.location)}</span>
                    <span class="detail-item">📂 ${e(t.category)}</span>
                    <span class="detail-item">🏛️ ${e(t.source)}</span>
                </div>

                ${tagsHTML ? `<div class="tags-row">${tagsHTML}</div>` : ''}

                <p class="description-text">${e(t.description)}</p>
            </div>

            <div class="card-bottom">
                <span class="source-badge">via ${e(t.source)}</span>
                ${tailorEnabled ? `<button type="button" class="tailor-btn" data-thesis-id="${e(t.id)}">✨ Tailor CV</button>` : ''}
                <a href="${e(safeURL(t.url) || '#')}" target="_blank" rel="noopener noreferrer" class="apply-btn">View Topic & Apply ↗</a>
            </div>
        </div>
    `;
}

// Local AI Tailor integration (active on localhost / resume_server.py)
async function initTailor() {
    if (!['localhost', '127.0.0.1'].includes(location.hostname)) return;

    let status;
    try {
        const res = await fetch('/api/tailor/status');
        if (!res.ok) return;
        status = await res.json();
    } catch {
        return;
    }

    tailorEnabled = true;
    document.getElementById('tailor-panel').hidden = false;
    const cvsNav = document.getElementById('nav-cvs');
    if (cvsNav) cvsNav.hidden = false;

    const select = document.getElementById('tailor-provider');
    const { local, cloud } = status.providers;
    select.innerHTML = `
        <option value="auto">Auto (local first)</option>
        <option value="local" ${local.available ? '' : 'disabled'}>Local · ${escapeHTML(local.label)}${local.available ? '' : ' (not running)'}</option>
        <option value="cloud" ${cloud.available ? '' : 'disabled'}>Cloud · ${escapeHTML(cloud.label)}${cloud.available ? '' : ' (no API key)'}</option>`;

    document.getElementById('tailor-modal-close').addEventListener('click', closeTailorModal);
    renderTheses();
}

function openTailorModal(thesisId) {
    const thesis = allTheses.find(t => t.id === thesisId);
    if (!thesis) return;

    const modal = document.getElementById('tailor-modal');
    const body = document.getElementById('tailor-modal-body');
    modal.hidden = false;

    body.innerHTML = `
        <div class="tailor-progress">
            <p>Tailoring your resume for <strong>${escapeHTML(thesis.title)}</strong> at <strong>${escapeHTML(thesis.institution)}</strong>...</p>
            <div class="spinner"></div>
        </div>
    `;

    const provider = document.getElementById('tailor-provider').value;
    const fullText = `${thesis.title}\n${thesis.institution} - ${thesis.department} (${thesis.research_group})\n\nTopic Description:\n${thesis.description}\n\nKey skills & topics: ${(thesis.tags || []).join(', ')}`;

    fetch('/api/tailor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url: thesis.url,
            text: fullText,
            provider
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.task_id) {
            pollTailorTask(data.task_id);
        } else {
            body.innerHTML = `<p class="cv-inline-error">Error: ${escapeHTML(data.error || 'Failed to start tailor pipeline')}</p>`;
        }
    })
    .catch(err => {
        body.innerHTML = `<p class="cv-inline-error">Error: ${escapeHTML(err.message)}</p>`;
    });
}

function pollTailorTask(taskId) {
    const body = document.getElementById('tailor-modal-body');
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/tailor/tasks/${taskId}`);
            const task = await res.json();
            if (task.status === 'done') {
                clearInterval(interval);
                body.innerHTML = `
                    <div class="tailor-result">
                        <div class="score-row">
                            <div class="score score-pass">${escapeHTML(task.result.analysis?.match_score || 85)}<small>/100</small></div>
                            <p>CV successfully tailored for this thesis position! PDF compiled and saved to <code>${escapeHTML(task.result.output_dir)}</code>.</p>
                        </div>
                        <div class="tailor-links">
                            ${task.result.files.resume_pdf ? `<a class="tailor-link" href="${task.result.files.resume_pdf}" target="_blank">📄 View PDF</a>` : ''}
                            ${task.result.files.cover_letter ? `<a class="tailor-link" href="${task.result.files.cover_letter}" target="_blank">✉️ Cover Letter</a>` : ''}
                            <a class="tailor-link" href="/cvs">Open in My CVs →</a>
                        </div>
                    </div>
                `;
            } else if (task.status === 'error') {
                clearInterval(interval);
                body.innerHTML = `<p class="cv-inline-error">Tailoring failed: ${escapeHTML(task.error)}</p>`;
            }
        } catch {
            clearInterval(interval);
        }
    }, 1000);
}

function closeTailorModal() {
    document.getElementById('tailor-modal').hidden = true;
}
