
// Batch form functionality
function finishBatch(action) {
    const form = document.getElementById('batchForm');
    const formData = new FormData(form);
    formData.append('action', action);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': form.querySelector('input[name="csrf_token"]').value
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
        try {
            const path = window.location.pathname;
            const batchId = path.match(/\/batches\/in-progress\/(\d+)/)[1];
            
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
        } catch (error) {
            console.error('Error cancelling batch:', error);
            alert('Error cancelling batch. Please try again.');
        }
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
        ingredients: Array.from(form.querySelectorAll('.ingredient-row')).map(row => ({
            id: parseInt(row.querySelector('select[name^="ingredients"][name$="[id]"]').value),
            amount: parseFloat(row.querySelector('input[name^="ingredients"][name$="[amount]"]').value),
            unit: row.querySelector('select[name^="ingredients"][name$="[unit]"]').value
        })),
        containers: Array.from(form.querySelectorAll('.container-row')).map(row => ({
            id: parseInt(row.querySelector('select[name="containers[]"]').value),
            qty: parseInt(row.querySelector('input[name="container_amounts[]"]').value),
            cost_each: parseFloat(row.querySelector('input[name="container_costs[]"]').value) || 0
        })),
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
