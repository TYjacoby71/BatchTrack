document.addEventListener('DOMContentLoaded', function() {
    // Check if initial inventory modal exists and show it
    const initialModal = document.getElementById('initialInventoryModal');
    if (initialModal) {
        const modal = new bootstrap.Modal(initialModal);
        modal.show();

        // Prevent closing modal by clicking outside or escape key
        initialModal.addEventListener('hide.bs.modal', function (e) {
            e.preventDefault();
            return false;
        });

        // Focus on quantity input when modal is shown
        initialModal.addEventListener('shown.bs.modal', function () {
            document.getElementById('initial_quantity').focus();
        });
    }

    const form = document.querySelector('#editDetailsModal form');
    const quantityInput = form.querySelector('input[name="quantity"]');
    const originalQuantity = parseFloat(quantityInput.value);
    const recountModalEl = document.getElementById('recountConfirmModal');
    const recountModal = new bootstrap.Modal(recountModalEl);

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const newQuantity = parseFloat(quantityInput.value);
        if (newQuantity !== originalQuantity) {
            recountModal.show();
        } else {
            form.submit();
        }
    });

    document.getElementById('confirmRecount').addEventListener('click', function() {
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'change_type';
        hiddenInput.value = 'recount';
        form.appendChild(hiddenInput);
        recountModal.hide();
        form.submit();
    });

    const overrideCostCheckbox = document.getElementById('modal_override_cost');
    const costPerUnitInput = document.getElementById('modal_cost_per_unit');
    const costOverrideModal = new bootstrap.Modal(document.getElementById('costOverrideWarningModal'));

    overrideCostCheckbox.addEventListener('change', function() {
        if (this.checked) {
            costOverrideModal.show();
        } else {
            costPerUnitInput.readOnly = true;
        }
    });

    document.getElementById('confirmCostOverride').addEventListener('click', function() {
        costPerUnitInput.readOnly = false;
        costOverrideModal.hide();
    });

    document.getElementById('costOverrideWarningModal').addEventListener('hidden.bs.modal', function() {
        if (costPerUnitInput.readOnly) {
            overrideCostCheckbox.checked = false;
        }
    });

    // Type change handler
    document.querySelector('select[name="type"]').addEventListener('change', function() {
        document.getElementById('categorySection').style.display = 
            this.value === 'ingredient' ? 'block' : 'none';
    });

    // Category change handler
    document.getElementById('categorySelect').addEventListener('change', function() {
        const densityInput = document.getElementById('density');
        if (this.value === '') {
            densityInput.disabled = false;
        } else {
            const selectedOption = this.options[this.selectedIndex];
            const defaultDensity = selectedOption.dataset.density;
            densityInput.value = defaultDensity;
            densityInput.disabled = true;
        }
    });

    // Initialize popovers for FIFO ID helper
    setTimeout(function() {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl, {
                container: 'body'
            });
        });

        // Close popover when clicking elsewhere
        document.addEventListener('click', function (e) {
            if (!e.target.closest('[data-bs-toggle="popover"]')) {
                popoverList.forEach(function(popover) {
                    popover.hide();
                });
            }
        });
    }, 100);

    // Check URL for fifo filter parameter and set checkbox state
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('fifo') === 'true') {
        document.getElementById('fifoFilter').checked = true;
        // Don't call toggleFifoFilter() here as it would cause a reload loop
    }
});

function toggleFifoFilter() {
    const fifoFilter = document.getElementById('fifoFilter');
    
    // Build new URL with filter parameter and reset to page 1
    const url = new URL(window.location);
    url.searchParams.delete('page'); // Reset to page 1
    
    if (fifoFilter.checked) {
        url.searchParams.set('fifo', 'true');
    } else {
        url.searchParams.delete('fifo');
    }
    
    // Redirect to apply filter at backend level
    window.location.href = url.toString();
}