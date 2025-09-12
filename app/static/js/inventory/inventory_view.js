
document.addEventListener('DOMContentLoaded', function() {
    // Check if initial inventory modal exists and show it
    const initialModal = document.getElementById('initialInventoryModal');
    if (initialModal) {
        const modal = new bootstrap.Modal(initialModal);
        modal.show();

        // Prevent closing modal by clicking outside or escape key
        initialModal.addEventListener('hide.bs.modal', function (e) {
            // Allow closing if we're switching to edit modal
            if (e.relatedTarget && e.relatedTarget.getAttribute('data-bs-target') === '#editDetailsModal') {
                return;
            }
            e.preventDefault();
            return false;
        });

        // Focus on quantity input when modal is shown
        initialModal.addEventListener('shown.bs.modal', function () {
            document.getElementById('initial_quantity').focus();
        });

        // Handle edit button click to properly transition modals
        const editButton = initialModal.querySelector('[data-bs-target="#editDetailsModal"]');
        if (editButton) {
            editButton.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Hide initial modal first
                modal.hide();
                
                // Wait for initial modal to be fully hidden before showing edit modal
                initialModal.addEventListener('hidden.bs.modal', function showEditModal() {
                    const editModal = document.getElementById('editDetailsModal');
                    if (editModal) {
                        const editModalInstance = new bootstrap.Modal(editModal);
                        editModalInstance.show();
                    }
                    // Remove the event listener to prevent multiple bindings
                    initialModal.removeEventListener('hidden.bs.modal', showEditModal);
                }, { once: true });
            });
        }
    }

    // Handle edit modal form validation and submission
    const form = document.querySelector('#editDetailsModal form');
    if (form) {
        const quantityInput = form.querySelector('input[name="quantity"]');
        const originalQuantity = quantityInput ? parseFloat(quantityInput.value) : 0;
        const recountModalEl = document.getElementById('recountConfirmModal');

        if (recountModalEl) {
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

            const confirmRecountBtn = document.getElementById('confirmRecount');
            if (confirmRecountBtn) {
                confirmRecountBtn.addEventListener('click', function() {
                    const hiddenInput = document.createElement('input');
                    hiddenInput.type = 'hidden';
                    hiddenInput.name = 'change_type';
                    hiddenInput.value = 'recount';
                    form.appendChild(hiddenInput);
                    recountModal.hide();
                    form.submit();
                });
            }
        }
    }

    // Cost override handling
    const overrideCostCheckbox = document.getElementById('modal_override_cost');
    const costPerUnitInput = document.getElementById('modal_cost_per_unit');
    const costOverrideWarningModalEl = document.getElementById('costOverrideWarningModal');

    if (overrideCostCheckbox && costPerUnitInput && costOverrideWarningModalEl) {
        const costOverrideModal = new bootstrap.Modal(costOverrideWarningModalEl);

        overrideCostCheckbox.addEventListener('change', function() {
            if (this.checked) {
                costOverrideModal.show();
            } else {
                costPerUnitInput.readOnly = true;
            }
        });

        const confirmCostOverrideBtn = document.getElementById('confirmCostOverride');
        if (confirmCostOverrideBtn) {
            confirmCostOverrideBtn.addEventListener('click', function() {
                costPerUnitInput.readOnly = false;
                costOverrideModal.hide();
            });
        }

        costOverrideWarningModalEl.addEventListener('hidden.bs.modal', function() {
            if (costPerUnitInput.readOnly) {
                overrideCostCheckbox.checked = false;
            }
        });
    }

    // Type change handler
    const typeSelect = document.querySelector('select[name="type"]');
    if (typeSelect) {
        typeSelect.addEventListener('change', function() {
            const categorySection = document.getElementById('categorySection');
            if (categorySection) {
                categorySection.style.display = this.value === 'ingredient' ? 'block' : 'none';
            }
        });
    }

    // Category change handler
    const categorySelect = document.getElementById('categorySelect');
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
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
    }

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
