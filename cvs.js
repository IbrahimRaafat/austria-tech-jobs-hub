// "My CVs" dashboard - only works when served by scripts/resume_server.py

let library = null;
let filterQuery = '';

document.addEventListener('DOMContentLoaded', () => {
    loadLibrary();

    document.getElementById('cv-search').addEventListener('input', (e) => {
        filterQuery = e.target.value.toLowerCase().trim();
        render();
    });

    document.body.addEventListener('click', onAction);

    const modal = document.getElementById('preview-modal');
    const close = () => { modal.hidden = true; document.getElementById('preview-frame').src = 'about:blank'; };
    document.getElementById('preview-close').addEventListener('click', close);
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) close(); });
});

function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function formatDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });
}

let overleafStatus = null;

async function loadLibrary() {
    try {
        const [cvRes, overleafRes] = await Promise.all([
            fetch('/api/cvs', { cache: 'no-store' }),
            fetch('/api/overleaf/status', { cache: 'no-store' }).catch(() => null)
        ]);
        if (!cvRes.ok) throw new Error(cvRes.statusText);
        library = await cvRes.json();
        if (overleafRes && overleafRes.ok) {
            overleafStatus = await overleafRes.json();
        }
        render();
    } catch {
        document.querySelector('main').innerHTML = `<p class="tailor-error">The CV dashboard needs the local server. Run <code>python scripts/resume_server.py</code> and open <a href="http://localhost:8765/cvs">localhost:8765/cvs</a>.</p>`;
    }
}

function matches(...fields) {
    return !filterQuery || fields.join(' ').toLowerCase().includes(filterQuery);
}

function render() {
    const { tailored, archive, master } = library;

    const scores = tailored.map(t => t.match_score).filter(s => typeof s === 'number');
    const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : '–';
    document.getElementById('cv-stats').innerHTML = [
        [tailored.length, 'tailored CVs'],
        [avg, 'avg. match score'],
        [archive.length, 'earlier CVs'],
        [library.latex_engine ? '✓' : '✕', library.latex_engine ? `PDF via ${escapeHTML(library.latex_engine)}` : 'no LaTeX engine'],
    ].map(([value, label]) => `<div class="cv-stat"><strong>${value}</strong><span>${label}</span></div>`).join('');

    const isOverleafRunning = Boolean(overleafStatus?.overleaf_running);
    const overleafBadge = isOverleafRunning
        ? `<span class="meta-badge new-badge" title="Overleaf container is running">Overleaf: Active</span>`
        : `<span class="meta-badge salary-badge" title="Overleaf container is stopped">Overleaf: Stopped</span>`;

    document.getElementById('cv-master').innerHTML = master.exists ? `
        <div class="job-card cv-card cv-master-card">
            <div>
                <div class="badges-row">
                    <span class="meta-badge seniority-badge">Master resume</span>
                    ${overleafBadge}
                    ${overleafStatus?.hardlinked ? `<span class="meta-badge cv-badge" title="Hardlinked to Desktop/CV/main.tex">Desktop Synced 🔗</span>` : ''}
                </div>
                <h3 class="job-title">${escapeHTML(master.path)}</h3>
                <p class="description-text">The source of truth every tailored CV is generated from. Updated ${formatDate(master.modified)}.</p>
                ${!isOverleafRunning ? `<p class="tailor-hint" style="color: #b45309; margin-top: 6px;">💡 <strong>Overleaf is currently stopped.</strong> To open Overleaf on port 80, launch Docker Desktop and run <code>bin/up -d</code> in <code>Desktop/CV/overleaf-toolkit</code> (or run <code>start_all.bat</code>).</p>` : ''}
            </div>
            <div class="cv-actions">
                ${pdfButton(master.pdf_url, 'archive', master.id, 'Master resume')}
                <a class="tailor-link" href="${master.source_url}" target="_blank">.tex ↗</a>
                <a class="tailor-link" href="${isOverleafRunning ? 'http://localhost:80' : 'javascript:void(0)'}" ${isOverleafRunning ? 'target="_blank"' : 'data-action="overleaf-warn"'} title="Open local Overleaf web UI">Overleaf ↗</a>
                <button type="button" class="tailor-link" data-action="overleaf-sync" title="Sync with Overleaf container">Sync Overleaf ⟳</button>
            </div>
        </div>` : `<p class="tailor-alert">No master resume at <code>${escapeHTML(master.path)}</code>.</p>`;

    const tailoredShown = tailored.filter(t => matches(t.title, t.company, t.id));
    document.getElementById('tailored-title').textContent = `Tailored CVs (${tailoredShown.length})`;
    document.getElementById('tailored-list').innerHTML = tailoredShown.length
        ? tailoredShown.map(tailoredCard).join('')
        : `<p class="tailor-hint">${tailored.length ? 'No matches.' : 'Nothing yet. Use ✨ Tailor resume on any job on the <a href="/">jobs board</a>.'}</p>`;

    const archiveShown = archive.filter(a => matches(a.name, a.tailored_for));
    document.getElementById('archive-title').textContent = `Earlier CVs (${archiveShown.length})`;
    document.getElementById('archive-dir').textContent = `from ${library.archive_dir}`;
    document.getElementById('archive-list').innerHTML = archiveShown.length
        ? archiveShown.map(archiveCard).join('')
        : `<p class="tailor-hint">${archive.length ? 'No matches.' : 'No CV files found (set CV_ARCHIVE_DIR to point elsewhere).'}</p>`;
}

function pdfButton(pdfUrl, kind, id, title) {
    return pdfUrl
        ? `<button type="button" class="apply-btn" data-action="preview" data-url="${pdfUrl}" data-title="${escapeHTML(title)}">View PDF</button>`
        : `<button type="button" class="tailor-btn" data-action="compile" data-kind="${kind}" data-id="${escapeHTML(id)}" data-title="${escapeHTML(title)}">Build PDF</button>`;
}

function tailoredCard(t) {
    const scoreClass = t.match_score >= 70 ? 'good' : t.match_score >= 45 ? 'ok' : 'low';
    const f = t.files;
    const title = `${t.title}${t.company ? ' · ' + t.company : ''}`;
    return `
        <div class="job-card cv-card">
            <div>
                <div class="card-top">
                    <div class="cv-score score-${scoreClass}">${escapeHTML(t.match_score ?? '–')}</div>
                    <div class="job-meta">
                        <h3 class="job-title">${escapeHTML(t.title)}</h3>
                        <div class="company-name">${escapeHTML(t.company)}</div>
                    </div>
                </div>
                <div class="badges-row">
                    <span class="meta-badge exp-badge">${formatDate(t.created)}</span>
                    ${t.verdict ? `<span class="meta-badge verdict-badge verdict-${escapeHTML(t.verdict)}">fact-check ${escapeHTML(t.verdict)}</span>` : ''}
                </div>
                ${t.gaps.length ? `<p class="description-text"><strong>Gaps:</strong> ${t.gaps.map(escapeHTML).join('; ')}</p>` : ''}
                <p class="tailor-hint">${escapeHTML(t.model)}</p>
            </div>
            <div class="cv-actions">
                ${pdfButton(f.resume_pdf, 'tailored', t.id, title)}
                ${f.resume_tex ? `<a class="tailor-link" href="${f.resume_tex}?download=1">.tex ⤓</a>` : ''}
                ${f.cover_letter ? `<a class="tailor-link" href="${f.cover_letter}" target="_blank">Cover letter</a>` : ''}
                ${f.report ? `<a class="tailor-link" href="${f.report}" target="_blank">Report</a>` : ''}
                ${/^https?:\/\//i.test(t.url || '') ? `<a class="tailor-link" href="${escapeHTML(t.url)}" target="_blank" rel="noopener noreferrer">Job ↗</a>` : ''}
                <button type="button" class="tailor-link cv-delete" data-action="delete" data-id="${escapeHTML(t.id)}" data-title="${escapeHTML(title)}">Delete</button>
            </div>
        </div>`;
}

function archiveCard(a) {
    return `
        <div class="job-card cv-card">
            <div>
                <div class="card-top">
                    <div class="company-logo">${escapeHTML(a.kind.toUpperCase())}</div>
                    <div class="job-meta">
                        <h3 class="job-title">${escapeHTML(a.name)}</h3>
                        <div class="company-name">${a.tailored_for ? 'Tailored for: ' + escapeHTML(a.tailored_for) : 'Modified ' + formatDate(a.modified)}</div>
                    </div>
                </div>
                ${a.tailored_for ? `<div class="badges-row"><span class="meta-badge exp-badge">${formatDate(a.modified)}</span></div>` : ''}
            </div>
            <div class="cv-actions">
                ${a.kind === 'docx' ? '' : pdfButton(a.pdf_url, 'archive', a.id, a.name)}
                ${a.kind !== 'pdf' ? `<a class="tailor-link" href="${a.source_url}" target="_blank">Source ${a.kind === 'docx' ? '⤓' : '↗'}</a>` : ''}
            </div>
        </div>`;
}

async function postJSON(url, body) {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return { ok: response.ok, data: await response.json() };
}

function openPreview(url, title) {
    document.getElementById('preview-title').textContent = title;
    document.getElementById('preview-frame').src = url;
    document.getElementById('preview-modal').hidden = false;
}

async function onAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const { action, id, kind, title, url } = btn.dataset;

    if (action === 'preview') return openPreview(url, title);

    if (action === 'overleaf-warn') {
        alert("Overleaf is currently not running!\n\n1. Open Docker Desktop on Windows.\n2. In terminal, run 'bin/up -d' in Desktop/CV/overleaf-toolkit (or double-click 'start_all.bat').\n3. Once running, click 'Overleaf ↗' to edit your CV.");
        return;
    }

    if (action === 'compile') {
        btn.parentElement.querySelector('.cv-inline-error')?.remove();
        btn.disabled = true;
        btn.textContent = 'Building…';
        const { ok, data } = await postJSON('/api/cvs/compile', { kind, id });
        if (ok) {
            await loadLibrary();
            openPreview(data.pdf_url, title);
        } else {
            btn.disabled = false;
            btn.textContent = 'Build PDF';
            btn.insertAdjacentHTML('afterend', `<p class="tailor-error cv-inline-error">${escapeHTML(data.message)}</p>`);
        }
    }

    if (action === 'delete') {
        if (btn.dataset.confirm !== 'yes') {
            btn.dataset.confirm = 'yes';
            btn.textContent = 'Click again to delete';
            return;
        }
        await postJSON('/api/cvs/delete', { id });
        loadLibrary();
    }

    if (action === 'overleaf-sync') {
        btn.disabled = true;
        btn.textContent = 'Syncing…';
        btn.parentElement.querySelector('.cv-inline-error')?.remove();
        const { ok, data } = await postJSON('/api/overleaf/sync', { action: 'pull' });
        btn.disabled = false;
        btn.textContent = 'Sync Overleaf ⟳';
        if (ok) {
            await loadLibrary();
            alert(data.message || 'Synced successfully from Overleaf!');
        } else {
            btn.insertAdjacentHTML('afterend', `<p class="tailor-error cv-inline-error">${escapeHTML(data.message || 'Sync failed. Make sure Docker and Overleaf are running.')}</p>`);
        }
    }
}
