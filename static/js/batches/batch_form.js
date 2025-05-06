// Batch form functionality
function showFinishBatchModal() {
    const modal = new bootstrap.Modal(document.getElementById('finishBatchModal'));
    modal.show();
    toggleOutputFields(); // Set initial field visibility
}

function toggleOutputFields() {
    const type = document.getElementById('output_type').value;
    const productFields = document.getElementById('productFields');
    const ingredientFields = document.getElementById('ingredientFields');

    productFields.style.display = type === 'product' ? 'block' : 'none';
    ingredientFields.style.display = type === 'ingredient' ? 'block' : 'none';

    // Update required attributes
    const productSelect = productFields.querySelector('select[name="product_id"]');
    if (productSelect) {
        productSelect.required = type === 'product';
    }
}

// Add event listener when document loads
document.addEventListener('DOMContentLoaded', function() {
    const outputTypeSelect = document.getElementById('output_type');
    if (outputTypeSelect) {
        outputTypeSelect.addEventListener('change', toggleOutputFields);
    }
});

function toggleOutputFields() {
    const type = document.getElementById('output_type').value;
    document.getElementById('productFields').style.display = type === 'product' ? 'block' : 'none';
    document.getElementById('ingredientFields').style.display = type === 'ingredient' ? 'block' : 'none';
}

function markBatchFailed() {
    if (confirm('Are you sure you want to mark this batch as failed?')) {
        const batchId = window.location.pathname.split('/').pop();
        fetch(`/batches/fail/${batchId}`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('.csrf-token').value
            }
        }).then(response => {
            if (response.ok) {
                window.location.href = '/batches/';
            }
        });
    }
}

function submitFinishBatch(action) {
    const form = document.getElementById('finishBatchForm');
    const formData = new FormData(form);
    formData.append('action', action);

    const batchId = window.location.pathname.split('/').pop();

    fetch(`/batches/${batchId}/finish`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
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

function addExtraIngredientRow() {
    const template = document.getElementById('extra-ingredient-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('extra-ingredients-container').appendChild(clone);

    // Initialize Select2 on the new row's selects
    const newRow = document.getElementById('extra-ingredients-container').lastElementChild;
    const ingredientSelect = newRow.querySelector('.ingredient-select');
    const unitSelect = newRow.querySelector('.unit');

    // Handle ingredient selection change
    ingredientSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        const defaultUnit = selectedOption.getAttribute('data-default-unit');
        
        if (defaultUnit && unitSelect) {
            // Update Select2 value
            $(unitSelect).val(defaultUnit).trigger('change');
        }
    });

    $(newRow).find('.select2-input').select2({
        width: 'resolve',
        dropdownAutoWidth: true
    });
}

function saveExtras() {
    const rows = document.querySelectorAll(".extra-row");
    const extras = Array.from(rows).map(row => ({
        ingredient_id: row.querySelector(".ingredient-select").value,
        quantity: parseFloat(row.querySelector(".qty").value) || 0,
        unit: row.querySelector(".unit").value,
        cost_per_unit: parseFloat(row.querySelector(".cost").value) || 0
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
    .then(res => res.json())
    .then(data => alert("Extra ingredients saved successfully"))
    .catch(err => console.error(err));
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

