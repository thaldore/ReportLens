/**
 * ReportLens Frontend Application — Microsoft Agent Framework Edition
 * .NET WebApi (port 8001) ile iletisim kurar.
 * Python versiyonuyla ayni is mantigi, farkli API base URL.
 */

const API = 'http://localhost:8001';  // .NET MAF Backend

// ══════════════════════════════════════════════════════════════════
//  SPA Routing
// ══════════════════════════════════════════════════════════════════

function navigate(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById('page-' + pageId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navBtn = document.querySelector(`.nav-item[data-page="${pageId}"]`);
    if (navBtn) navBtn.classList.add('active');

    const titles = {
        'dashboard': 'Kalite İstihbaratı',
        'analysis': 'Kalite Analiz Uzmanı',
        'report-analysis': 'Rapor Analizi',
        'self-eval': 'Öz Değerlendirme',
        'rubric': 'Rubrik Notlandırma',
        'consistency': 'Tutarsızlık Analizi',
        'management': 'Rapor Yönetimi',
        'test-results': 'Test Sonuçları',
        'settings': 'Ayarlar',
    };
    document.getElementById('topbar-title').textContent = titles[pageId] || 'ReportLens';

    if (pageId === 'dashboard') loadDashboard();
    if (pageId === 'report-analysis') loadReportSelect();
    if (pageId === 'self-eval') loadBirimSelect('selfeval-birim');
    if (pageId === 'rubric') loadRubricFiles();
    if (pageId === 'consistency') loadConsistencyOptions();
    if (pageId === 'management') loadManagementData();
    if (pageId === 'test-results') loadTestResults();
    if (pageId === 'settings') loadSettings();

    document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ══════════════════════════════════════════════════════════════════
//  Toast Notifications
// ══════════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const icons = { info: 'info', success: 'check_circle', error: 'error' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="material-symbols-outlined">${icons[type] || 'info'}</span>${message}`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4000);
}

// ══════════════════════════════════════════════════════════════════
//  Markdown Rendering
// ══════════════════════════════════════════════════════════════════

function renderMarkdown(text) {
    if (!text) return '<p style="color:var(--on-surface-variant)">Sonuç bulunamadı.</p>';
    try {
        return marked.parse(text);
    } catch (e) {
        return `<pre style="white-space:pre-wrap">${escapeHtml(text)}</pre>`;
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ══════════════════════════════════════════════════════════════════
//  API Helpers — .NET endpoint'leri
// ══════════════════════════════════════════════════════════════════

async function apiGet(endpoint) {
    const res = await fetch(API + endpoint);
    if (!res.ok) throw new Error(`API Hatası: ${res.status}`);
    return res.json();
}

async function apiPost(endpoint, body) {
    const res = await fetch(API + endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `API Hatası: ${res.status}`);
    }
    return res.json();
}

// ══════════════════════════════════════════════════════════════════
//  Dashboard
// ══════════════════════════════════════════════════════════════════

let allReports = [];

async function loadDashboard() {
    try {
        const [statusData, reportsData, birimData] = await Promise.all([
            apiGet('/api/status'),
            apiGet('/api/reports'),
            apiGet('/api/birimler'),
        ]);

        allReports = reportsData.reports || [];

        document.getElementById('dash-total-reports').textContent = allReports.length;
        document.getElementById('dash-birim-count').textContent = (birimData.birimler || []).length;
        document.getElementById('dash-vector-count').textContent = statusData.vektor_sayisi ?? statusData.toplam_nokta ?? '—';
        document.getElementById('dash-db-status').textContent = '✓ Aktif';
        document.getElementById('dash-db-engine').textContent = statusData.durum || 'SQL Server 2025';
        document.getElementById('dash-model').textContent = statusData.model || 'llama3.1:8b';

        populateBirimSelect('analysis-birim', birimData.birimler || []);
        renderDashReports(allReports);
        renderSystemInfo(statusData);
        renderQuickStats(statusData, allReports);

    } catch (e) {
        showToast('Dashboard yüklenirken hata: ' + e.message + ' — .NET backend ayakta mı? (port 8001)', 'error');
    }
}

function renderDashReports(reports) {
    const container = document.getElementById('dash-report-list');
    if (!reports.length) {
        container.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">folder_off</span><h3>Rapor bulunamadı</h3><p style="font-size:13px">Rapor Yönetimi sayfasından indeksleme yapın.</p></div>';
        return;
    }
    container.innerHTML = reports.slice(0, 15).map(r => `
        <div class="report-item" onclick="analyzeReportFromDash('${r.filename}')">
            <div class="report-item-left">
                <div class="report-icon"><span class="material-symbols-outlined">description</span></div>
                <div>
                    <div class="report-name">${r.filename}</div>
                    <div class="report-meta">Birim: ${r.birim} · Yıl: ${r.yil} · ${r.size_kb} KB</div>
                </div>
            </div>
            <div style="text-align:right">
                <div class="report-badge badge-info">${r.tur || '—'}</div>
                <div style="font-size:10px;color:var(--primary);margin-top:4px;font-weight:600">Analiz Et →</div>
            </div>
        </div>
    `).join('');
}

function analyzeReportFromDash(filename) {
    navigate('report-analysis');
    setTimeout(() => {
        const select = document.getElementById('report-select');
        if (select) { select.value = filename; analyzeSelectedReport(); }
    }, 300);
}

function filterDashReports(birim) {
    document.querySelectorAll('#page-dashboard .chip-filter').forEach(c => c.classList.remove('active'));
    event.target.classList.add('active');
    const filtered = birim === 'all' ? allReports : allReports.filter(r => r.birim === birim);
    renderDashReports(filtered);
}

function renderSystemInfo(status) {
    document.getElementById('dash-system-info').innerHTML = `
        <div class="insight-alert opportunity">
            <div class="alert-title">Framework</div>
            <p style="font-size:12px">${status.framework || 'ASP.NET Core 9 + Semantic Kernel'}</p>
        </div>
        <div class="insight-alert opportunity">
            <div class="alert-title">Veritabanı</div>
            <p style="font-size:12px">${status.durum || 'Aktif'}</p>
        </div>
        <div class="insight-alert opportunity">
            <div class="alert-title">Mimari</div>
            <p style="font-size:12px">${status.mimari || 'Clean Architecture + Modular Monolith'}</p>
        </div>
    `;
}

function renderQuickStats(status, reports) {
    const birimSet = new Set(reports.map(r => r.birim).filter(Boolean));
    document.getElementById('dash-quick-stats').innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px">
            <span style="color:var(--on-surface-variant)">Toplam Rapor</span>
            <span style="font-weight:700">${reports.length}</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px">
            <span style="color:var(--on-surface-variant)">Birim Sayısı</span>
            <span style="font-weight:700">${birimSet.size}</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px">
            <span style="color:var(--on-surface-variant)">MAF Vektör Noktası</span>
            <span style="font-weight:700">${status.vektor_sayisi ?? status.toplam_nokta ?? '—'}</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px">
            <span style="color:var(--on-surface-variant)">Tablo</span>
            <span style="font-weight:700;font-size:10px">${status.tablo_adi || 'MAF_DocumentVectors'}</span>
        </div>
    `;
}

// ══════════════════════════════════════════════════════════════════
//  Kalite Analizi (Chat)
// ══════════════════════════════════════════════════════════════════

async function sendAnalysis() {
    const input = document.getElementById('analysis-input');
    const query = input.value.trim();
    if (!query) return;

    const birim = document.getElementById('analysis-birim').value || null;
    const yil = document.getElementById('analysis-yil').value || null;

    const emptyState = document.getElementById('analysis-empty');
    if (emptyState) emptyState.remove();

    const chatBox = document.getElementById('analysis-chat');
    chatBox.innerHTML += `
        <div class="chat-message">
            <div class="chat-avatar user"><span class="material-symbols-outlined">person</span></div>
            <div class="chat-bubble user">${escapeHtml(query)}</div>
        </div>
    `;
    input.value = '';
    document.getElementById('analysis-send-btn').disabled = true;

    const loadingId = 'loading-' + Date.now();
    chatBox.innerHTML += `
        <div class="chat-message" id="${loadingId}">
            <div class="chat-avatar ai"><span class="material-symbols-outlined">auto_awesome</span></div>
            <div class="chat-bubble ai"><div class="loading-container" style="padding:12px"><div class="loading-spinner"></div><div class="loading-text">Semantic Kernel analiz ediyor...</div></div></div>
        </div>
    `;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const data = await apiPost('/api/analyze', { query, birim, yil });
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) {
            const bubble = loadingEl.querySelector('.chat-bubble');
            let filterInfo = '';
            if (data.auto_birim || data.auto_yil || birim || yil) {
                const parts = [];
                if (birim || data.auto_birim) parts.push(`Birim: <strong>${birim || data.auto_birim}</strong>`);
                if (yil || data.auto_yil) parts.push(`Yıl: <strong>${yil || data.auto_yil}</strong>`);
                filterInfo = `<div style="font-size:11px;color:var(--on-surface-variant);margin-bottom:12px;padding:6px 12px;background:var(--surface-container-low);border-radius:6px">🔍 Filtre: ${parts.join(', ')}</div>`;
            }
            bubble.innerHTML = filterInfo + renderMarkdown(data.result);
        }
    } catch (e) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.querySelector('.chat-bubble').innerHTML = `<p style="color:var(--error)">❌ Hata: ${escapeHtml(e.message)}</p>`;
    }

    document.getElementById('analysis-send-btn').disabled = false;
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ══════════════════════════════════════════════════════════════════
//  Rapor Analizi
// ══════════════════════════════════════════════════════════════════

async function loadReportSelect() {
    try {
        const data = await apiGet('/api/reports');
        const select = document.getElementById('report-select');
        select.innerHTML = '<option value="">Rapor seçin...</option>';
        (data.reports || []).forEach(r => {
            select.innerHTML += `<option value="${r.filename}">${r.filename} (${r.birim} · ${r.yil})</option>`;
        });
    } catch (e) { showToast('Raporlar yüklenemedi', 'error'); }
}

async function analyzeSelectedReport() {
    const filename = document.getElementById('report-select').value;
    if (!filename) { showToast('Lütfen bir rapor seçin', 'error'); return; }

    document.getElementById('report-result').style.display = 'none';
    document.getElementById('report-loading').style.display = 'block';

    try {
        const data = await apiPost('/api/analyze-report', { filename });
        document.getElementById('report-result').innerHTML = renderMarkdown(data.result);
        document.getElementById('report-result').style.display = 'block';
    } catch (e) {
        document.getElementById('report-result').innerHTML = `<p style="color:var(--error)">❌ ${escapeHtml(e.message)}</p>`;
        document.getElementById('report-result').style.display = 'block';
    }
    document.getElementById('report-loading').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════════
//  Öz Değerlendirme
// ══════════════════════════════════════════════════════════════════

async function loadBirimSelect(selectId) {
    try {
        const data = await apiGet('/api/birimler');
        populateBirimSelect(selectId, data.birimler || []);
    } catch (e) { /* ignore */ }
}

function populateBirimSelect(selectId, birimler) {
    const select = document.getElementById(selectId);
    if (!select) return;
    const currentVal = select.value;
    select.innerHTML = '<option value="">Tüm Birimler</option>';
    birimler.forEach(b => { select.innerHTML += `<option value="${b}">${b}</option>`; });
    if (currentVal) select.value = currentVal;
}

async function generateSelfEval() {
    const birim = document.getElementById('selfeval-birim').value;
    if (!birim) { showToast('Lütfen bir birim seçin', 'error'); return; }
    const yil = document.getElementById('selfeval-yil').value || null;

    document.getElementById('selfeval-result').style.display = 'none';
    document.getElementById('selfeval-loading').style.display = 'block';

    try {
        const data = await apiPost('/api/self-evaluation', { birim, yil });
        document.getElementById('selfeval-result').innerHTML = renderMarkdown(data.result);
        document.getElementById('selfeval-result').style.display = 'block';
    } catch (e) {
        document.getElementById('selfeval-result').innerHTML = `<p style="color:var(--error)">❌ ${escapeHtml(e.message)}</p>`;
        document.getElementById('selfeval-result').style.display = 'block';
    }
    document.getElementById('selfeval-loading').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════════
//  Rubrik Notlandırma
// ══════════════════════════════════════════════════════════════════

async function loadRubricFiles() {
    try {
        const data = await apiGet('/api/reports');
        const container = document.getElementById('rubric-file-list');
        const ozReports = (data.reports || []).filter(r =>
            r.filename.toLowerCase().includes('oz_degerlendirme') || r.filename.toLowerCase().includes('ozdegerlendirme')
        );
        const list = ozReports.length ? ozReports : (data.reports || []).slice(0, 10);
        container.innerHTML = list.map(r => `
            <label style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:var(--radius-sm);background:var(--surface-container-low);cursor:pointer;font-size:13px">
                <input type="checkbox" value="${r.filename}" class="rubric-checkbox" />
                <span>${r.filename}</span>
                <span style="margin-left:auto;font-size:11px;color:var(--on-surface-variant)">${r.birim}</span>
            </label>
        `).join('');
    } catch (e) { showToast('Dosyalar yüklenemedi', 'error'); }
}

async function evaluateRubric() {
    const checked = [...document.querySelectorAll('.rubric-checkbox:checked')].map(c => c.value);
    if (!checked.length) { showToast('Lütfen en az bir rapor seçin', 'error'); return; }

    document.getElementById('rubric-result').style.display = 'none';
    document.getElementById('rubric-loading').style.display = 'block';

    try {
        const data = await apiPost('/api/rubric', { filenames: checked });
        document.getElementById('rubric-result').innerHTML = renderMarkdown(data.result);
        document.getElementById('rubric-result').style.display = 'block';
    } catch (e) {
        document.getElementById('rubric-result').innerHTML = `<p style="color:var(--error)">❌ ${escapeHtml(e.message)}</p>`;
        document.getElementById('rubric-result').style.display = 'block';
    }
    document.getElementById('rubric-loading').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════════
//  Tutarsızlık Analizi
// ══════════════════════════════════════════════════════════════════

function setConsistencyTab(tab) {
    document.querySelectorAll('#page-consistency .tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('consistency-manual').style.display = tab === 'manual' ? 'block' : 'none';
    document.getElementById('consistency-mock').style.display = tab === 'mock' ? 'block' : 'none';
}

async function loadConsistencyOptions() {
    try {
        const [birimData, reportData] = await Promise.all([apiGet('/api/birimler'), apiGet('/api/reports')]);
        populateBirimSelect('consistency-birim', birimData.birimler || []);
        const reports = reportData.reports || [];
        ['consistency-file', 'mock-file'].forEach(id => {
            const sel = document.getElementById(id);
            sel.innerHTML = '<option value="">Rapor seçin...</option>';
            reports.forEach(r => { sel.innerHTML += `<option value="${r.filename}">${r.filename}</option>`; });
        });
    } catch (e) { /* ignore */ }
}

async function checkConsistency() {
    const text = document.getElementById('consistency-text').value.trim();
    if (!text) { showToast('Lütfen karşılaştırılacak metin girin', 'error'); return; }

    const survey = document.getElementById('consistency-survey').value.trim() || null;
    const birim = document.getElementById('consistency-birim').value || null;
    const filename = document.getElementById('consistency-file').value || null;

    document.getElementById('consistency-result').style.display = 'none';
    document.getElementById('consistency-loading').style.display = 'block';

    try {
        const data = await apiPost('/api/consistency', { comparison_text: text, survey_text: survey, birim, filename });
        document.getElementById('consistency-result').innerHTML = renderMarkdown(data.result);
        document.getElementById('consistency-result').style.display = 'block';
    } catch (e) {
        document.getElementById('consistency-result').innerHTML = `<p style="color:var(--error)">❌ ${escapeHtml(e.message)}</p>`;
        document.getElementById('consistency-result').style.display = 'block';
    }
    document.getElementById('consistency-loading').style.display = 'none';
}

async function generateAndCheckMock() {
    const filename = document.getElementById('mock-file').value;
    if (!filename) { showToast('Lütfen bir rapor seçin', 'error'); return; }
    const mode = document.getElementById('mock-mode').value;

    document.getElementById('consistency-result').style.display = 'none';
    document.getElementById('consistency-loading').style.display = 'block';

    try {
        const mockData = await apiPost('/api/mock-data', { filename, mode });
        const mockText = mockData.result || '';
        let surveyText = '';
        let comparisonText = mockText;
        if (mockText.includes('[METIN_BEYANLARI]')) {
            const parts = mockText.split('[METIN_BEYANLARI]');
            surveyText = parts[0].replace('[ANKET_VERISI]', '').trim();
            comparisonText = parts[1] ? parts[1].trim() : mockText;
        }
        const consData = await apiPost('/api/consistency', { comparison_text: comparisonText, survey_text: surveyText || null, filename });
        document.getElementById('consistency-result').innerHTML = `
            <h2 style="font-family:'Manrope';color:var(--primary)">📋 Mock Veri (Mod: ${mode})</h2>
            ${renderMarkdown(mockText)}
            <hr />
            <h2 style="font-family:'Manrope';color:var(--primary)">🔍 Tutarsızlık Analizi</h2>
            ${renderMarkdown(consData.result)}
        `;
        document.getElementById('consistency-result').style.display = 'block';
    } catch (e) {
        document.getElementById('consistency-result').innerHTML = `<p style="color:var(--error)">❌ ${escapeHtml(e.message)}</p>`;
        document.getElementById('consistency-result').style.display = 'block';
    }
    document.getElementById('consistency-loading').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════════
//  Rapor Yönetimi
// ══════════════════════════════════════════════════════════════════

async function loadManagementData() {
    try {
        const data = await apiGet('/api/raw-files');
        const container = document.getElementById('raw-file-list');
        const files = data.files || [];
        if (!files.length) {
            container.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">folder_off</span><h3>Dosya bulunamadı</h3><p style="font-size:13px">Python API üzerinden dosya yükleyin.</p></div>';
            return;
        }
        container.innerHTML = `<div class="report-list">${files.map(f => `
            <div class="report-item">
                <div class="report-item-left">
                    <div class="report-icon"><span class="material-symbols-outlined">${f.processed ? 'check_circle' : 'pending'}</span></div>
                    <div>
                        <div class="report-name">${f.filename}</div>
                        <div class="report-meta">${f.birim} · ${f.yil} · ${f.size_mb} MB</div>
                    </div>
                </div>
                <div>
                    <span class="report-badge ${f.processed ? 'badge-success' : 'badge-warning'}">${f.processed ? 'İşlendi' : 'Bekliyor'}</span>
                </div>
            </div>
        `).join('')}</div>`;
    } catch (e) { showToast('Dosyalar yüklenemedi', 'error'); }
}

async function uploadFiles(fileList) {
    showToast('Dosya yükleme için Python API (port 8000) kullanın.', 'info');
}

async function processAndIndex(forceReindex) {
    const statusEl = document.getElementById('process-status');
    statusEl.innerHTML = '<div style="display:flex;align-items:center;gap:8px"><div class="loading-spinner" style="width:20px;height:20px"></div> MAF_DocumentVectors indeksleniyor...</div>';

    try {
        const data = await apiPost('/api/process?force_reindex=' + forceReindex, {});
        statusEl.innerHTML = `<p style="color:#1b5e20">✅ İndeksleme tamamlandı — ${data.indexed_chunks || 0} chunk eklendi</p>`;
        showToast('MAF indeksleme tamamlandı', 'success');
        loadManagementData();
    } catch (e) {
        statusEl.innerHTML = `<p style="color:var(--error)">❌ ${escapeHtml(e.message)}</p>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const area = document.getElementById('upload-area');
    if (area) {
        ['dragenter', 'dragover'].forEach(e => area.addEventListener(e, ev => { ev.preventDefault(); area.classList.add('dragging'); }));
        ['dragleave', 'drop'].forEach(e => area.addEventListener(e, ev => { ev.preventDefault(); area.classList.remove('dragging'); }));
        area.addEventListener('drop', ev => { uploadFiles(ev.dataTransfer.files); });
    }
});

// ══════════════════════════════════════════════════════════════════
//  Test Sonuçları
// ══════════════════════════════════════════════════════════════════

async function loadTestResults() {
    try {
        const data = await apiGet('/api/test-results');
        const container = document.getElementById('test-list');
        const results = data.results || [];
        if (!results.length) {
            container.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">science</span><h3>Test sonucu bulunamadı</h3></div>';
            return;
        }
        container.innerHTML = `<div class="report-list">${results.map(r => `
            <div class="report-item" style="cursor:pointer">
                <div class="report-item-left">
                    <div class="report-icon"><span class="material-symbols-outlined">science</span></div>
                    <div><div class="report-name">${r.filename}</div></div>
                </div>
            </div>
        `).join('')}</div>`;
    } catch (e) { showToast('Test sonuçları yüklenemedi', 'error'); }
}

// ══════════════════════════════════════════════════════════════════
//  Ayarlar
// ══════════════════════════════════════════════════════════════════

async function loadSettings() {
    try {
        const data = await apiGet('/api/status');
        document.getElementById('settings-llm').innerHTML = `
            <div><strong>Model:</strong> ${data.model || '—'}</div>
            <div><strong>Embedding:</strong> ${data.embedding_model || '—'}</div>
            <div><strong>Ollama URL:</strong> ${data.ollama_url || '—'}</div>
            <div><strong>Orchestrator:</strong> Semantic Kernel</div>
        `;
        document.getElementById('settings-db').innerHTML = `
            <div><strong>Tablo:</strong> ${data.tablo_adi || 'MAF_DocumentVectors'}</div>
            <div><strong>Veritabanı:</strong> ReportLensDB</div>
            <div><strong>Durum:</strong> ${data.durum || '—'}</div>
            <div><strong>Vektör Sayısı:</strong> ${data.vektor_sayisi ?? data.toplam_nokta ?? '—'}</div>
        `;
        document.getElementById('settings-sys').innerHTML = `
            <div><strong>Framework:</strong> ${data.framework || 'ASP.NET Core 9 + Semantic Kernel'}</div>
            <div><strong>Mimari:</strong> ${data.mimari || 'Clean Architecture + Modular Monolith'}</div>
            <div><strong>Telemetri:</strong> ❌ Kapalı</div>
            <div><strong>Sürüm:</strong> v2.0.0</div>
        `;
    } catch (e) { showToast('Ayarlar yüklenemedi — .NET backend ayakta mı?', 'error'); }
}

// ══════════════════════════════════════════════════════════════════
//  Export
// ══════════════════════════════════════════════════════════════════

function exportCurrentResult() {
    const activePage = document.querySelector('.page.active');
    if (!activePage) return;
    const resultPanel = activePage.querySelector('.result-panel');
    const chatBubbles = activePage.querySelectorAll('.chat-bubble.ai');

    let content = '';
    if (resultPanel && resultPanel.style.display !== 'none') {
        content = resultPanel.innerText;
    } else if (chatBubbles.length) {
        content = Array.from(chatBubbles).map(b => b.innerText).join('\n\n---\n\n');
    }

    if (!content) { showToast('Dışa aktarılacak sonuç bulunamadı', 'error'); return; }

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `reportlens_maf_export_${new Date().toISOString().slice(0,10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Dışa aktarma tamamlandı', 'success');
}

// ══════════════════════════════════════════════════════════════════
//  Initialization
// ══════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});
