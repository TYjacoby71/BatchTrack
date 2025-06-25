
// Product inventory adjustment functionality
document.addEventListener('DOMContentLoaded', function() {
    // Handle FIFO adjustment modal
    const adjustModal = document.getElementById('adjustFifoModal');
    const adjustForm = document.getElementById('adjustFifoForm');

    if (adjustModal && adjustForm) {
        adjustModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            if (button) {
                const inventoryId = button.getAttribute('data-inventory-id');
                const currentQuantity = button.getAttribute('data-current-quantity');
                const unit = button.getAttribute('data-unit');

                if (inventoryId) {
                    // Set form action dynamically - get base URL from current page
                    const baseUrl = window.location.origin + '/products/adjust_fifo/';
                    adjustForm.action = baseUrl + inventoryId;
                }

                // Update help text
                const quantityHelp = document.getElementById('quantityHelp');
                if (quantityHelp && currentQuantity && unit) {
                    quantityHelp.textContent = 
                        `Current quantity: ${currentQuantity} ${unit}. For recount: enter new total. For deductions: enter amount to remove.`;
                }

                // Clear previous values
                const quantityInput = document.getElementById('quantity');
                const changeTypeSelect = document.getElementById('change_type');
                const notesInput = document.getElementById('notes');
                
                if (quantityInput) quantityInput.value = '';
                if (changeTypeSelect) changeTypeSelect.value = '';
                if (notesInput) notesInput.value = '';
            }
        });

        // Update help text based on adjustment type
        const changeTypeSelect = document.getElementById('change_type');
        if (changeTypeSelect) {
            changeTypeSelect.addEventListener('change', function() {
                const helpText = document.getElementById('quantityHelp');
                if (helpText) {
                    const currentText = helpText.textContent;
                    const beforeFor = currentText.split('For')[0];
                    
                    if (this.value === 'recount') {
                        helpText.textContent = beforeFor + 'For recount: enter the new total quantity you want this entry to have.';
                    } else if (this.value) {
                        helpText.textContent = beforeFor + 'For deductions: enter the amount to remove from this entry.';
                    }
                }
            });
        }

        // Form validation
        adjustForm.addEventListener('submit', function(e) {
            const quantity = document.getElementById('quantity');
            const changeType = document.getElementById('change_type');
            
            if (!quantity || !quantity.value || parseFloat(quantity.value) <= 0) {
                e.preventDefault();
                alert('Please enter a valid quantity greater than 0');
                return false;
            }
            
            if (!changeType || !changeType.value) {
                e.preventDefault();
                alert('Please select an adjustment type');
                return false;
            }
        });
    }

    // Initialize Bootstrap modals if not already initialized
    if (typeof bootstrap !== 'undefined') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(function(modal) {
            if (!modal._bootstrap_modal) {
                modal._bootstrap_modal = new bootstrap.Modal(modal);
            }
        });
    }
});

// FIFO filter toggle function
function toggleFifoFilter() {
    const fifoFilter = document.getElementById('fifoFilter');
    if (!fifoFilter) return;

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
