function showInventoryTrackingUpgradeModal() {
    const upgradeModal = document.getElementById('featureUpgradeModal');
    if (!upgradeModal || typeof bootstrap === 'undefined') {
        window.location.href = '/billing/upgrade';
        return;
    }

    const modalTitle = document.getElementById('featureUpgradeModalTitle');
    const modalBody = document.getElementById('featureUpgradeModalBody');
    if (modalTitle) {
        modalTitle.textContent = 'Inventory quantity tracking requires an upgrade';
    }
    if (modalBody) {
        modalBody.textContent = 'Your current plan runs inventory in Infinite mode. Upgrade to unlock quantity adjustments, recounts, and lot edits.';
    }
    bootstrap.Modal.getOrCreateInstance(upgradeModal).show();
}

function lockAdjustInventoryCard() {
    const adjustmentForm = document.querySelector('form[action*="/inventory/adjust/"]');
    if (!adjustmentForm) return;

    const adjustmentCard = adjustmentForm.closest('.card');
    if (!adjustmentCard) return;

    adjustmentCard.classList.add('position-relative', 'opacity-50');
    adjustmentForm.querySelectorAll('input, select, textarea, button').forEach((field) => {
        field.disabled = true;
    });

    if (adjustmentCard.querySelector('[data-quantity-upgrade-overlay="true"]')) {
        return;
    }

    const overlay = document.createElement('div');
    overlay.setAttribute('data-quantity-upgrade-overlay', 'true');
    overlay.className = 'position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center';
    overlay.style.background = 'rgba(255, 255, 255, 0.45)';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-warning btn-sm';
    button.textContent = 'Upgrade to adjust quantities';
    button.addEventListener('click', function (event) {
        event.preventDefault();
        showInventoryTrackingUpgradeModal();
    });
    overlay.appendChild(button);
    adjustmentCard.appendChild(overlay);
}

function lockExpiredQuantityActions() {
    const quantityActionButtons = document.querySelectorAll('button[onclick*="markAsExpired"], button[onclick*="markAsSpoiled"]');
    quantityActionButtons.forEach((button) => {
        button.removeAttribute('onclick');
        button.classList.add('disabled', 'opacity-75');
        button.setAttribute('title', 'Upgrade to adjust tracked quantities');
        button.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            showInventoryTrackingUpgradeModal();
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const trackedToggleInModal = document.getElementById('modal_is_tracked');
    const orgTracksInventoryQuantities = !(trackedToggleInModal && trackedToggleInModal.disabled);

    if (!orgTracksInventoryQuantities) {
        lockAdjustInventoryCard();
        lockExpiredQuantityActions();
    }

    // Check if initial inventory modal exists and show it
    const initialModal = document.getElementById('initialInventoryModal');
    if (initialModal && orgTracksInventoryQuantities) {
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
            const initialQty = document.getElementById('initial_quantity');
            if (initialQty) {
                initialQty.focus();
            }
        });
    } else if (initialModal && !orgTracksInventoryQuantities) {
        initialModal.remove();
    }

    // Handle returning from edit modal to initial inventory modal
    const editModal = document.getElementById('editDetailsModal');
    if (editModal && initialModal && orgTracksInventoryQuantities) {
        editModal.addEventListener('hidden.bs.modal', function () {
            // If we came from initial inventory modal, show it again
            if (document.getElementById('initialInventoryModal')) {
                const initialModalInstance = new bootstrap.Modal(initialModal);
                initialModalInstance.show();
            }
        });
    }

    if (editModal) {
        editModal.addEventListener('shown.bs.modal', function () {
            const quantityInput = document.querySelector('#editDetailsModal input[name="quantity"]');
            if (quantityInput) {
                quantityInput.dataset.initialQuantity = quantityInput.value || '0';
            }
            const trackedToggle = document.getElementById('modal_is_tracked');
            if (trackedToggle) {
                trackedToggle.dataset.initialTracked = trackedToggle.checked ? 'true' : 'false';
            }
        });
    }

    const form = document.querySelector('#editDetailsModal form');
    let recountModal = null;
    if (form) {
        const quantityInput = form.querySelector('input[name="quantity"]');
        const recountModalEl = document.getElementById('recountConfirmModal');
        if (recountModalEl) {
            recountModal = new bootstrap.Modal(recountModalEl);
        }

        if (!orgTracksInventoryQuantities && quantityInput) {
            quantityInput.readOnly = true;
            quantityInput.classList.add('bg-light', 'text-muted');
            quantityInput.setAttribute('aria-disabled', 'true');
            quantityInput.addEventListener('click', function (event) {
                event.preventDefault();
                showInventoryTrackingUpgradeModal();
            });
            quantityInput.addEventListener('focus', function () {
                this.blur();
                showInventoryTrackingUpgradeModal();
            });
        }

        form.addEventListener('submit', function(e) {
            const trackedToggle = document.getElementById('modal_is_tracked');
            const initialTracked = trackedToggle
                ? ((trackedToggle.dataset.initialTracked || '').toLowerCase() === 'true')
                : false;
            const switchedToInfinite = Boolean(
                orgTracksInventoryQuantities
                && trackedToggle
                && initialTracked
                && !trackedToggle.checked
            );

            if (switchedToInfinite) {
                const confirmedDrain = window.confirm(
                    'You are about to toggle to Infinite mode. This will mark all of your existing lots with remaining quantity as 0.'
                );
                if (!confirmedDrain) {
                    e.preventDefault();
                    return;
                }
                let confirmInput = form.querySelector('input[name="confirm_infinite_drain"]');
                if (!confirmInput) {
                    confirmInput = document.createElement('input');
                    confirmInput.type = 'hidden';
                    confirmInput.name = 'confirm_infinite_drain';
                    form.appendChild(confirmInput);
                }
                confirmInput.value = 'true';
            }

            if (!quantityInput) {
                return;
            }

            const baselineRaw = quantityInput.dataset.initialQuantity || quantityInput.defaultValue || quantityInput.value || '0';
            const baselineQuantity = parseFloat(baselineRaw);
            const newQuantity = parseFloat(quantityInput.value);
            if (Number.isNaN(newQuantity) || Number.isNaN(baselineQuantity)) {
                return;
            }

            const quantityChanged = Math.abs(newQuantity - baselineQuantity) > 1e-9;
            if (!quantityChanged) {
                return;
            }

            if (!orgTracksInventoryQuantities) {
                e.preventDefault();
                showInventoryTrackingUpgradeModal();
                return;
            }

            if (recountModal) {
                e.preventDefault();
                recountModal.show();
            }
        });
    }

    const confirmRecountBtn = document.getElementById('confirmRecount');
    if (confirmRecountBtn && form) {
        confirmRecountBtn.addEventListener('click', function() {
            let hiddenInput = form.querySelector('input[name="change_type"]');
            if (!hiddenInput) {
                hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = 'change_type';
                form.appendChild(hiddenInput);
            }
            hiddenInput.value = 'recount';
            if (recountModal) { recountModal.hide(); }
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
    const categorySelect = document.getElementById('editCategory');
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            const densityInput = document.getElementById('density');
            if (!densityInput) return;
            if (this.value === '') {
                densityInput.disabled = false;
                densityInput.readOnly = false;
            } else {
                const selectedOption = this.options[this.selectedIndex];
                const defaultDensity = selectedOption && selectedOption.dataset ? selectedOption.dataset.density : '';
                if (defaultDensity) densityInput.value = defaultDensity;
                densityInput.disabled = true;
                densityInput.readOnly = true;
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
        const fifoFilterEl = document.getElementById('fifoFilter');
        if (fifoFilterEl) {
            fifoFilterEl.checked = true;
        }
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