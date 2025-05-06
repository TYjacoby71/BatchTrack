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

function saveBatch(event) {
    if (event) {
        event.preventDefault();
    }

    const batchId = window.location.pathname.split('/').pop();
    const form = document.getElementById('batchForm');
    if (!form) {
        console.error('Batch form not found');
        return;
    }

    const data = {
        notes: form.querySelector('textarea[name="notes"]')?.value || '',
        tags: form.querySelector('input[name="tags"]')?.value || '',
        output_type: form.querySelector('select[name="output_type"]')?.value,
        product_id: form.querySelector('select[name="product_id"]')?.value,
        variant_label: form.querySelector('input[name="variant_label"]')?.value,
        final_quantity: parseFloat(form.querySelector('input[name="final_quantity"]')?.value) || 0,
        output_unit: form.querySelector('select[name="output_unit"]')?.value || '',
        timers: Array.from(form.querySelectorAll('.timer-row')).map(row => ({
            name: row.querySelector('input[name="timers[]"]').value,
            duration_seconds: parseInt(row.querySelector('input[name="timer_durations[]"]').value)
        }))
    };

    const csrfToken = form.querySelector('input[name="csrf_token"]').value;

    fetch(`/batches/${batchId}/save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Keep form values after save
            const notesField = form.querySelector('textarea[name="notes"]');
            const tagsField = form.querySelector('input[name="tags"]');
            if (notesField) notesField.value = data.notes || notesField.value;
            if (tagsField) tagsField.value = data.tags || tagsField.value;
            alert('Batch saved successfully');
        }
    })
    .catch(error => {
        console.error('Error saving batch:', error);
        alert('Error saving batch');
    });
}