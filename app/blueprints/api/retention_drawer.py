from flask import Blueprint, jsonify, render_template_string, request, send_file
from flask_login import login_required, current_user
from io import BytesIO

from ...models import db, Organization
from ...services.retention_service import RetentionService

retention_bp = Blueprint('retention', __name__, url_prefix='/retention')


@retention_bp.route('/api/check')
@login_required
def check_retention_needed():
    org: Organization | None = current_user.organization
    if not org:
        return jsonify({'needs_drawer': False})
    items = RetentionService.get_pending_drawer_items(org)
    return jsonify({'needs_drawer': len(items) > 0, 'count': len(items)})


@retention_bp.route('/api/modal')
@login_required
def get_retention_modal():
    org: Organization | None = current_user.organization
    items = RetentionService.get_pending_drawer_items(org) if org else []

    html = render_template_string('''
<div class="modal fade" id="retentionDrawerModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header bg-warning">
        <h5 class="modal-title"><i class="fas fa-exclamation-triangle me-2"></i>Data Retention Notice</h5>
      </div>
      <div class="modal-body">
        <p>Some experimental recipes have reached your plan's data retention limit. You must choose an action below. If you do nothing, the items will be permanently deleted after 15 days.</p>
        <div class="alert alert-light border">
          <strong>{{ items|length }} recipe(s)</strong> are at risk of deletion.
        </div>
        <div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
          <table class="table table-sm align-middle">
            <thead><tr><th>Name</th><th>Created</th><th>Yield</th></tr></thead>
            <tbody>
            {% for r in items %}
              <tr>
                <td>{{ r.name }}</td>
                <td>{{ r.created_at.strftime('%Y-%m-%d') if r.created_at else '' }}</td>
                <td>{{ r.predicted_yield }} {{ r.predicted_yield_unit }}</td>
              </tr>
            {% endfor %}
            </tbody>
          </table>
        </div>
        <div class="d-flex gap-2 mt-3">
          <a href="/billing/upgrade" target="_blank" class="btn btn-primary"><i class="fas fa-crown"></i> Upgrade Plan</a>
          <a href="/billing/storage" target="_blank" class="btn btn-outline-primary"><i class="fas fa-database"></i> Buy Storage</a>
          <div class="ms-auto">
            <a href="/retention/api/export?format=csv" class="btn btn-outline-secondary"><i class="fas fa-file-csv"></i> Export CSV</a>
            <a href="/retention/api/export?format=json" class="btn btn-outline-secondary"><i class="fas fa-file-code"></i> Export JSON</a>
            <button class="btn btn-danger ms-2" id="acknowledgeBtn"><i class="fas fa-check"></i> Acknowledge</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
document.getElementById('acknowledgeBtn').addEventListener('click', async function() {
  try {
    const res = await fetch('/retention/api/acknowledge', { method: 'POST', headers: {'Content-Type':'application/json','X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')}, body: JSON.stringify({ acknowledge: true }) });
    const data = await res.json();
    if (data.success) {
      const modalEl = document.getElementById('retentionDrawerModal');
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
      window.dispatchEvent(new CustomEvent('retention.acknowledged', { detail: { queued: data.queued } }));
    } else {
      alert('Error: ' + (data.error || 'Failed to acknowledge'));
    }
  } catch (e) {
    alert('Network error');
  }
});
setTimeout(() => {
  const el = document.getElementById('retentionDrawerModal');
  if (el) { const modal = new bootstrap.Modal(el); modal.show(); }
}, 0);
</script>
''', items=items)

    return jsonify({'success': True, 'modal_html': html})


@retention_bp.route('/api/acknowledge', methods=['POST'])
@login_required
def acknowledge_retention():
    org: Organization | None = current_user.organization
    items = RetentionService.get_pending_drawer_items(org) if org else []
    ids = [r.id for r in items]
    created, skipped = RetentionService.acknowledge_and_queue(org, ids)
    return jsonify({'success': True, 'queued': created, 'skipped': skipped})


@retention_bp.route('/api/export')
@login_required
def export_retention():
    org: Organization | None = current_user.organization
    fmt = request.args.get('format', 'json')
    mimetype, content = RetentionService.export_at_risk(org, fmt)
    return content, 200, {'Content-Type': mimetype}

