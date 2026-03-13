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
        const showValidationMessage = (message) => {
            if (typeof window.showAlert === 'function') {
                window.showAlert('warning', message);
            } else {
                console.warn(message);
            }
        };

        const feedbackIdFor = (field) => {
            const rawKey = field?.name || field?.id || 'field';
            return `${String(rawKey).replace(/[^a-zA-Z0-9_-]/g, '_')}-validation-feedback`;
        };

        const markInvalid = (field, message) => {
            if (!field) return;
            field.classList.add('is-invalid');
            const feedbackId = feedbackIdFor(field);
            let feedback = form.querySelector(`#${feedbackId}`);
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.id = feedbackId;
                feedback.className = 'invalid-feedback d-block';
                field.insertAdjacentElement('afterend', feedback);
            }
            feedback.textContent = message;
        };

        const clearInvalid = (field) => {
            if (!field) return;
            field.classList.remove('is-invalid');
            const feedbackId = feedbackIdFor(field);
            const feedback = form.querySelector(`#${feedbackId}`);
            if (feedback) feedback.remove();
        };

        form.addEventListener('submit', function(e) {
            console.log('Adjustment form submitted');

            // Validate required fields
            const quantity = form.querySelector('input[name="quantity"]');
            const changeType = form.querySelector('input[name="change_type"]:checked');
            const changeTypeInputs = form.querySelectorAll('input[name="change_type"]');

            if (!quantity || !quantity.value) {
                e.preventDefault();
                markInvalid(quantity, 'Quantity is required.');
                showValidationMessage('Please enter a quantity.');
                quantity?.focus();
                return false;
            }
            clearInvalid(quantity);

            if (!changeType) {
                e.preventDefault();
                changeTypeInputs.forEach((input) => input.classList.add('is-invalid'));
                showValidationMessage('Please select a change type.');
                changeTypeInputs[0]?.focus();
                return false;
            }
            changeTypeInputs.forEach((input) => input.classList.remove('is-invalid'));

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