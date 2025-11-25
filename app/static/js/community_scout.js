class CommunityScoutUI {
  constructor(root) {
    this.root = root;
    this.nextUrl = root.dataset.nextUrl || '/api/dev/community-scout/batches/next';
    this.apiBase = root.dataset.baseUrl || '/api/dev/community-scout';
    this.statusEl = document.getElementById('community-scout-status');
    this.metaEl = document.getElementById('community-scout-meta');
    this.needsReviewList = document.getElementById('needs-review-list');
    this.uniqueList = document.getElementById('unique-list');
    this.refreshBtn = document.getElementById('community-scout-refresh');
    this.clearBtn = document.getElementById('community-scout-clear');
    this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

    this.refreshBtn?.addEventListener('click', () => this.loadBatch(true));
    this.clearBtn?.addEventListener('click', () => this.clearLists(true));

    this.loadBatch();
  }

  async loadBatch(manual = false) {
    this.setStatus(manual ? 'Fetching next batch…' : 'Loading Community Scout…', 'info');
    try {
      const resp = await fetch(this.nextUrl, { credentials: 'same-origin' });
      if (!resp.ok) {
        throw new Error(`Request failed (${resp.status})`);
      }
      const data = await resp.json();
      this.renderBatch(data.batch);
    } catch (err) {
      console.error(err);
      this.setStatus(`Failed to load batch: ${err.message}`, 'danger');
    }
  }

  renderBatch(batch) {
    if (!batch) {
      this.clearLists();
      if (this.metaEl) this.metaEl.textContent = '';
      this.setStatus('No pending Community Scout batches. All caught up! 🎉', 'success');
      return;
    }

    const pending = batch.metadata?.pending ?? 0;
    const resolved = batch.metadata?.resolved ?? 0;
    if (this.metaEl) {
      this.metaEl.textContent = `Batch #${batch.id} · ${pending} pending / ${resolved} resolved`;
    }

    this.setStatus('Batch ready for review.', 'primary');
    this.needsReviewList.innerHTML = '';
    this.uniqueList.innerHTML = '';

    const candidates = batch.candidates || [];
    const needsReview = candidates.filter((c) => c.classification === 'needs_review' && c.state === 'open');
    const unique = candidates.filter((c) => c.classification !== 'needs_review' && c.state === 'open');

    if (!needsReview.length) {
      this.needsReviewList.innerHTML = '<div class="text-muted small">No pending review items.</div>';
    } else {
      needsReview.forEach((candidate) => {
        const card = this.buildCandidateCard(candidate);
        this.needsReviewList.appendChild(card);
      });
    }

    if (!unique.length) {
      this.uniqueList.innerHTML = '<div class="text-muted small">No unique items pending.</div>';
    } else {
      unique.forEach((candidate) => {
        const card = this.buildCandidateCard(candidate);
        this.uniqueList.appendChild(card);
      });
    }
  }

  clearLists(manual = false) {
    this.needsReviewList.innerHTML = '';
    this.uniqueList.innerHTML = '';
    if (manual) {
      this.setStatus('Cleared current batch view.', 'secondary');
      if (this.metaEl) this.metaEl.textContent = '';
    }
  }

  buildCandidateCard(candidate) {
    const snapshot = candidate.snapshot || {};
    const card = document.createElement('div');
    card.className = 'card shadow-sm';

    const body = document.createElement('div');
    body.className = 'card-body';
    card.appendChild(body);

    const header = document.createElement('div');
    header.className = 'd-flex justify-content-between align-items-start mb-2';
    body.appendChild(header);

    const titleWrap = document.createElement('div');
    header.appendChild(titleWrap);

    const title = document.createElement('h5');
    title.className = 'card-title mb-0';
    title.textContent = snapshot.name || 'Unnamed item';
    titleWrap.appendChild(title);

    const subtitle = document.createElement('div');
    subtitle.className = 'text-muted small';
    subtitle.textContent = `${snapshot.organization_name || 'Unknown org'} · ${snapshot.type || 'ingredient'}`;
    titleWrap.appendChild(subtitle);

    const badge = document.createElement('span');
    badge.className = `badge ${candidate.classification === 'needs_review' ? 'bg-warning text-dark' : 'bg-success'}`;
    badge.textContent = candidate.classification === 'needs_review' ? 'Needs review' : 'Unique';
    header.appendChild(badge);

    const info = document.createElement('div');
    info.className = 'mb-3 small';
    info.innerHTML = this.buildMatchesMarkup(candidate);
    body.appendChild(info);

    if (candidate.sensitivity_flags && candidate.sensitivity_flags.length) {
      const alert = document.createElement('div');
      alert.className = 'alert alert-warning py-2';
      alert.innerHTML = `<strong>Flagged alias:</strong> ${CommunityScoutUI.escapeHtml(candidate.sensitivity_flags[0].alias_used || snapshot.name || '')}`;
      body.appendChild(alert);
    }

    const actions = document.createElement('div');
    actions.className = 'border-top pt-3';
    actions.innerHTML = this.buildActionsMarkup(candidate, snapshot);
    body.appendChild(actions);

    this.attachActionHandlers(actions, candidate);
    return card;
  }

  buildMatchesMarkup(candidate) {
    const matches = candidate.match_scores?.top_matches || [];
    if (!matches.length) {
      return '<span class="text-muted">No related global items yet.</span>';
    }
    const rows = matches
      .map((match) => {
        const percent = Math.round((match.score || 0) * 100);
        const type = CommunityScoutUI.escapeHtml(match.match_type || 'match');
        return `<li><strong>${CommunityScoutUI.escapeHtml(match.name || 'Unnamed')}</strong> · ${percent}% (${type})</li>`;
      })
      .join('');
    return `<span class="text-muted d-block mb-1">Possible matches:</span><ul class="mb-0 small">${rows}</ul>`;
  }

  buildActionsMarkup(candidate, snapshot) {
    const itemName = CommunityScoutUI.escapeHtml(snapshot.name || '');
    const defaultUnit = CommunityScoutUI.escapeHtml(snapshot.unit || '');
    const inci = CommunityScoutUI.escapeHtml(snapshot.inci_name || '');
    const normalizedType = (snapshot.type || 'ingredient').toLowerCase();
    const typeOptions = ['ingredient', 'container', 'consumable', 'packaging']
      .map((opt) => `<option value="${opt}" ${normalizedType === opt ? 'selected' : ''}>${opt}</option>`)
      .join('');

    return `
      <form class="scout-promote-form" data-candidate-id="${candidate.id}">
        <div class="row g-2">
          <div class="col-md-5">
            <label class="form-label small mb-1">Global Name</label>
            <input type="text" name="name" class="form-control form-control-sm" value="${itemName}" required>
          </div>
          <div class="col-md-3">
            <label class="form-label small mb-1">Type</label>
            <select name="item_type" class="form-select form-select-sm">
              ${typeOptions}
            </select>
          </div>
          <div class="col-md-4">
            <label class="form-label small mb-1">Default Unit</label>
            <input type="text" name="default_unit" class="form-control form-control-sm" value="${defaultUnit}">
          </div>
        </div>
        <div class="row g-2 mt-2">
          <div class="col-md-4">
            <label class="form-label small mb-1">INCI</label>
            <input type="text" name="inci_name" class="form-control form-control-sm" value="${inci}">
          </div>
          <div class="col-md-4">
            <label class="form-label small mb-1">Density (g/ml)</label>
            <input type="number" step="0.0001" name="density" class="form-control form-control-sm">
          </div>
          <div class="col-md-4">
            <label class="form-label small mb-1">Aliases (comma separated)</label>
            <input type="text" name="aliases" class="form-control form-control-sm" placeholder="Brazil nut, ...">
          </div>
        </div>
        <button type="submit" class="btn btn-sm btn-primary mt-3">
          <i class="fas fa-plus me-1"></i> Add to Global Library
        </button>
      </form>

      <form class="scout-link-form mt-3" data-candidate-id="${candidate.id}">
        <label class="form-label small mb-1">Match Existing Global Item</label>
        <div class="input-group input-group-sm">
          <span class="input-group-text">Global Item ID</span>
          <input type="number" name="global_item_id" class="form-control" required>
          <button class="btn btn-outline-success" type="submit">
            <i class="fas fa-link"></i>
          </button>
        </div>
      </form>

      <form class="scout-reject-form mt-3" data-candidate-id="${candidate.id}">
        <label class="form-label small mb-1">Reject / Defer Reason</label>
        <div class="input-group input-group-sm">
          <input type="text" name="reason" class="form-control" placeholder="e.g. duplicate data, unclear specs" required>
          <button class="btn btn-outline-secondary" type="submit">
            <i class="fas fa-ban"></i>
          </button>
        </div>
      </form>

      <button class="btn btn-sm btn-warning mt-3 scout-flag-btn" data-candidate-id="${candidate.id}">
        <i class="fas fa-flag"></i> Flag alias usage
      </button>
    `;
  }

  attachActionHandlers(container, candidate) {
    const promoteForm = container.querySelector('.scout-promote-form');
    promoteForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      this.handlePromote(candidate.id, promoteForm);
    });

    const linkForm = container.querySelector('.scout-link-form');
    linkForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      this.handleLink(candidate.id, linkForm);
    });

    const rejectForm = container.querySelector('.scout-reject-form');
    rejectForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      this.handleReject(candidate.id, rejectForm);
    });

    const flagBtn = container.querySelector('.scout-flag-btn');
    flagBtn?.addEventListener('click', (event) => {
      event.preventDefault();
      this.handleFlag(candidate.id);
    });
  }

  async handlePromote(candidateId, form) {
    const formData = new FormData(form);
    const payload = {
      global_item_payload: {
        name: formData.get('name')?.toString().trim(),
        item_type: formData.get('item_type')?.toString().trim(),
        default_unit: formData.get('default_unit')?.toString().trim() || null,
        inci_name: formData.get('inci_name')?.toString().trim() || null,
      },
    };

    const densityValue = formData.get('density');
    const parsedDensity = densityValue ? parseFloat(densityValue) : NaN;
    if (!Number.isNaN(parsedDensity)) {
      payload.global_item_payload.density = parsedDensity;
    }

    const aliasesValue = formData.get('aliases')?.toString();
    if (aliasesValue) {
      payload.global_item_payload.aliases = aliasesValue
        .split(',')
        .map((alias) => alias.trim())
        .filter(Boolean);
    }

    await this.submitAction(`${this.apiBase}/candidates/${candidateId}/promote`, payload);
  }

  async handleLink(candidateId, form) {
    const formData = new FormData(form);
    const globalItemId = formData.get('global_item_id');
    if (!globalItemId) {
      this.setStatus('Global item ID is required to link.', 'warning');
      return;
    }
    await this.submitAction(`${this.apiBase}/candidates/${candidateId}/link`, {
      global_item_id: Number(globalItemId),
    });
  }

  async handleReject(candidateId, form) {
    const formData = new FormData(form);
    const reason = formData.get('reason')?.toString().trim();
    if (!reason) {
      this.setStatus('Please provide a reason before rejecting.', 'warning');
      return;
    }
    await this.submitAction(`${this.apiBase}/candidates/${candidateId}/reject`, { reason });
  }

  async handleFlag(candidateId) {
    await this.submitAction(`${this.apiBase}/candidates/${candidateId}/flag`, {
      reason: 'manual_flag',
    });
  }

  async submitAction(url, payload) {
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.success === false) {
        throw new Error(data.error || `Request failed (${resp.status})`);
      }
      this.setStatus('Action completed successfully.', 'success');
      this.loadBatch(true);
    } catch (err) {
      console.error(err);
      this.setStatus(`Action failed: ${err.message}`, 'danger');
    }
  }

  setStatus(message, variant = 'info') {
    if (!this.statusEl) return;
    this.statusEl.className = `alert alert-${variant}`;
    this.statusEl.textContent = message;
  }

  static escapeHtml(value) {
    if (value === undefined || value === null) return '';
    return value
      .toString()
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('community-scout-root');
  if (root) {
    new CommunityScoutUI(root);
  }
});
