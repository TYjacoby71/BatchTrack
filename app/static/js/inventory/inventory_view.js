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
    }

    // Handle returning from edit modal to initial inventory modal
    const editModal = document.getElementById('editDetailsModal');
    if (editModal && initialModal) {
        let returnToInitialModal = false;
        let isTransitioning = false;

        // Track when we're switching from initial to edit modal
        const editButton = initialModal.querySelector('[data-bs-target="#editDetailsModal"]');
        if (editButton) {
            editButton.addEventListener('click', function(e) {
                e.preventDefault();
                
                if (isTransitioning) return; // Prevent multiple transitions
                isTransitioning = true;
                returnToInitialModal = true;

                // Get the current modal instance
                const initialModalInstance = bootstrap.Modal.getInstance(initialModal);
                
                if (initialModalInstance) {
                    // Create one-time event listener for when initial modal is fully hidden
                    const handleInitialHidden = function() {
                        initialModal.removeEventListener('hidden.bs.modal', handleInitialHidden);
                        
                        // Add delay to ensure DOM is ready
                        setTimeout(() => {
                            // Force z-index reset and show edit modal
                            editModal.style.zIndex = '1055';
                            const editModalInstance = new bootstrap.Modal(editModal, {
                                backdrop: 'static',
                                keyboard: false
                            });
                            editModalInstance.show();
                            isTransitioning = false;
                        }, 100);
                    };

                    initialModal.addEventListener('hidden.bs.modal', handleInitialHidden);
                    initialModalInstance.hide();
                } else {
                    // Fallback - force hide initial modal
                    initialModal.style.display = 'none';
                    initialModal.classList.remove('show');
                    document.body.classList.remove('modal-open');
                    
                    // Remove any existing backdrop
                    const existingBackdrop = document.querySelector('.modal-backdrop');
                    if (existingBackdrop) {
                        existingBackdrop.remove();
                    }
                    
                    setTimeout(() => {
                        editModal.style.zIndex = '1055';
                        const editModalInstance = new bootstrap.Modal(editModal, {
                            backdrop: 'static',
                            keyboard: false
                        });
                        editModalInstance.show();
                        isTransitioning = false;
                    }, 100);
                }
            });
        }

        // Listen for successful form submission to prevent return
        const editForm = editModal.querySelector('form');
        if (editForm) {
            editForm.addEventListener('submit', function() {
                returnToInitialModal = false;
            });
        }

        editModal.addEventListener('hidden.bs.modal', function () {
            // Reset z-index
            editModal.style.zIndex = '';
            
            // Only return to initial modal if we didn't submit the form
            if (returnToInitialModal && document.getElementById('initialInventoryModal')) {
                setTimeout(() => {
                    const initialModalInstance = new bootstrap.Modal(initialModal);
                    initialModalInstance.show();
                    returnToInitialModal = false;
                }, 100);
            }
        });
    }

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
        }
    }

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
        // Don't call toggleFifoFilter() here as it would cause a reload loop
    }

    const initialStockBtn = document.getElementById('initial-stock-btn');
    if (initialStockBtn) {
        initialStockBtn.addEventListener('click', function() {
            // Initial stock button functionality can be added here if needed
        });
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