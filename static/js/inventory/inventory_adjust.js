// Inventory adjustment functionality
document.addEventListener('DOMContentLoaded', function() {
    // Prevent multiple script loading
    if (window.inventoryAdjustmentLoaded) {
        return;
    }
    window.inventoryAdjustmentLoaded = true;

    // Initialize any inventory adjustment specific functionality here
    const adjustmentForms = document.querySelectorAll('.adjustment-form');

    adjustmentForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Add any form validation or processing here
            console.log('Adjustment form submitted');
        });
    });

    // Show/hide shelf life override section for restocks
    const expirationSection = document.getElementById('expirationOverrideSection');
    const expirationCheckbox = document.getElementById('override_expiration');
    const shelfLifeField = document.getElementById('shelfLifeField');

    if (expirationSection) {
        if (changeType === 'restock') {
            expirationSection.style.display = 'block';
        } else {
            expirationSection.style.display = 'none';
            if (expirationCheckbox) expirationCheckbox.checked = false;
            if (shelfLifeField) shelfLifeField.style.display = 'none';
        }
    }

    // Handle shelf life override checkbox
    if (expirationCheckbox) {
        expirationCheckbox.addEventListener('change', function() {
            if (shelfLifeField) {
                shelfLifeField.style.display = this.checked ? 'block' : 'none';
            }
        });
    }
});