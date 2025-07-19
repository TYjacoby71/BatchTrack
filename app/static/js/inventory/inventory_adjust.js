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
            console.log('Adjustment form submitted');

            // Validate required fields
            const quantity = form.querySelector('input[name="quantity"]');
            const changeType = form.querySelector('input[name="change_type"]:checked');

            if (!quantity || !quantity.value) {
                e.preventDefault();
                alert('Please enter a quantity');
                return false;
            }

            if (!changeType) {
                e.preventDefault();
                alert('Please select a change type');
                return false;
            }

            console.log('Form validation passed, submitting...');
        });
    });

    // Show/hide shelf life override section for restocks
    const expirationSection = document.getElementById('expirationOverrideSection');
    const expirationCheckbox = document.getElementById('override_expiration');
    const shelfLifeField = document.getElementById('shelfLifeField');

    if (expirationSection) {
        const selectedChangeType = getSelectedChangeType();
        if (selectedChangeType === 'restock') {
            expirationSection.style.display = 'block';
        } else {
            expirationSection.style.display = 'none';
            if (expirationCheckbox) expirationCheckbox.checked = false;
            if (shelfLifeField) shelfLifeField.style.display = 'none';
        }
    }

    // Handle shelf life override checkbox
    if (expirationCheckbox && shelfLifeField) {
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
    // Update expiration section visibility based on change type
    const expirationSection = document.getElementById('expirationOverrideSection');
    const selectedValue = selectElement ? selectElement.value : getSelectedChangeType();

    if (expirationSection) {
        if (selectedValue === 'restock') {
            expirationSection.style.display = 'block';
        } else {
            expirationSection.style.display = 'none';
            const expirationCheckbox = document.getElementById('override_expiration');
            const shelfLifeField = document.getElementById('shelfLifeField');
            if (expirationCheckbox) expirationCheckbox.checked = false;
            if (shelfLifeField) shelfLifeField.style.display = 'none';
        }
    }
}

function getSelectedChangeType() {
    const changeTypeSelect = document.getElementById('change_type');
    return changeTypeSelect ? changeTypeSelect.value : 'adjustment';
}

// Function to handle quantity input changes
function handleQuantityChange() {
    const quantity = parseFloat(document.getElementById('quantity').value) || 0;
    const changeType = document.querySelector('input[name="change_type"]:checked')?.value;

    updateQuantityDisplay(quantity, changeType);
}

// Function to get selected change type
function getSelectedChangeType() {
    return document.querySelector('input[name="change_type"]:checked')?.value || 'restock';
}