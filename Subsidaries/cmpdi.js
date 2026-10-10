'use strict';
/* ═══════════════════════════════════════════════════════════════════
   IPMPRS — Puducherry Police Hackathon 2026 · Problem Statement 01
   Intelligent Proposal Management and Precedent Retrieval System
   Frontend Logic: State Machine, Precedent Gate, Pulse & Audit Chain
   ═══════════════════════════════════════════════════════════════════ */

const API = (window.location.protocol.startsWith('http') && window.location.port)
  ? window.location.origin
  : 'http://localhost:5000';

/* ── DOM & Formatting Helpers ───────────────────────────────────── */
const $   = id => document.getElementById(id);
const esc = s  => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const num = n  => (n == null || isNaN(n)) ? '0' : Number(n).toLocaleString();

const fmtInr = val => {
  if (val == null || isNaN(val) || val === '') return '₹0';
  const n = Number(val);
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000)   return `₹${(n / 100000).toFixed(2)} Lakh`;
  return `₹${n.toLocaleString('en-IN')}`;
};

const fmtDate = d => {
  if (!d) return '—';
  try {
    const dt = new Date(d);
    if (isNaN(dt.getTime())) return String(d).slice(0, 16);
    return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return String(d).slice(0, 16); }
};

const fmtTime = d => {
  if (!d) return '—';
  try {
    const dt = new Date(d);
    if (isNaN(dt.getTime())) return String(d).slice(0, 16);
    return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return String(d).slice(0, 16); }
};

/* ── Toast & Loading Overlay ────────────────────────────────────── */
function toast(msg, type = 'info', duration = 3200) {
  const t = $('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = `toast ${type === 'ok' ? 'ok' : (type === 'err' ? 'err' : '')}`;
  t.style.display = 'block';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.display = 'none'; }, duration);
}

function showLoad(msg = 'Processing…') {
  const m = $('loading-msg'); if (m) m.textContent = msg;
  const o = $('loading-ov');  if (o) o.style.display = 'flex';
}
function hideLoad() {
  const o = $('loading-ov'); if (o) o.style.display = 'none';
}

/* ── Ambience & Sidebar Controls ────────────────────────────────── */
let _ambientMode = localStorage.getItem('ipmprs_ambient') || 'high';

function applyAmbientMode(mode) {
  _ambientMode = mode;
  localStorage.setItem('ipmprs_ambient', mode);
  const vid = $('bg-video');
  const txt = $('ambient-state-text');
  if (!vid) return;
  vid.classList.remove('ambient-low', 'ambient-off');
  if (mode === 'low') {
    vid.classList.add('ambient-low');
    if (vid.paused) vid.play().catch(() => {});
    if (txt) txt.textContent = 'Ambience: Low';
  } else if (mode === 'off') {
    vid.classList.add('ambient-off');
    vid.pause();
    if (txt) txt.textContent = 'Ambience: Off';
  } else {
    if (vid.paused) vid.play().catch(() => {});
    if (txt) txt.textContent = 'Ambience: High';
  }
}

function toggleBackgroundVideo() {
  if (_ambientMode === 'high') applyAmbientMode('low');
  else if (_ambientMode === 'low') applyAmbientMode('off');
  else applyAmbientMode('high');
  toast(`Ambience: ${_ambientMode.toUpperCase()}`, 'ok', 1500);
}

function toggleSidebar() {
  const sb = $('sidebar');
  if (sb) sb.classList.toggle('sidebar-open');
}

/* ═══════════════════════════════════════════════════════════════════
   ROLE SWITCHER & ACTIVE USER MANAGEMENT
   ═══════════════════════════════════════════════════════════════════ */
const OFFICERS_BY_ROLE = {
  initiator: { name: 'HC R. Kumar (Dealing Assistant)', roleName: 'Initiator' },
  reviewer:  { name: 'DSP M. Selvam (Reviewing Officer)', roleName: 'Reviewer' },
  approver:  { name: 'SP K. Vijayakumar (Approving Authority)', roleName: 'Approving Authority' },
  auditor:   { name: 'Insp. S. Anand (Police Internal Audit)', roleName: 'Auditor' }
};

let _currentRole = localStorage.getItem('ipmprs_role') || 'initiator';

function initRole() {
  const sel = $('role-switcher');
  if (sel) sel.value = _currentRole;
  updateOfficerDisplay();
}

function onRoleChanged(newRole) {
  _currentRole = newRole;
  localStorage.setItem('ipmprs_role', newRole);
  updateOfficerDisplay();
  toast(`Active role switched to: ${OFFICERS_BY_ROLE[newRole]?.roleName || newRole}`, 'ok');
  // If detail view is open, re-render role buttons
  if (_activeProposal) renderDetailActionButtons(_activeProposal);
}

function updateOfficerDisplay() {
  const info = OFFICERS_BY_ROLE[_currentRole] || OFFICERS_BY_ROLE.initiator;
  const nameEl = $('officer-name');
  if (nameEl) nameEl.textContent = info.name;
}

function getCurrentActor() {
  const info = OFFICERS_BY_ROLE[_currentRole] || OFFICERS_BY_ROLE.initiator;
  return { actor: info.name, role: info.roleName };
}

/* ═══════════════════════════════════════════════════════════════════
   TAB SWITCHING & ROUTING
   ═══════════════════════════════════════════════════════════════════ */
const _loadedTabs = new Set();

function switchTab(name) {
  document.querySelectorAll('.pane').forEach(p => {
    p.classList.remove('active');
    // Also hide display:none panes (OCR, DocGen, Memory)
    if (p.id && ['pane-ocr','pane-docgen','pane-memory'].includes(p.id)) {
      p.style.display = 'none';
    }
  });
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));

  const pane = $(`pane-${name}`);
  const nav  = $(`nav-${name}`);

  if (pane) {
    if (['ocr','docgen','memory'].includes(name)) {
      pane.style.display = 'block';
      // Add active class too for consistent styling
      pane.classList.add('active');
    } else {
      pane.style.display = '';
      pane.classList.add('active');
    }
  }
  if (nav) nav.classList.add('active');

  if (name === 'dashboard') initDashboard();
  if (name === 'proposals') loadProposals();
  if (name === 'archive')   loadArchive();
  if (name === 'reports')   loadBriefsList();
  if (name === 'docgen')    initDocgen();
  if (name === 'memory')    loadMemoryDocs();
}

/* ── Subtab switching inside Proposal Detail View ──────────────── */
function switchSubtab(subName) {
  document.querySelectorAll('.subtab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.subtab-pane').forEach(p => p.classList.remove('active'));

  const targetPane = $(`subtab-${subName}`);
  if (targetPane) targetPane.classList.add('active');

  const btn = Array.from(document.querySelectorAll('.subtab-btn'))
    .find(b => b.getAttribute('onclick')?.includes(subName));
  if (btn) btn.classList.add('active');
}

/* ═══════════════════════════════════════════════════════════════════
   HEALTH CHECK
   ═══════════════════════════════════════════════════════════════════ */
async function checkHealth() {
  try {
    const r = await fetch(`${API}/api/health`);
    const d = await r.json();
    const dot = $('status-dot');
    const txt = $('status-text');
    if (d.ollama_running) {
      if (dot) dot.className = 'status-dot online';
      if (txt) txt.textContent = 'Ollama Online';
    } else {
      if (dot) dot.className = 'status-dot offline';
      if (txt) txt.textContent = 'Offline Engine (BM25)';
    }
    if (d.default_model) {
      const chip = $('model-chip');
      if (chip) chip.textContent = d.default_model;
    }
  } catch {
    const dot = $('status-dot');
    const txt = $('status-text');
    if (dot) dot.className = 'status-dot offline';
    if (txt) txt.textContent = 'Server Offline';
  }
}

/* ═══════════════════════════════════════════════════════════════════
   STATUS BADGE FORMATTER
   ═════════════════════════════════════════════════════════════ */
function getStatusBadge(status) {
  const map = {
    'Draft':                  'badge-draft',
    'Submitted':              'badge-submitted',
    'Under Review':           'badge-review',
    'Returned for Revision':  'badge-returned',
    'Approved':               'badge-approved',
    'Rejected':               'badge-rejected',
    'In Implementation':      'badge-implementation',
    'Implemented':            'badge-implemented',
    'Closed':                 'badge-closed',
  };
  const cls = map[status] || 'badge-draft';
  return `<span class="status-pill ${cls}">${esc(status)}</span>`;
}

/* ═══════════════════════════════════════════════════════════════════
   1. DASHBOARD & CHARTS
   ═══════════════════════════════════════════════════════════════════ */
let _chartCategories = null;
let _chartStatus = null;

async function initDashboard() {
  try {
    const r = await fetch(`${API}/api/proposals/stats`);
    const d = await r.json();

    // Populate KPI cards
    if ($('kv-pending'))   $('kv-pending').textContent   = num(d.pending_action);
    if ($('kv-review'))    $('kv-review').textContent    = num(d.under_review);
    if ($('kv-approved'))  $('kv-approved').textContent  = num(d.approved);
    if ($('kv-rejected'))  $('kv-rejected').textContent  = num(d.rejected);
    if ($('kv-avg-days'))  $('kv-avg-days').textContent  = `${d.avg_decision_days}d`;
    if ($('badge-proposals')) $('badge-proposals').textContent = num(d.total_proposals);

    // Render Charts
    renderCategoryChart(d.by_category || {});
    renderStatusChart(d.by_status || {});

    // Populate Recently Closed Table
    renderRecentlyClosedTable(d.recently_closed || []);
  } catch (err) {
    console.error('[Dashboard] error loading stats:', err);
  }
}

function renderCategoryChart(catData) {
  const canvas = $('chart-categories');
  if (!canvas || !window.Chart) return;

  const labels = Object.keys(catData);
  const data = labels.map(k => catData[k]?.count || 0);

  if (_chartCategories) _chartCategories.destroy();

  _chartCategories = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Proposals',
        data: data,
        backgroundColor: [
          'rgba(201, 169, 97, 0.7)',
          'rgba(56, 189, 248, 0.7)',
          'rgba(52, 211, 153, 0.7)',
          'rgba(148, 163, 184, 0.7)',
          'rgba(245, 158, 11, 0.7)',
          'rgba(129, 140, 248, 0.7)',
        ],
        borderColor: 'rgba(255, 255, 255, 0.2)',
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#a39c92', font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#a39c92', font: { size: 10 }, stepSize: 2 }
        }
      }
    }
  });
}

function renderStatusChart(statusData) {
  const canvas = $('chart-status');
  if (!canvas || !window.Chart) return;

  const labels = Object.keys(statusData);
  const data = labels.map(k => statusData[k] || 0);

  if (_chartStatus) _chartStatus.destroy();

  _chartStatus = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: [
          '#94a3b8', // Draft
          '#818cf8', // Submitted
          '#38bdf8', // Under Review
          '#f59e0b', // Returned
          '#34d399', // Approved
          '#f43f5e', // Rejected
          '#0284c7', // Implementation
          '#10b981', // Implemented
          '#64748b'  // Closed
        ],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#ece8e1', font: { size: 10.5 }, boxWidth: 10 }
        }
      },
      cutout: '62%'
    }
  });
}

function renderRecentlyClosedTable(items) {
  const tbody = $('dash-closed-tbody');
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="tbl-empty">No closed proposals with outcomes recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(p => `
    <tr>
      <td class="mono fw6 text-ac" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">${esc(p.ref_no)}</td>
      <td>
        <div class="fw6" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">${esc(p.title)}</div>
        <div style="font-size:11px; color:var(--text-dim);">${esc(p.category)}</div>
      </td>
      <td style="font-size:12px; color:var(--text-mid);">${esc(p.department)}</td>
      <td class="mono fw6">${fmtInr(p.actual_cost)}</td>
      <td><span class="status-pill badge-implemented">${esc(p.implementation_status || 'Closed')}</span></td>
      <td style="font-size:12px; color:var(--text-mid); max-width:280px;">
        ${p.lessons_learned ? `<span class="text-amber">⚠</span> ${esc(p.lessons_learned)}` : '—'}
      </td>
    </tr>
  `).join('');
}

/* ═══════════════════════════════════════════════════════════════════
   2. PROPOSALS HUB (LISTING & FILTERING)
   ═══════════════════════════════════════════════════════════════════ */
let _allProposalsCache = [];

async function loadProposals() {
  const tbody = $('proposals-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="tbl-empty">Loading proposal records…</td></tr>`;

  try {
    const r = await fetch(`${API}/api/proposals?limit=200`);
    const d = await r.json();
    _allProposalsCache = d.proposals || [];
    renderFilteredProposals();
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="tbl-empty">Failed to load proposals. Ensure server is running.</td></tr>`;
  }
}

function onProposalFilterChanged() {
  renderFilteredProposals();
}

function renderFilteredProposals() {
  const tbody = $('proposals-tbody');
  if (!tbody) return;

  const search = ($('prop-search')?.value || '').toLowerCase().trim();
  const cat    = $('prop-filter-cat')?.value || 'All';
  const dept   = $('prop-filter-dept')?.value || 'All';
  const status = $('prop-filter-status')?.value || 'All';

  let filtered = _allProposalsCache.filter(p => {
    if (cat !== 'All' && p.category !== cat) return false;
    if (dept !== 'All' && p.department !== dept) return false;
    if (status !== 'All' && p.status !== status) return false;
    if (search) {
      const matchRef   = (p.ref_no || '').toLowerCase().includes(search);
      const matchTitle = (p.title || '').toLowerCase().includes(search);
      const matchDesc  = (p.description || '').toLowerCase().includes(search);
      if (!matchRef && !matchTitle && !matchDesc) return false;
    }
    return true;
  });

  const countLbl = $('proposals-count-label');
  if (countLbl) countLbl.textContent = `Showing ${filtered.length} of ${_allProposalsCache.length} proposals`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="tbl-empty">No matching proposals found for active filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(p => `
    <tr>
      <td class="mono fw6 text-ac" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">${esc(p.ref_no)}</td>
      <td>
        <div class="fw6" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">${esc(p.title)}</div>
        <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">Priority: ${esc(p.priority || 'Medium')} · ${fmtDate(p.created_at)}</div>
      </td>
      <td><span style="font-size:12px; color:var(--text-mid);">${esc(p.category)}</span></td>
      <td style="font-size:12px; color:var(--text-mid);">${esc(p.department)}</td>
      <td class="mono fw6">${fmtInr(p.estimated_cost)}</td>
      <td>${getStatusBadge(p.status)}</td>
      <td>
        <span class="match-score-badge" title="Surfaced precedents linked">
          ${p.precedent_count || 0} prec
        </span>
      </td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="openProposalDetail('${p.id}')">View Details</button>
      </td>
    </tr>
  `).join('');
}

/* ═══════════════════════════════════════════════════════════════════
   3. NEW / EDIT PROPOSAL + LIVE PRECEDENT GATE
   ═══════════════════════════════════════════════════════════════════ */
let _livePrecedentsDebounceTimer = null;
let _currentSurfacedPrecedents = [];
let _precedentGateAcknowledgements = {}; // precedent_id -> { relevance, reason }

function openNewProposalForm(editProposal = null) {
  switchTab('new-proposal');
  const form = $('proposal-form');
  if (form) form.reset();

  _currentSurfacedPrecedents = [];
  _precedentGateAcknowledgements = {};

  const propIdEl = $('form-prop-id');
  const titleEl  = $('form-title');

  if (editProposal) {
    if (propIdEl) propIdEl.value = editProposal.id;
    if (titleEl)  titleEl.textContent = `Edit Proposal (${editProposal.ref_no})`;
    if ($('form-category'))  $('form-category').value = editProposal.category;
    if ($('form-dept'))      $('form-dept').value = editProposal.department;
    if ($('form-cost'))      $('form-cost').value = editProposal.estimated_cost;
    if ($('form-priority'))  $('form-priority').value = editProposal.priority || 'Medium';
    if ($('form-title-inp')) $('form-title-inp').value = editProposal.title;
    if ($('form-desc'))      $('form-desc').value = editProposal.description;
    if ($('form-just'))      $('form-just').value = editProposal.justification;

    // Load existing precedent acknowledgements
    if (editProposal.precedent_links) {
      editProposal.precedent_links.forEach(l => {
        _precedentGateAcknowledgements[l.precedent_id] = {
          relevance: l.relevance,
          reason: l.reason || ''
        };
      });
    }
    triggerLivePrecedentSearch();
  } else {
    if (propIdEl) propIdEl.value = '';
    if (titleEl)  titleEl.textContent = 'Initiate Proposal';
    renderLivePrecedentsList([]);
    checkPrecedentGateCompletion();
  }
}

function onFormCategoryChanged(cat) {
  const hintEl = $('cat-hint');
  if (!hintEl) return;
  const hints = {
    'Administrative': 'Civil service rules, station allocations, administrative digitization, welfare schemes.',
    'Technical': 'VHF communications, cyber forensics, software portals, database integrations.',
    'Procurement': 'CCTV cameras, vehicles, body-worn cameras, arms, ammunition, forensic kits.',
    'Infrastructure': 'Station lockup anti-ligature renovation, baffle firing range, solar PV, barracks.',
    'Training': 'PTS Shanmugapuram curriculum, tactical simulators, specialized investigation crash courses.',
    'Operational': 'Beat patrol redeployment, tourist police kiosks, coastal security checkposts, drone surveillance.'
  };
  hintEl.textContent = hints[cat] || 'Select a category for police guidelines.';
}

function triggerLivePrecedentSearch() {
  clearTimeout(_livePrecedentsDebounceTimer);
  _livePrecedentsDebounceTimer = setTimeout(runLivePrecedentSearch, 360);
}

async function runLivePrecedentSearch() {
  const title = ($('form-title-inp')?.value || '').trim();
  const desc  = ($('form-desc')?.value || '').trim();
  const query = `${title} ${desc}`.trim();
  const cat   = $('form-category')?.value || null;
  const dept  = $('form-dept')?.value || null;
  const excludeId = $('form-prop-id')?.value || null;

  if (query.length < 5) {
    renderLivePrecedentsList([]);
    return;
  }

  try {
    const r = await fetch(`${API}/api/precedents/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, category: cat, department: dept, exclude_id: excludeId, top_k: 4 })
    });
    const d = await r.json();
    _currentSurfacedPrecedents = d.precedents || [];
    renderLivePrecedentsList(_currentSurfacedPrecedents, d.duplicate_warning);
    renderPrecedentGateChecklist(_currentSurfacedPrecedents);
  } catch (err) {
    console.error('[Precedents] Search error:', err);
  }
}

function renderLivePrecedentsList(precedents, isDuplicateWarning = false) {
  const container = $('live-precedents-list');
  const dupBanner = $('duplicate-warning');

  if (dupBanner) {
    dupBanner.style.display = isDuplicateWarning ? 'flex' : 'none';
  }

  if (!container) return;

  if (!precedents || precedents.length === 0) {
    container.innerHTML = `
      <div style="font-size:12px; color:var(--text-dim); text-align:center; padding:30px 10px;">
        No matching precedents identified yet. Type more details in title or description…
      </div>
    `;
    return;
  }

  container.innerHTML = precedents.map(p => `
    <div class="precedent-card ${p.is_duplicate ? 'duplicate-border' : ''}">
      <div class="precedent-card-top">
        <span class="precedent-ref">${esc(p.ref_no)}</span>
        <div style="display:flex; align-items:center; gap:6px;">
          ${getStatusBadge(p.status)}
          <span class="match-score-badge">${p.similarity}% match</span>
        </div>
      </div>
      <div class="precedent-card-title">${esc(p.title)}</div>
      <div style="font-size:11px; color:var(--text-dim);">
        Unit: ${esc(p.department)} · Outlay: ${fmtInr(p.estimated_cost)}
      </div>

      <div class="precedent-why">
        <strong>Why it matched:</strong> ${esc(p.explanation || 'Precedent surfaced based on lexical and domain overlap.')}
      </div>

      ${p.matched_keywords && p.matched_keywords.length > 0 ? `
        <div class="kw-tags">
          ${p.matched_keywords.map(kw => `<span class="kw-tag">${esc(kw)}</span>`).join('')}
        </div>
      ` : ''}
    </div>
  `).join('');
}

/* ── PRECEDENT GATE VERIFICATION ───────────────────────────────── */
function renderPrecedentGateChecklist(precedents) {
  const listEl = $('gate-ack-checklist');
  if (!listEl) return;

  if (!precedents || precedents.length === 0) {
    listEl.innerHTML = `<div style="font-size:11.5px; color:var(--text-dim);">No precedents requiring acknowledgement.</div>`;
    checkPrecedentGateCompletion();
    return;
  }

  listEl.innerHTML = precedents.map(p => {
    const existing = _precedentGateAcknowledgements[p.id] || { relevance: '', reason: '' };
    return `
      <div class="gate-ack-item" id="gate-item-${p.id}">
        <div class="gate-ack-row">
          <span class="mono fw6 text-ac" style="font-size:11.5px;">${esc(p.ref_no)}</span>
          <div class="gate-relevance-toggles">
            <button type="button" class="gate-toggle-btn ${existing.relevance === 'relevant' ? 'active-relevant' : ''}"
              onclick="setGateRelevance('${p.id}', 'relevant')">✓ Relevant</button>
            <button type="button" class="gate-toggle-btn ${existing.relevance === 'not_relevant' ? 'active-not-relevant' : ''}"
              onclick="setGateRelevance('${p.id}', 'not_relevant')">✗ Not Relevant</button>
          </div>
        </div>
        <div style="font-size:12px; color:var(--text); margin-bottom:6px;">${esc(p.title)}</div>
        <input type="text" class="gate-reason-inp" id="gate-reason-${p.id}"
          placeholder="Mandatory institutional reason for relevance / irrelevance…"
          value="${esc(existing.reason)}"
          oninput="setGateReason('${p.id}', this.value)" />
      </div>
    `;
  }).join('');

  checkPrecedentGateCompletion();
}

function setGateRelevance(precedentId, relevance) {
  if (!_precedentGateAcknowledgements[precedentId]) {
    _precedentGateAcknowledgements[precedentId] = { relevance: '', reason: '' };
  }
  _precedentGateAcknowledgements[precedentId].relevance = relevance;

  // Update UI toggles
  const item = $(`gate-item-${precedentId}`);
  if (item) {
    const btnRel = item.querySelector('.gate-toggle-btn:nth-child(1)');
    const btnNot = item.querySelector('.gate-toggle-btn:nth-child(2)');
    if (btnRel) btnRel.className = `gate-toggle-btn ${relevance === 'relevant' ? 'active-relevant' : ''}`;
    if (btnNot) btnNot.className = `gate-toggle-btn ${relevance === 'not_relevant' ? 'active-not-relevant' : ''}`;
  }

  checkPrecedentGateCompletion();
}

function setGateReason(precedentId, reason) {
  if (!_precedentGateAcknowledgements[precedentId]) {
    _precedentGateAcknowledgements[precedentId] = { relevance: '', reason: '' };
  }
  _precedentGateAcknowledgements[precedentId].reason = reason;
  checkPrecedentGateCompletion();
}

function checkPrecedentGateCompletion() {
  const pill    = $('gate-status-pill');
  const btnSub  = $('btn-submit-proposal');
  const msgEl   = $('gate-block-msg');

  if (_currentSurfacedPrecedents.length === 0) {
    if (pill) { pill.className = 'status-pill badge-approved'; pill.textContent = 'Gate Cleared'; }
    if (btnSub) btnSub.disabled = false;
    if (msgEl)  msgEl.style.display = 'none';
    return true;
  }

  let allCompleted = true;
  for (const p of _currentSurfacedPrecedents) {
    const ack = _precedentGateAcknowledgements[p.id];
    if (!ack || !ack.relevance || !ack.reason || !ack.reason.trim()) {
      allCompleted = false;
      break;
    }
  }

  if (allCompleted) {
    if (pill) { pill.className = 'status-pill badge-approved'; pill.textContent = 'Gate Cleared'; }
    if (btnSub) btnSub.disabled = false;
    if (msgEl)  msgEl.style.display = 'none';
  } else {
    if (pill) { pill.className = 'status-pill badge-returned'; pill.textContent = 'Review Required'; }
    if (btnSub) btnSub.disabled = true;
    if (msgEl)  msgEl.style.display = 'inline';
  }

  return allCompleted;
}

/* ── FORM ACTIONS: SAVE DRAFT OR SUBMIT ────────────────────────── */
async function saveAsDraft() {
  const prop = await createOrUpdateProposal('Draft');
  if (prop) {
    toast(`Proposal ${prop.ref_no} saved in Draft status.`, 'ok');
    openProposalDetail(prop.id);
  }
}

async function submitProposalForm() {
  if (!checkPrecedentGateCompletion()) {
    toast('Precedent Gate Incomplete: All surfaced precedents must be acknowledged with a reason.', 'err');
    return;
  }

  showLoad('Validating precedent acknowledgements and submitting proposal…');
  try {
    const prop = await createOrUpdateProposal('Draft');
    if (!prop) { hideLoad(); return; }

    // Save all precedent acknowledgements to backend
    const actorInfo = getCurrentActor();
    for (const p of _currentSurfacedPrecedents) {
      const ack = _precedentGateAcknowledgements[p.id];
      if (ack && ack.relevance) {
        await fetch(`${API}/api/proposals/${prop.id}/precedents/ack`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            precedent_id: p.id,
            relevance: ack.relevance,
            reason: ack.reason,
            actor: actorInfo.actor
          })
        });
      }
    }

    // Now execute transition to Submitted
    const res = await fetch(`${API}/api/proposals/${prop.id}/transition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_status: 'Submitted',
        actor: actorInfo.actor,
        role: actorInfo.role,
        note: 'Submitted following Precedent Gate appraisal'
      })
    });
    const d = await res.json();
    hideLoad();

    if (!res.ok) {
      toast(`Submission rejected: ${d.error}`, 'err', 4000);
      return;
    }

    toast(`Proposal ${prop.ref_no} submitted successfully for review!`, 'ok');
    openProposalDetail(prop.id);
  } catch (err) {
    hideLoad();
    toast(`Submission error: ${err}`, 'err');
  }
}

async function createOrUpdateProposal(initialStatus = 'Draft') {
  const propId   = $('form-prop-id')?.value || '';
  const category = $('form-category')?.value || '';
  const dept     = $('form-dept')?.value || '';
  const cost     = parseFloat($('form-cost')?.value || '0');
  const priority = $('form-priority')?.value || 'Medium';
  const title    = $('form-title-inp')?.value || '';
  const desc     = $('form-desc')?.value || '';
  const just     = $('form-just')?.value || '';
  const actorInfo = getCurrentActor();

  const payload = {
    category, department: dept, estimated_cost: cost,
    priority, title, description: desc, justification: just,
    created_by: actorInfo.actor, role: actorInfo.role
  };

  if (propId) {
    // Update
    const r = await fetch(`${API}/api/proposals/${propId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if (!r.ok) { toast(`Update failed: ${d.error}`, 'err'); return null; }
    return d.proposal;
  } else {
    // Create new
    const r = await fetch(`${API}/api/proposals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if (!r.ok) { toast(`Creation failed: ${d.error}`, 'err'); return null; }
    return d.proposal;
  }
}

/* ═══════════════════════════════════════════════════════════════════
   4. PROPOSAL DETAIL VIEW, STEPPER, ACTIONS & AUDIT CHAIN
   ═══════════════════════════════════════════════════════════════════ */
let _activeProposal = null;

async function openProposalDetail(propId) {
  showLoad('Loading proposal details and precedent pulse…');
  try {
    const r = await fetch(`${API}/api/proposals/${propId}`);
    const d = await r.json();
    hideLoad();

    if (!r.ok || !d.proposal) {
      toast('Proposal not found.', 'err');
      return;
    }

    _activeProposal = d.proposal;
    renderProposalDetailView(_activeProposal);
    switchTab('proposal-detail');
  } catch (err) {
    hideLoad();
    toast(`Failed to load proposal: ${err}`, 'err');
  }
}

function renderProposalDetailView(p) {
  if ($('detail-ref'))       $('detail-ref').textContent = p.ref_no;
  if ($('detail-title'))     $('detail-title').textContent = p.title;
  if ($('detail-cat-tag'))   $('detail-cat-tag').textContent = `${p.category} · ${p.department}`;
  if ($('detail-desc'))      $('detail-desc').textContent = p.description;
  if ($('detail-just'))      $('detail-just').textContent = p.justification;
  if ($('detail-cost'))      $('detail-cost').textContent = fmtInr(p.estimated_cost);
  if ($('detail-dept'))      $('detail-dept').textContent = p.department;
  if ($('detail-priority'))  $('detail-priority').textContent = p.priority || 'Medium';
  if ($('detail-created-by')) $('detail-created-by').textContent = p.created_by || 'Dealing Assistant';
  if ($('detail-dates'))     $('detail-dates').textContent = `Initiated: ${fmtDate(p.created_at)} · Updated: ${fmtDate(p.updated_at)}`;

  const pill = $('detail-status-pill');
  if (pill) pill.outerHTML = getStatusBadge(p.status);

  // Render Visual Status Stepper
  renderStatusStepper(p.status);

  // Render Action Buttons Bar (strictly based on role and status)
  renderDetailActionButtons(p);

  // Render Subtabs Data
  renderDetailPrecedents(p);
  renderDetailRemarks(p.remarks || []);
  renderDetailDecision(p);
  renderDetailOutcome(p);
  renderDetailAuditTrail(p.history || []);

  switchSubtab('overview');
}

/* ── Visual Stepper ─────────────────────────────────────────────── */
function renderStatusStepper(currentStatus) {
  const container = $('status-stepper');
  if (!container) return;

  const steps = [
    'Draft',
    'Submitted',
    'Under Review',
    currentStatus === 'Rejected' ? 'Rejected' : (currentStatus === 'Returned for Revision' ? 'Returned' : 'Approved'),
    'In Implementation',
    'Implemented',
    'Closed'
  ];

  const statusOrder = {
    'Draft': 0,
    'Submitted': 1,
    'Under Review': 2,
    'Returned for Revision': 3,
    'Approved': 3,
    'Rejected': 3,
    'In Implementation': 4,
    'Implemented': 5,
    'Closed': 6
  };

  const currentIdx = statusOrder[currentStatus] ?? 0;

  container.innerHTML = steps.map((s, idx) => {
    let cls = '';
    if (idx < currentIdx) cls = 'step-done';
    else if (idx === currentIdx) {
      cls = (currentStatus === 'Rejected') ? 'step-rejected' : 'step-active';
    }

    return `
      <div class="step-item ${cls}">
        <div class="step-circle">${idx < currentIdx ? '✓' : idx + 1}</div>
        <div class="step-label">${esc(s)}</div>
      </div>
    `;
  }).join('');
}

/* ── Role-Governed Action Buttons ───────────────────────────────── */
function renderDetailActionButtons(p) {
  const bar = $('detail-action-buttons');
  if (!bar) return;

  const role = _currentRole; // 'initiator', 'reviewer', 'approver', 'auditor'
  const status = p.status;
  const buttons = [];

  // Initiator Actions
  if (role === 'initiator') {
    if (status === 'Draft') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="openNewProposalForm(_activeProposal)">Edit Draft</button>`);
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('Submitted', 'Submitted after Precedent Gate clearance')">Submit Proposal</button>`);
    } else if (status === 'Returned for Revision') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="openNewProposalForm(_activeProposal)">Revise Proposal</button>`);
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('Submitted', 'Resubmitted after addressing reviewer remarks')">Resubmit</button>`);
    } else if (status === 'Approved') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('In Implementation', 'Procurement / works rollout initiated')">Start Implementation</button>`);
    } else if (status === 'In Implementation') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('Implemented', 'All deliverables received and verified')">Mark Implemented</button>`);
    }
  }

  // Reviewer Actions
  if (role === 'reviewer') {
    if (status === 'Submitted') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('Under Review', 'Sub-divisional scrutiny commenced')">Begin Review</button>`);
    } else if (status === 'Under Review') {
      buttons.push(`<button class="btn btn-secondary btn-sm" onclick="openDecisionModal('Return for Revision')">Return for Revision</button>`);
    } else if (status === 'Approved') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('In Implementation', 'Implementation works cleared to commence')">Start Implementation</button>`);
    } else if (status === 'Implemented' || status === 'Rejected') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="openOutcomeModal()">Record Outcome & Close</button>`);
    }
  }

  // Approving Authority Actions
  if (role === 'approver') {
    if (status === 'Submitted') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="transitionActiveProposal('Under Review', 'Taken up for sanction scrutiny')">Take Up Review</button>`);
    } else if (status === 'Under Review') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="openDecisionModal('Approve')">Record Decision & Sanction</button>`);
      buttons.push(`<button class="btn btn-secondary btn-sm" onclick="openDecisionModal('Return for Revision')">Return for Revision</button>`);
    } else if (status === 'Implemented' || status === 'Rejected') {
      buttons.push(`<button class="btn btn-primary btn-sm" onclick="openOutcomeModal()">Record Outcome & Close</button>`);
    }
  }

  // Auditor Actions (Always verify trail)
  if (role === 'auditor') {
    buttons.push(`<button class="btn btn-secondary btn-sm" onclick="verifyCurrentAuditTrail()">Verify Integrity Chain</button>`);
  }

  bar.innerHTML = buttons.join('');
}

async function transitionActiveProposal(toStatus, defaultNote = '') {
  if (!_activeProposal) return;
  const actorInfo = getCurrentActor();

  showLoad(`Advancing status to ${toStatus}…`);
  try {
    const r = await fetch(`${API}/api/proposals/${_activeProposal.id}/transition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_status: toStatus,
        actor: actorInfo.actor,
        role: actorInfo.role,
        note: defaultNote
      })
    });
    const d = await r.json();
    hideLoad();

    if (!r.ok) {
      toast(`Transition refused: ${d.error}`, 'err', 4000);
      return;
    }

    toast(`Proposal successfully transitioned to ${toStatus}`, 'ok');
    openProposalDetail(_activeProposal.id);
  } catch (err) {
    hideLoad();
    toast(`Transition failed: ${err}`, 'err');
  }
}

/* ── Precedents Subtab in Detail ────────────────────────────────── */
function renderDetailPrecedents(p) {
  const pulseLine  = $('detail-pulse-line');
  const pulsePills = $('detail-pulse-pills');
  const listEl     = $('detail-precedents-list');

  const pulse = p.precedent_pulse || {};
  if (pulseLine) pulseLine.textContent = pulse.summary_line || 'No historical precedents identified.';

  if (pulsePills) {
    pulsePills.innerHTML = `
      <span class="pulse-pill">Total Matches: <strong>${pulse.total || 0}</strong></span>
      <span class="pulse-pill">Past Approved: <strong>${pulse.approved || 0}</strong></span>
      <span class="pulse-pill">Past Rejected: <strong>${pulse.rejected || 0}</strong></span>
      <span class="pulse-pill">Avg Decision Turnaround: <strong>${pulse.avg_decision_days || 18} days</strong></span>
    `;
  }

  if (!listEl) return;
  const links = p.precedent_links || [];

  if (links.length === 0) {
    listEl.innerHTML = `<div style="font-size:12.5px; color:var(--text-dim); padding:20px;">No precedents linked to this proposal.</div>`;
    return;
  }

  listEl.innerHTML = links.map(l => `
    <div class="precedent-card">
      <div class="precedent-card-top">
        <span class="precedent-ref">${esc(l.precedent_ref || l.precedent_id)}</span>
        <div style="display:flex; align-items:center; gap:6px;">
          ${getStatusBadge(l.precedent_status || 'Past Record')}
          <span class="match-score-badge">${l.similarity}% similarity</span>
          <span class="status-pill ${l.relevance === 'relevant' ? 'badge-approved' : 'badge-returned'}">
            ${l.relevance === 'relevant' ? 'Acknowledged: Relevant' : 'Acknowledged: Not Relevant'}
          </span>
        </div>
      </div>
      <div class="precedent-card-title">${esc(l.precedent_title || 'Past proposal')}</div>
      <div style="font-size:12px; color:var(--text-mid); margin-top:4px;">
        Unit: ${esc(l.precedent_department || '—')} · Outlay: ${fmtInr(l.precedent_cost)}
      </div>
      <div class="precedent-why" style="margin-top:8px;">
        <strong>Initiator Acknowledged Reason:</strong> ${esc(l.reason || 'None provided')}
        <div style="font-size:11px; color:var(--text-dim); margin-top:3px;">
          Acknowledged by ${esc(l.acknowledged_by || 'Initiator')} on ${fmtDate(l.acknowledged_at)}
        </div>
      </div>
    </div>
  `).join('');
}

/* ── Remarks Subtab ─────────────────────────────────────────────── */
function renderDetailRemarks(remarks) {
  const countEl = $('count-remarks');
  if (countEl) countEl.textContent = remarks.length;

  const container = $('detail-remarks-thread');
  if (!container) return;

  if (remarks.length === 0) {
    container.innerHTML = `<div style="font-size:12.5px; color:var(--text-dim); padding:16px;">No remarks or observations recorded yet.</div>`;
    return;
  }

  container.innerHTML = remarks.map(r => `
    <div class="remark-card">
      <div class="remark-top">
        <div class="remark-author-info">
          <span class="remark-author">${esc(r.author)}</span>
          <span class="remark-role-tag">${esc(r.role)}</span>
        </div>
        <span class="remark-date">${fmtTime(r.timestamp)}</span>
      </div>
      <div class="remark-content">${esc(r.text)}</div>
    </div>
  `).join('');
}

async function submitAddRemark() {
  const txtEl = $('inp-remark-text');
  const text  = (txtEl?.value || '').trim();
  if (!text || !_activeProposal) return;

  const actorInfo = getCurrentActor();
  showLoad('Adding officer observation…');
  try {
    const r = await fetch(`${API}/api/proposals/${_activeProposal.id}/remarks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        author: actorInfo.actor,
        role: actorInfo.role,
        text: text
      })
    });
    const d = await r.json();
    hideLoad();
    if (txtEl) txtEl.value = '';
    toast('Observation added to official record.', 'ok');
    openProposalDetail(_activeProposal.id);
  } catch (err) {
    hideLoad();
    toast(`Failed to add remark: ${err}`, 'err');
  }
}

/* ── Decision Subtab ────────────────────────────────────────────── */
function renderDetailDecision(p) {
  const area = $('detail-decision-area');
  if (!area) return;

  const dec = p.latest_decision;
  if (!dec) {
    area.innerHTML = `
      <div class="form-card" style="text-align:center; padding:30px;">
        <div style="font-size:14px; font-weight:600; color:var(--text-mid);">No formal decision recorded yet.</div>
        <p style="font-size:12px; color:var(--text-dim); margin-top:6px;">
          Decisions are recorded by the Approving Authority (SP / SSP / DGP) at the 'Under Review' stage.
        </p>
      </div>
    `;
    return;
  }

  area.innerHTML = `
    <div class="form-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px;">
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Decision Order</span>
          <h3 style="font-size:18px; font-weight:700; color:var(--accent); margin-top:2px;">${esc(dec.decision_type)}</h3>
        </div>
        <span class="status-pill ${dec.decision_type.includes('Approve') ? 'badge-approved' : 'badge-rejected'}">
          ${esc(dec.decision_type)}
        </span>
      </div>

      <div class="form-row" style="margin-bottom:14px;">
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Deciding Authority</span>
          <div style="font-size:13.5px; font-weight:600; color:var(--text);">${esc(dec.decided_by)}</div>
        </div>
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Decision Date</span>
          <div style="font-size:13.5px; color:var(--text);">${fmtTime(dec.timestamp)}</div>
        </div>
      </div>

      ${dec.sanction_order_no ? `
        <div class="form-row" style="margin-bottom:14px;">
          <div>
            <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Sanction Order Number</span>
            <div class="mono fw6 text-ac" style="font-size:14px;">${esc(dec.sanction_order_no)}</div>
          </div>
          <div>
            <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Sanctioned Outlay</span>
            <div style="font-size:16px; font-weight:700; color:var(--green);">${fmtInr(dec.sanctioned_amount)}</div>
          </div>
        </div>
      ` : ''}

      <div style="margin-bottom:14px;">
        <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Reason & Grounds</span>
        <p style="font-size:13.5px; color:var(--text); line-height:1.5; margin-top:4px;">${esc(dec.reason)}</p>
      </div>

      ${dec.conditions ? `
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Conditions of Sanction</span>
          <p style="font-size:13px; color:var(--text-mid); line-height:1.5; margin-top:4px;">${esc(dec.conditions)}</p>
        </div>
      ` : ''}
    </div>
  `;
}

/* ── Outcome Subtab ─────────────────────────────────────────────── */
function renderDetailOutcome(p) {
  const area = $('detail-outcome-area');
  if (!area) return;

  const out = p.latest_outcome;
  if (!out) {
    area.innerHTML = `
      <div class="form-card" style="text-align:center; padding:30px;">
        <div style="font-size:14px; font-weight:600; color:var(--text-mid);">Implementation outcome not yet recorded.</div>
        <p style="font-size:12px; color:var(--text-dim); margin-top:6px;">
          Once implementation is completed, the post-sanction summary and institutional lessons learned are logged here.
        </p>
      </div>
    `;
    return;
  }

  area.innerHTML = `
    <div class="form-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px;">
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Implementation Result</span>
          <h3 style="font-size:17px; font-weight:700; color:var(--text); margin-top:2px;">${esc(out.implementation_status)}</h3>
        </div>
        <span class="status-pill badge-implemented">${esc(out.implementation_status)}</span>
      </div>

      <div class="form-row" style="margin-bottom:14px;">
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Actual Cost Incurred</span>
          <div style="font-size:18px; font-weight:700; color:var(--accent);">${fmtInr(out.actual_cost)}</div>
        </div>
        <div>
          <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Completion Date</span>
          <div style="font-size:13.5px; color:var(--text);">${esc(out.completion_date || '—')}</div>
        </div>
      </div>

      <div style="margin-bottom:16px;">
        <span style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Outcome Summary</span>
        <p style="font-size:13.5px; color:var(--text); line-height:1.55; margin-top:4px;">${esc(out.outcome_summary)}</p>
      </div>

      <div style="background:rgba(201, 169, 97, 0.08); border-left:3px solid var(--accent); padding:12px 16px; border-radius:0 8px 8px 0;">
        <span style="font-size:11.5px; font-weight:700; color:var(--accent); text-transform:uppercase;">Indexed Institutional Lesson Learned</span>
        <p style="font-size:13px; color:var(--text); line-height:1.5; margin-top:4px;">${esc(out.lessons_learned)}</p>
      </div>
    </div>
  `;
}

/* ── Audit Trail Subtab ─────────────────────────────────────────── */
function renderDetailAuditTrail(history) {
  const tbody = $('detail-audit-tbody');
  if (!tbody) return;

  if (history.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="tbl-empty">No history entries logged.</td></tr>`;
    return;
  }

  tbody.innerHTML = history.map(h => `
    <tr>
      <td class="mono fw6 text-ac">#${h.id}</td>
      <td><span style="font-size:12px; color:var(--text-dim);">${esc(h.from_status || 'Genesis')}</span></td>
      <td>${getStatusBadge(h.to_status)}</td>
      <td>
        <div class="fw6" style="font-size:12.5px;">${esc(h.actor)}</div>
        <div style="font-size:11px; color:var(--text-dim);">${esc(h.role)}</div>
      </td>
      <td style="font-size:12.5px; max-width:240px;">${esc(h.note || '—')}</td>
      <td style="font-size:11.5px; color:var(--text-mid);">${fmtTime(h.timestamp)}</td>
      <td><span class="hash-badge" title="${esc(h.prev_hash)}">${esc(h.prev_hash.slice(0, 14))}…</span></td>
      <td><span class="hash-badge" title="${esc(h.hash)}">${esc(h.hash.slice(0, 14))}…</span></td>
    </tr>
  `).join('');
}

async function verifyCurrentAuditTrail() {
  if (!_activeProposal) return;
  showLoad('Verifying cryptographic SHA-256 hash chain…');
  try {
    const r = await fetch(`${API}/api/proposals/${_activeProposal.id}/audit/verify`);
    const d = await r.json();
    hideLoad();

    const banner = $('audit-verify-banner');
    const titleEl = $('audit-verify-title');
    const msgEl   = $('audit-verify-msg');

    if (d.valid) {
      if (banner) banner.className = 'verify-status-banner verify-valid';
      if (titleEl) titleEl.textContent = `SHA-256 Hash Chain Valid: Verified ${d.chain_length} Blocks`;
      if (msgEl) msgEl.textContent = d.message;
      toast('Cryptographic integrity confirmed: 100% authentic and tamper-evident.', 'ok');
    } else {
      if (banner) banner.className = 'verify-status-banner verify-invalid';
      if (titleEl) titleEl.textContent = `TAMPER DETECTED at Block ID #${d.tamper_detected_at}!`;
      if (msgEl) msgEl.textContent = d.message;
      toast('Audit warning: Hash mismatch detected!', 'err');
    }
  } catch (err) {
    hideLoad();
    toast(`Verification error: ${err}`, 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   5. DECISION BRIEF PDF DOWNLOAD
   ═══════════════════════════════════════════════════════════════════ */
function downloadDecisionBrief() {
  if (!_activeProposal) return;
  toast('Generating executive Decision Brief PDF…', 'info');
  window.location.href = `${API}/api/proposals/${_activeProposal.id}/brief`;
}

function downloadBriefFor(propId) {
  toast('Generating Decision Brief PDF…', 'info');
  window.location.href = `${API}/api/proposals/${propId}/brief`;
}

async function loadBriefsList() {
  const tbody = $('briefs-tbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="6" class="tbl-empty">Loading proposals for brief generation…</td></tr>`;

  try {
    const r = await fetch(`${API}/api/proposals?limit=100`);
    const d = await r.json();
    const props = d.proposals || [];

    if (props.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="tbl-empty">No proposals available.</td></tr>`;
      return;
    }

    tbody.innerHTML = props.map(p => `
      <tr>
        <td class="mono fw6 text-ac" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">${esc(p.ref_no)}</td>
        <td>
          <div class="fw6" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">${esc(p.title)}</div>
          <div style="font-size:11px; color:var(--text-dim);">${fmtInr(p.estimated_cost)}</div>
        </td>
        <td><span style="font-size:12px; color:var(--text-mid);">${esc(p.category)}</span></td>
        <td style="font-size:12px; color:var(--text-mid);">${esc(p.department)}</td>
        <td>${getStatusBadge(p.status)}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="downloadBriefFor('${p.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <span>Download Brief (PDF)</span>
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="tbl-empty">Failed to load proposals list.</td></tr>`;
  }
}

/* ═══════════════════════════════════════════════════════════════════
   6. MODALS MANAGEMENT: DECISION & OUTCOME
   ═══════════════════════════════════════════════════════════════════ */
function openModal(id) {
  const m = $(id); if (m) m.style.display = 'flex';
}
function closeModal(id) {
  const m = $(id); if (m) m.style.display = 'none';
}

function openDecisionModal(preselectType = 'Approve') {
  const sel = $('modal-dec-type');
  if (sel) sel.value = preselectType;
  onDecisionTypeChanged(preselectType);
  openModal('modal-decision');
}

function onDecisionTypeChanged(type) {
  const fields = $('modal-dec-sanction-fields');
  if (fields) {
    fields.style.display = type.startsWith('Approve') ? 'block' : 'none';
  }
}

async function submitDecisionModal() {
  if (!_activeProposal) return;
  const decType = $('modal-dec-type')?.value;
  const reason  = ($('modal-dec-reason')?.value || '').trim();
  const sanctNo = $('modal-dec-sanction-no')?.value || null;
  const sanctAmt= $('modal-dec-amount')?.value || null;
  const conds   = $('modal-dec-conditions')?.value || null;
  const actorInfo = getCurrentActor();

  showLoad('Recording formal decision…');
  try {
    const r = await fetch(`${API}/api/proposals/${_activeProposal.id}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        decision_type: decType,
        decided_by: actorInfo.actor,
        reason: reason,
        sanction_order_no: sanctNo,
        sanctioned_amount: sanctAmt,
        conditions: conds,
        role: actorInfo.role
      })
    });
    const d = await r.json();
    hideLoad();
    closeModal('modal-decision');

    if (!r.ok) {
      toast(`Decision failed: ${d.error}`, 'err', 4000);
      return;
    }

    toast(`Decision recorded: ${decType}`, 'ok');
    openProposalDetail(_activeProposal.id);
  } catch (err) {
    hideLoad();
    toast(`Decision error: ${err}`, 'err');
  }
}

function openOutcomeModal() {
  openModal('modal-outcome');
}

async function submitOutcomeModal() {
  if (!_activeProposal) return;
  const status   = $('modal-out-status')?.value;
  const cost     = $('modal-out-cost')?.value || null;
  const date     = $('modal-out-date')?.value || null;
  const summary  = ($('modal-out-summary')?.value || '').trim();
  const lessons  = ($('modal-out-lessons')?.value || '').trim();
  const actorInfo= getCurrentActor();

  showLoad('Recording implementation outcome and closing proposal…');
  try {
    // 1. Record outcome
    const r1 = await fetch(`${API}/api/proposals/${_activeProposal.id}/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        implementation_status: status,
        actual_cost: cost,
        completion_date: date,
        outcome_summary: summary,
        lessons_learned: lessons,
        actor: actorInfo.actor,
        role: actorInfo.role
      })
    });

    // 2. Transition proposal to Closed
    const r2 = await fetch(`${API}/api/proposals/${_activeProposal.id}/transition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_status: 'Closed',
        actor: actorInfo.actor,
        role: actorInfo.role,
        note: `Proposal closed with outcome: ${status}`
      })
    });

    hideLoad();
    closeModal('modal-outcome');

    toast('Implementation outcome and lessons learned saved. Proposal closed.', 'ok');
    openProposalDetail(_activeProposal.id);
  } catch (err) {
    hideLoad();
    toast(`Outcome save error: ${err}`, 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   7. ORDERS ARCHIVE & INGESTION
   ═══════════════════════════════════════════════════════════════════ */
async function loadArchive() {
  const tbody = $('archive-tbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty">Loading archived documents…</td></tr>`;

  try {
    const r = await fetch(`${API}/api/documents`);
    const d = await r.json();
    const docs = d.documents || [];

    const badge = $('badge-docs');
    if (badge) badge.textContent = docs.length;

    if (docs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty">No documents in archive. Upload past orders above.</td></tr>`;
      return;
    }

    tbody.innerHTML = docs.map(doc => `
      <tr>
        <td class="fw6 text-ac">${esc(doc.filename)}</td>
        <td>${doc.page_count || 1}</td>
        <td>${(doc.char_count || 0).toLocaleString()} chars</td>
        <td><span class="match-score-badge">${doc.page_count * 2 || 2} chunks</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="deleteArchiveDoc('${doc.id}')">Delete</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty">Failed to load archive.</td></tr>`;
  }
}

async function submitIngestFile() {
  const fileInput = $('ingest-file');
  if (!fileInput || !fileInput.files[0]) return;

  const file = fileInput.files[0];
  const dept = $('ingest-dept')?.value || 'Police Headquarters';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('department', dept);

  showLoad(`Ingesting & extracting text from ${file.name}…`);
  try {
    const r = await fetch(`${API}/api/ingest`, {
      method: 'POST',
      body: formData
    });
    const d = await r.json();
    hideLoad();

    if (!r.ok) {
      toast(`Ingestion error: ${d.error}`, 'err', 4000);
      return;
    }

    toast(`Successfully ingested ${d.filename} into Archive.`, 'ok');
    fileInput.value = '';
    loadArchive();
  } catch (err) {
    hideLoad();
    toast(`Ingestion failed: ${err}`, 'err');
  }
}

async function deleteArchiveDoc(docId) {
  if (!confirm('Are you sure you want to remove this document from the archive?')) return;
  showLoad('Removing document…');
  try {
    const r = await fetch(`${API}/api/documents/${docId}`, { method: 'DELETE' });
    hideLoad();
    toast('Document removed from archive.', 'ok');
    loadArchive();
  } catch (err) {
    hideLoad();
    toast('Failed to delete document.', 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   8. PRECEDENT QUERY / CHATBOT SEARCH
   ═══════════════════════════════════════════════════════════════════ */
function setQuickQuery(txt) {
  const inp = $('query-input');
  if (inp) {
    inp.value = txt;
    executePrecedentQuery();
  }
}

async function executePrecedentQuery() {
  const inp = $('query-input');
  const query = (inp?.value || '').trim();
  if (!query) return;

  showLoad('Retrieving historical precedents and synthesizing advice…');
  try {
    const r = await fetch(`${API}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const d = await r.json();
    hideLoad();

    const area = $('query-results-area');
    if (area) area.style.display = 'block';

    // Pulse
    const pulse = d.pulse || {};
    if ($('query-pulse-line')) $('query-pulse-line').textContent = pulse.summary_line || 'Precedent search completed.';
    if ($('query-pulse-pills')) {
      $('query-pulse-pills').innerHTML = `
        <span class="pulse-pill">Matched Precedents: <strong>${pulse.total || 0}</strong></span>
        <span class="pulse-pill">Past Approved: <strong>${pulse.approved || 0}</strong></span>
        <span class="pulse-pill">Past Rejected: <strong>${pulse.rejected || 0}</strong></span>
      `;
    }

    // AI synthesis
    if ($('query-answer')) $('query-answer').textContent = d.answer || '—';

    // Precedent cards
    const precList = $('query-precedents-list');
    if (precList) {
      const precs = d.precedents || [];
      if (precs.length === 0) {
        precList.innerHTML = `<div style="font-size:12.5px; color:var(--text-dim);">No past proposals matched this query text.</div>`;
      } else {
        precList.innerHTML = precs.map(p => `
          <div class="precedent-card" style="cursor:pointer;" onclick="openProposalDetail('${p.id}')">
            <div class="precedent-card-top">
              <span class="precedent-ref">${esc(p.ref_no)}</span>
              <div style="display:flex; align-items:center; gap:6px;">
                ${getStatusBadge(p.status)}
                <span class="match-score-badge">${p.similarity}% match</span>
              </div>
            </div>
            <div class="precedent-card-title">${esc(p.title)}</div>
            <div style="font-size:12px; color:var(--text-mid);">
              Unit: ${esc(p.department)} · Outlay: ${fmtInr(p.estimated_cost)}
            </div>
            <div class="precedent-why" style="margin-top:8px;">
              ${esc(p.explanation || p.decision_reason || 'Historical proposal indexed in repository.')}
            </div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    hideLoad();
    toast(`Search error: ${err}`, 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   9. SEED DEMO DATA RESET (FOR PRESENTATION)
   ═══════════════════════════════════════════════════════════════════ */
async function seedDatabaseDemo() {
  if (!confirm('Reset database with 50+ realistic past Puducherry Police proposals for the hackathon demo?')) return;
  showLoad('Resetting database and generating 50+ realistic police proposals with verified SHA-256 chains…');
  try {
    const r = await fetch(`${API}/api/proposals/seed`, { method: 'POST' });
    const d = await r.json();
    hideLoad();
    toast('Database reseeded successfully with full precedent history!', 'ok', 3500);
    initDashboard();
    loadProposals();
  } catch (err) {
    hideLoad();
    toast('Failed to reseed database.', 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   INITIALIZATION
   ═══════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  applyAmbientMode(_ambientMode);
  initRole();
  checkHealth();
  initDashboard();

  // Poll health every 30s
  setInterval(checkHealth, 30000);
});

/* ═══════════════════════════════════════════════════════════════════
   10. IMAGE OCR
   ═══════════════════════════════════════════════════════════════════ */
let _ocrFile = null;
let _ocrResultText = '';

function handleOcrDrop(event) {
  event.preventDefault();
  const zone = event.currentTarget;
  zone.style.borderColor = 'var(--border-accent)';
  zone.style.background = 'var(--surface)';
  const file = event.dataTransfer.files[0];
  if (file) setOcrFile(file);
}

function handleOcrFileSelect(input) {
  if (input.files[0]) setOcrFile(input.files[0]);
}

function setOcrFile(file) {
  _ocrFile = file;
  const info = $('ocr-file-info');
  const nameEl = $('ocr-file-name');
  const sizeEl = $('ocr-file-size');
  const stats  = $('ocr-stats');

  if (info) info.style.display = 'flex';
  if (nameEl) nameEl.textContent = file.name;
  if (sizeEl) sizeEl.textContent = `${(file.size / 1024).toFixed(1)} KB`;
  if (stats) stats.style.display = 'none';

  // Reset result
  const result = $('ocr-result-text');
  if (result) { result.value = ''; }
  _ocrResultText = '';
}

async function runOcr() {
  if (!_ocrFile) { toast('Please select an image or PDF first.', 'err'); return; }

  const btn = $('ocr-run-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Processing…'; }

  showLoad(`Running OCR on ${_ocrFile.name}… This may take a moment.`);

  try {
    const formData = new FormData();
    formData.append('file', _ocrFile);

    const r = await fetch(`${API}/api/ocr`, { method: 'POST', body: formData });
    const d = await r.json();
    hideLoad();

    if (!r.ok) {
      toast(`OCR Error: ${d.error}`, 'err', 5000);
      return;
    }

    _ocrResultText = d.text || '';
    const result = $('ocr-result-text');
    if (result) result.value = _ocrResultText;

    // Update stats
    const stats = $('ocr-stats');
    if (stats) stats.style.display = 'block';
    if ($('ocr-stat-chars')) $('ocr-stat-chars').textContent = (d.char_count || 0).toLocaleString();
    if ($('ocr-stat-pages')) $('ocr-stat-pages').textContent = d.page_count || 1;
    if ($('ocr-stat-conf')) $('ocr-stat-conf').textContent = d.confidence ? `${Math.round(d.confidence * 100)}%` : '—';

    const badge = $('ocr-engine-badge');
    if (badge) { badge.textContent = d.ocr_engine || 'Tesseract'; badge.style.display = 'inline-block'; }

    toast(`OCR complete — ${(d.char_count || 0).toLocaleString()} chars extracted`, 'ok');
  } catch (err) {
    hideLoad();
    toast(`OCR failed: ${err}`, 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Run OCR'; }
  }
}

function ocrCopyText() {
  if (!_ocrResultText) { toast('No text to copy. Run OCR first.', 'err'); return; }
  navigator.clipboard.writeText(_ocrResultText).then(() => {
    toast('Extracted text copied to clipboard.', 'ok');
  }).catch(() => {
    const ta = $('ocr-result-text');
    if (ta) { ta.select(); document.execCommand('copy'); }
    toast('Text copied.', 'ok');
  });
}

function ocrDownloadText() {
  if (!_ocrResultText) { toast('No text to download. Run OCR first.', 'err'); return; }
  const baseName = _ocrFile ? _ocrFile.name.replace(/\.[^.]+$/, '') : 'ocr_result';
  const blob = new Blob([_ocrResultText], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `${baseName}_ocr.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

async function ocrAddToMemory() {
  if (!_ocrResultText || !_ocrFile) { toast('Run OCR first before saving to memory.', 'err'); return; }
  showLoad('Saving OCR text to Memory & Knowledge Base…');
  try {
    // Create a text file from the OCR output and upload to memory
    const baseName = _ocrFile.name.replace(/\.[^.]+$/, '') + '_ocr.txt';
    const blob = new Blob([_ocrResultText], { type: 'text/plain' });
    const file = new File([blob], baseName, { type: 'text/plain' });

    const formData = new FormData();
    formData.append('file', file);

    const r = await fetch(`${API}/api/memory/upload`, { method: 'POST', body: formData });
    const d = await r.json();
    hideLoad();

    if (!r.ok) { toast(`Memory save error: ${d.error}`, 'err'); return; }
    toast(`OCR text saved to Memory as "${baseName}"`, 'ok');
  } catch (err) {
    hideLoad();
    toast(`Failed to save to memory: ${err}`, 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   11. DOCUMENT GENERATOR
   ═══════════════════════════════════════════════════════════════════ */
let _dgProposals = [];
let _dgSelectedProp = null;

async function initDocgen() {
  // Load proposals into dropdown
  try {
    if (_dgProposals.length === 0) {
      const r = await fetch(`${API}/api/proposals?limit=200`);
      const d = await r.json();
      _dgProposals = d.proposals || [];
    }
    const sel = $('dg-prop-select');
    if (sel) {
      // Clear and repopulate
      sel.innerHTML = '<option value="">— Free-form document —</option>';
      _dgProposals.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${esc(p.ref_no)} — ${esc(p.title)} [${esc(p.status)}]`;
        sel.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn('[DocGen] Could not load proposals:', err);
  }
}

function onDocgenProposalSelected(propId) {
  const preview = $('dg-prop-preview');
  if (!propId) {
    _dgSelectedProp = null;
    if (preview) preview.innerHTML = 'No proposal selected. Choose one from the dropdown or create a free-form document.';
    return;
  }

  _dgSelectedProp = _dgProposals.find(p => p.id === propId) || null;
  if (!_dgSelectedProp || !preview) return;

  const p = _dgSelectedProp;
  preview.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:8px;">
      <div style="display:flex; align-items:center; gap:8px;">
        <span class="mono fw6 text-ac" style="font-size:13px;">${esc(p.ref_no)}</span>
        ${getStatusBadge(p.status)}
      </div>
      <div style="font-size:14px; font-weight:600; color:var(--text);">${esc(p.title)}</div>
      <div style="font-size:12px; color:var(--text-mid);">${esc(p.category)} · ${esc(p.department)}</div>
      <div style="font-size:12px; color:var(--text-mid);">Cost: <strong>${fmtInr(p.estimated_cost)}</strong> · Priority: ${esc(p.priority || 'Medium')}</div>
      ${p.description ? `<div style="font-size:12px; color:var(--text-dim); margin-top:4px;">${esc(p.description.slice(0, 160))}…</div>` : ''}
    </div>
  `;

  // Auto-set title if empty
  const titleInput = $('dg-title');
  if (titleInput && !titleInput.value) {
    titleInput.value = `Proposal Report — ${p.ref_no} — ${p.title}`;
  }
}

async function generateDocument(format) {
  const title   = ($('dg-title')?.value || '').trim();
  const content = ($('dg-content')?.value || '').trim();
  const template = $('dg-template')?.value || 'standard';

  if (!title) { toast('Please enter a document title.', 'err'); return; }

  const payload = { title, content, template };
  if (_dgSelectedProp) {
    // For PDF with a proposal, use Decision Brief if template is 'brief'
    payload.prop_id = _dgSelectedProp.id;
  }

  showLoad(`Generating ${format.toUpperCase()} document…`);
  try {
    const endpoint = format === 'docx' ? '/api/generate/docx' : '/api/generate/pdf';
    const r = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    hideLoad();

    if (!r.ok) {
      const err = await r.json().catch(() => ({ error: 'Unknown error' }));
      toast(`Generation failed: ${err.error}`, 'err', 5000);
      return;
    }

    // Trigger download
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safeTitle = title.replace(/[^a-zA-Z0-9\s\-_]/g, '').trim().slice(0, 40).replace(/\s+/g, '_');
    a.href = url;
    a.download = `${safeTitle}.${format}`;
    a.click();
    URL.revokeObjectURL(url);

    toast(`${format.toUpperCase()} document generated and downloaded.`, 'ok');
  } catch (err) {
    hideLoad();
    toast(`Generation error: ${err}`, 'err');
  }
}

/* ═══════════════════════════════════════════════════════════════════
   12. MEMORY & KNOWLEDGE BASE
   ═══════════════════════════════════════════════════════════════════ */

async function loadMemoryDocs() {
  try {
    const r = await fetch(`${API}/api/memory/documents`);
    const d = await r.json();
    renderMemoryDocs(d.documents || [], d.total_chars || 0);
  } catch (err) {
    console.warn('[Memory] Failed to load documents:', err);
  }
}

function renderMemoryDocs(docs, totalChars) {
  // Update stats
  if ($('mem-stat-docs')) $('mem-stat-docs').textContent = docs.length;
  if ($('mem-stat-chars')) $('mem-stat-chars').textContent = (totalChars || 0).toLocaleString();
  if ($('mem-doc-count')) $('mem-doc-count').textContent = `${docs.length} document${docs.length !== 1 ? 's' : ''}`;

  const list = $('mem-doc-list');
  if (!list) return;

  if (docs.length === 0) {
    list.innerHTML = `<div style="color:var(--text-dim); font-size:13px; text-align:center; padding:32px 0;">No documents in memory. Upload files above to begin.</div>`;
    return;
  }

  list.innerHTML = docs.map(doc => `
    <div style="background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
                padding:12px 14px; display:flex; align-items:flex-start; gap:12px;">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.8" style="flex-shrink:0; margin-top:2px;">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
      </svg>
      <div style="flex:1; min-width:0;">
        <div style="font-size:13px; font-weight:600; color:var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(doc.filename)}</div>
        <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">
          ${(doc.char_count || 0).toLocaleString()} chars · ${doc.uploaded_at || '—'}
        </div>
        ${doc.summary ? `<div style="font-size:11.5px; color:var(--text-dim); margin-top:4px; line-height:1.5;">${esc(doc.summary)}</div>` : ''}
      </div>
      <button class="btn btn-secondary btn-sm" onclick="deleteMemoryDoc('${doc.doc_id}')"
        style="flex-shrink:0; color:var(--red); border-color:var(--red);">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
        </svg>
      </button>
    </div>
  `).join('');
}

function handleMemoryDrop(event) {
  event.preventDefault();
  const zone = event.currentTarget;
  zone.style.borderColor = 'var(--border-accent)';
  zone.style.background = 'var(--surface)';
  const files = Array.from(event.dataTransfer.files);
  if (files.length > 0) uploadMemoryFileList(files);
}

async function uploadMemoryFiles(input) {
  const files = Array.from(input.files);
  if (files.length === 0) return;
  await uploadMemoryFileList(files);
  input.value = '';
}

async function uploadMemoryFileList(files) {
  showLoad(`Uploading ${files.length} file(s) to Memory…`);
  let success = 0;
  let errors = [];

  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const r = await fetch(`${API}/api/memory/upload`, { method: 'POST', body: formData });
      const d = await r.json();
      if (r.ok) {
        success++;
      } else {
        errors.push(`${file.name}: ${d.error}`);
      }
    } catch (err) {
      errors.push(`${file.name}: ${err}`);
    }
  }

  hideLoad();

  if (success > 0) toast(`${success} file(s) added to Memory.`, 'ok');
  if (errors.length > 0) toast(`${errors.length} file(s) failed: ${errors[0]}`, 'err', 5000);

  loadMemoryDocs();
}

async function deleteMemoryDoc(docId) {
  if (!confirm('Remove this document from Memory?')) return;
  showLoad('Removing document…');
  try {
    const r = await fetch(`${API}/api/memory/documents/${docId}`, { method: 'DELETE' });
    hideLoad();
    toast('Document removed from memory.', 'ok');
    loadMemoryDocs();
  } catch (err) {
    hideLoad();
    toast(`Delete failed: ${err}`, 'err');
  }
}

async function confirmMemoryClear() {
  if (!confirm('Clear ALL documents from Memory? This cannot be undone.')) return;
  showLoad('Clearing all memory documents…');
  try {
    const r = await fetch(`${API}/api/memory/clear`, { method: 'POST' });
    const d = await r.json();
    hideLoad();
    toast(`Memory cleared — ${d.deleted || 0} documents removed.`, 'ok');
    loadMemoryDocs();
  } catch (err) {
    hideLoad();
    toast(`Clear failed: ${err}`, 'err');
  }
}

async function memorySearch() {
  const query = ($('mem-search-input')?.value || '').trim();
  if (!query) { toast('Enter a search query.', 'err'); return; }

  const resultsEl = $('mem-search-results');
  if (resultsEl) resultsEl.innerHTML = `<div style="color:var(--text-dim); font-size:12.5px;">Searching…</div>`;

  try {
    const r = await fetch(`${API}/api/memory/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const d = await r.json();

    if (!r.ok) { toast(`Search error: ${d.error}`, 'err'); return; }

    const results = d.results || [];
    if (!resultsEl) return;

    if (results.length === 0) {
      resultsEl.innerHTML = `<div style="color:var(--text-dim); font-size:12.5px;">No relevant excerpts found for: "${esc(query)}"</div>`;
      return;
    }

    resultsEl.innerHTML = results.map(r => `
      <div style="background:var(--surface); border:1px solid var(--border-accent); border-radius:var(--radius); padding:12px 14px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
          <span style="font-size:12px; font-weight:600; color:var(--accent);">${esc(r.filename)}</span>
          <span style="font-size:10px; background:var(--accent-dim); color:var(--accent); border-radius:4px; padding:2px 6px;">Score: ${r.score}</span>
        </div>
        <div style="font-size:12px; color:var(--text); line-height:1.7; font-family:var(--fm);">${esc(r.excerpt)}</div>
      </div>
    `).join('');

    toast(`Found ${results.length} relevant excerpt(s) in memory.`, 'ok', 2000);
  } catch (err) {
    if (resultsEl) resultsEl.innerHTML = `<div style="color:var(--red); font-size:12.5px;">Search error: ${esc(String(err))}</div>`;
  }
}

