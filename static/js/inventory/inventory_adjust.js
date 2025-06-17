// Inventory adjustment functionality
document.addEventListener('DOMContentLoaded', function() {
    // Prevent multiple script loading
    if (window.inventoryAdjustmentLoaded) {
        return;
    }
    window.inventoryAdjustmentLoaded = true;

    // Only proceed if we're on a page with adjustment forms
    const adjustmentForms = document.querySelectorAll('.adjustment-form');
    if (adjustmentForms.length === 0) {
        return; // Exit early if no adjustment forms found
    }

    adjustmentForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Add any form validation or processing here
            console.log('Adjustment form submitted');
        });
    });

    // Show/hide shelf life override section for restocks - only if elements exist
    const expirationSection = document.getElementById('expirationOverrideSection');
    const expirationCheckbox = document.getElementById('override_expiration');
    const shelfLifeField = document.getElementById('shelfLifeField');

    // Only proceed with expiration logic if the section exists
    if (expirationSection && expirationCheckbox && shelfLifeField) {
        const selectedChangeType = getSelectedChangeType();
        if (selectedChangeType === 'restock') {
            expirationSection.style.display = 'block';
        } else {
            expirationSection.style.display = 'none';
            expirationCheckbox.checked = false;
            shelfLifeField.style.display = 'none';
        }

        // Handle shelf life override checkbox
        expirationCheckbox.addEventListener('change', function() {
            shelfLifeField.style.display = this.checked ? 'block' : 'none';
        });
    }
});

// Global function for change type updates  
function updateChangeTypeHandler(selectElement) {
    updateChangeType(selectElement);
}

function updateChangeType(selectElement) {
    // Handle change type updates if needed
    console.log('Change type updated:', selectElement.value);
}

// Function to handle quantity input changes
function handleQuantityChange() {
    const quantity = parseFloat(document.getElementById('quantity').value) || 0;
    const changeType = document.querySelector('input[name="change_type"]:checked')?.value;

    updateQuantityDisplay(quantity, changeType);
}

// Function to get selected change type
function getSelectedChangeType() {
    // First try radio buttons (if they exist)
    const radioElement = document.querySelector('input[name="change_type"]:checked');
    if (radioElement) {
        return radioElement.value;
    }
    
    // Then try select dropdown (if it exists)
    const selectElement = document.querySelector('select[name="change_type"]');
    if (selectElement) {
        return selectElement.value;
    }
    
    // Default fallback
    return 'restock';
}