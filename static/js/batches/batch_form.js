// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
    const finishModal = document.getElementById('finishBatchModal');
    if (finishModal) {
        finishModal.addEventListener('shown.bs.modal', function () {
            toggleOutputFields();
        });
    }

    // Initialize tooltips
    var tooltips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltips.map(function (tooltip) {
        return new bootstrap.Tooltip(tooltip);
    });

    const outputTypeSelect = document.getElementById('output_type');
    if (outputTypeSelect) {
        outputTypeSelect.addEventListener('change', toggleOutputFields);
    }
});

function togglePerishableFields() {
    const isPerishable = document.getElementById('is_perishable').checked;
    const perishableFields = document.getElementById('perishableFields');
    if (perishableFields) {
        perishableFields.style.display = isPerishable ? 'block' : 'none';
    }
}

function toggleOutputFields() {
    const type = document.getElementById('output_type').value;
    const productFields = document.getElementById('productFields');
    const ingredientFields = document.getElementById('ingredientFields');

    if (productFields) {
        productFields.style.display = type === 'product' ? 'block' : 'none';
    }
    if (ingredientFields) {
        ingredientFields.style.display = type === 'ingredient' ? 'block' : 'none';
    }

    // Update required attributes
    const productSelect = productFields?.querySelector('select[name="product_id"]');
    if (productSelect) {
        productSelect.required = type === 'product';
    }
}

async function loadProductVariants() {
    const productId = document.getElementById('product_id').value;
    const variantSelect = document.getElementById('variant_label');

    if (!productId) {
        variantSelect.innerHTML = '<option value="">Select a product first</option>';
        return;
    }

    try {
        const response = await fetch(`/api/products/${productId}/variants`);
        const variants = await response.json();

        if (variants.length > 0) {
            variantSelect.innerHTML = variants.map(v => 
                `<option value="${v.name}">${v.name}</option>`
            ).join('');
        } else {
            variantSelect.innerHTML = '<option value="">No variants available</option>';
        }
    } catch (error) {
        console.error('Error loading variants:', error);
        variantSelect.innerHTML = '<option value="">Error loading variants</option>';
    }
}

function markBatchFailed() {
    if (confirm('Are you sure you want to mark this batch as failed?')) {
        const batchId = window.location.pathname.split('/').pop();
        fetch(`/finish-batch/${batchId}/fail`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
            }
        }).then(response => {
            if (response.ok) {
                window.location.href = '/batches/';
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Verify modal form exists on page load
    const modalForm = document.getElementById('finishBatchModalForm');
    if (!modalForm) {
        console.error('Initial modal form check failed - form not found on page load');
    }
});

function submitFinishBatch(action) {
    console.log('Submitting batch...');
    const modal = document.getElementById('finishBatchModal');
    const modalForm = document.getElementById('finishBatchModalForm');

    // More detailed error logging
    if (!modal || !modalForm) {
        console.error('Modal elements check failed:', {
            modalExists: !!modal,
            formExists: !!modalForm,
            formHTML: document.querySelector('#finishBatchModal .modal-body').innerHTML
        });
        alert('Error: Form elements not found. Please refresh the page.');
        return;
    }

    const formData = new FormData(modalForm);
    // Using raw CSRF token from <input>, not Flask-WTF
    const csrfTokenInput = modalForm.querySelector('input[name="csrf_token"]');
    
    if (!csrfTokenInput) {
        console.error('CSRF token not found');
        alert('Error: Security token missing. Please refresh the page.');
        return;
    }

    const csrfToken = csrfTokenInput.value;
    formData.append('action', action);

    const batchId = window.location.pathname.split('/').pop();

    fetch(`/finish_batch/${batchId}/complete`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': csrfToken,
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.error || 'Failed to finish batch');
            });
        }
        window.location.href = '/batches/';
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error finishing batch: ' + error.message);
    });
}

function saveBatchAndExit() {
    const batchId = window.location.pathname.split('/').pop();
    const notes = document.querySelector('textarea[name="notes"]').value;
    const tags = document.querySelector('input[name="tags"]').value;

    fetch(`/batches/${batchId}/update-notes`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('.csrf-token').value
        },
        body: JSON.stringify({
            notes: notes,
            tags: tags
        })
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '/batches/';
        }
    });
}

function updateRowCost(selectElement) {
    const cost = selectElement.options[selectElement.selectedIndex].dataset.cost;
    const costInput = selectElement.parentElement.querySelector('.cost');
    costInput.value = cost;
}

function addExtraIngredientRow() {
    const template = document.getElementById('extra-ingredient-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('extra-ingredients-container').appendChild(clone);

    // Initialize Select2 on the new row's selects
    const newRow = document.getElementById('extra-ingredients-container').lastElementChild;
    $(newRow).find('.select2-input').select2({
        width: 'resolve',
        dropdownAutoWidth: true
    });

    // Set initial cost
    const select = newRow.querySelector('.ingredient-select');
    updateRowCost(select);
}

function addExtraContainerRow() {
    const template = document.getElementById('extra-container-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('extra-containers-container').appendChild(clone);

    // Initialize Select2 on the new row's selects
    const newRow = document.getElementById('extra-containers-container').lastElementChild;
    $(newRow).find('.select2-input').select2({
        width: 'resolve',
        dropdownAutoWidth: true
    });
}

function saveExtraContainers() {
    const rows = document.querySelectorAll(".extra-container-row");
    const extras = Array.from(rows).map(row => ({
        container_id: parseInt(row.querySelector(".container-select").value),
        quantity: parseInt(row.querySelector(".qty").value) || 0,
        cost_per_unit: parseFloat(row.querySelector(".cost").value) || 0,
        container_name: row.querySelector(".container-select option:checked").text
    }));

    const batchId = window.location.pathname.split('/').pop();
    fetch(`/batches/extras-containers/${batchId}`, {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRFToken": document.querySelector('input[name="csrf_token"]').value
        },
        body: JSON.stringify({ extras })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => {
                throw new Error(err.error || 'Failed to save extra containers');
            });
        }
        return res.json();
    })
    .then(data => {
        if (data.errors) {
            const errorMsg = data.errors.map(err => 
                `${err.container}: ${err.message} (Available: ${err.available})`
            ).join('\n');
            alert("Cannot save extra containers:\n" + errorMsg);
        } else {
            alert("Extra containers saved successfully");
            window.location.reload();
        }
    })
    .catch(err => {
        alert(err.message);
        console.error(err);
    });
}

function saveExtras() {
    const rows = document.querySelectorAll(".extra-row");
    const extras = Array.from(rows).map(row => ({
        ingredient_id: row.querySelector(".ingredient-select").value,
        quantity: parseFloat(row.querySelector(".qty").value) || 0,
        unit: row.querySelector(".unit").value,
        cost_per_unit: parseFloat(row.querySelector(".cost").value) || 0,
        ingredient_name: row.querySelector(".ingredient-select option:checked").text
    }));

    const batchId = window.location.pathname.split('/').pop();
    fetch(`/batches/extras/${batchId}`, {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRFToken": document.querySelector('input[name="csrf_token"]').value
        },
        body: JSON.stringify({ extras })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => {
                throw new Error(err.error || 'Failed to save extras');
            });
        }
        return res.json();
    })
    .then(data => {
        if (data.errors) {
            const errorMsg = data.errors.map(err => 
                `${err.ingredient}: ${err.message} (Available: ${err.available} ${err.available_unit})`
            ).join('\n');
            function displayErrors(errors) {
                const message = errors.map(err =>
                    `❌ ${err.ingredient}: ${err.message}`
                ).join("\n\n");

                alert("Save failed:\n\n" + message);
            }

            displayErrors(data.errors);
        } else {
            alert("Extra ingredients saved successfully");
            window.location.reload();
        }
    })
    .catch(err => {
        alert(err.message);
        console.error(err);
    });
}

function cancelBatch() {
    if (confirm('Cancel this batch? Ingredients will be returned to inventory.')) {
        const batchId = window.location.pathname.split('/').pop();
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/batches/cancel/${batchId}`;

        const csrf = document.querySelector('.csrf-token').value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = csrf;

        form.appendChild(csrfInput);
        document.body.appendChild(form);
        form.submit();
    }
}