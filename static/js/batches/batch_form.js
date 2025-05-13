// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeForm();
    initializeTooltips();
});

function initializeForm() {
    const outputType = document.getElementById('output_type');
    if (outputType) {
        outputType.addEventListener('change', toggleProductFields);
        toggleProductFields(); // Initial toggle
    }

    const productSelect = document.getElementById('product_id');
    if (productSelect) {
        productSelect.addEventListener('change', loadProductVariants);
    }
}

function initializeTooltips() {
    const tooltips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltips.map(function(tooltip) {
        return new bootstrap.Tooltip(tooltip);
    });
}

function toggleProductFields() {
    const outputType = document.getElementById('output_type');
    const productFields = document.getElementById('productFields');

    if (productFields && outputType) {
        productFields.style.display = outputType.value === 'product' ? 'block' : 'none';

        // Toggle required attributes
        const productSelect = document.getElementById('product_id');
        if (productSelect) {
            productSelect.required = outputType.value === 'product';
        }
    }
}

async function loadProductVariants() {
    const productId = document.getElementById('product_id').value;
    const variantSelect = document.getElementById('variant_label');

    if (!productId || !variantSelect) return;

    try {
        const response = await fetch(`/api/products/${productId}/variants`);
        const variants = await response.json();

        variantSelect.innerHTML = variants.length ? 
            variants.map(v => `<option value="${v.name}">${v.name}</option>`).join('') :
            '<option value="">No variants available</option>';
    } catch (error) {
        console.error('Error loading variants:', error);
        variantSelect.innerHTML = '<option value="">Error loading variants</option>';
    }
}

function submitBatchCompletion() {
    const form = document.getElementById('finishBatchModalForm');
    if (!form) {
        console.error('Batch completion form not found');
        return;
    }
    console.log('Submitting batch...');
    form.submit();
                throw new Error(err.error || 'Failed to complete batch');
            });
        }
        window.location.href = '/batches/';
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error completing batch: ' + error.message);
    });
}

function cancelBatch() {
    if (!confirm('Cancel this batch? Ingredients will be returned to inventory.')) {
        return;
    }

    const batchId = window.location.pathname.split('/').pop();
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/batches/cancel/${batchId}`;

    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = document.querySelector('.csrf-token').value;

    form.appendChild(csrfInput);
    document.body.appendChild(form);
    form.submit();
}

function togglePerishableFields() {
    const isPerishable = document.getElementById('is_perishable').checked;
    const perishableFields = document.getElementById('perishableFields');
    if (perishableFields) {
        perishableFields.style.display = isPerishable ? 'block' : 'none';
    }
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