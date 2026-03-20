(function () {
  function ensureModal() {
    let modalEl = document.getElementById('quickCreateUnitClientModal');
    if (modalEl) {
      return modalEl;
    }

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
<div class="modal fade" id="quickCreateUnitClientModal" tabindex="-1" aria-labelledby="quickCreateUnitClientModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="quickCreateUnitClientModalLabel">Quick Create Unit</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div class="mb-2">
          <label class="form-label" for="quickCreateUnitClientName">Name</label>
          <input id="quickCreateUnitClientName" class="form-control" type="text" maxlength="64" placeholder="e.g., bar, bottle, packet" />
        </div>
        <div class="mb-2">
          <label class="form-label" for="quickCreateUnitClientType">Type</label>
          <select id="quickCreateUnitClientType" class="form-select">
            <option value="count" selected>Count</option>
            <option value="weight">Weight</option>
            <option value="volume">Volume</option>
            <option value="length">Length</option>
            <option value="area">Area</option>
            <option value="time">Time</option>
          </select>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-primary" id="quickCreateUnitClientSubmit">
          <i class="fas fa-save"></i> Create
        </button>
      </div>
    </div>
  </div>
</div>
    `;
    document.body.appendChild(wrapper);
    modalEl = document.getElementById('quickCreateUnitClientModal');

    const submitBtn = document.getElementById('quickCreateUnitClientSubmit');
    const nameInput = document.getElementById('quickCreateUnitClientName');
    const typeSelect = document.getElementById('quickCreateUnitClientType');

    submitBtn.addEventListener('click', async function () {
      const name = (nameInput.value || '').trim();
      if (!name) {
        if (typeof window.showAlert === 'function') {
          window.showAlert('warning', 'Unit name is required');
        }
        return;
      }

      const original = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
      try {
        const response = await fetch('/api/units', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            unit_type: typeSelect.value || 'count',
          }),
        });
        const data = await response.json();
        const unit = data && data.data ? data.data : data;
        if (!response.ok || (data && data.success === false) || (unit && unit.error)) {
          throw new Error((data && data.error) || (unit && unit.error) || 'Failed to create unit');
        }

        window.dispatchEvent(new CustomEvent('unit.created', { detail: { unit } }));
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.hide();
      } catch (error) {
        if (typeof window.showAlert === 'function') {
          window.showAlert('danger', error.message || 'Failed to create unit');
        } else {
          console.error(error);
        }
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = original;
      }
    });

    return modalEl;
  }

  window.openUnitQuickCreateModal = function openUnitQuickCreateModal(defaultName = '') {
    const modalEl = ensureModal();
    const nameInput = document.getElementById('quickCreateUnitClientName');
    if (nameInput) {
      nameInput.value = defaultName || '';
      setTimeout(() => nameInput.focus(), 30);
    }
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  };
})();
