let allJobs = [];
let activeCategory = 'All';
let searchQuery = '';
let activeLocation = 'All';
let activeSeniority = 'All';
let activeRelocation = 'All';

document.addEventListener('DOMContentLoaded', () => {
    loadJobs();
    setupEventListeners();
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
                <a href="${job.url}" target="_blank" rel="noopener noreferrer" class="apply-btn">Apply Now ↗</a>
            </div>
        </div>
    `;
}
