
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

function toggleOutputFields() {
    const outputType = document.getElementById('output_type').value;
    const productFields = document.getElementById('productFields');
    const ingredientFields = document.getElementById('ingredientFields');
    
    if (outputType === 'product') {
        productFields.style.display = 'block';
        ingredientFields.style.display = 'none';
    } else {
        productFields.style.display = 'none';
        ingredientFields.style.display = 'block';
    }
}

function addIngredientRow() {
    const template = `
        <div class="ingredient-row d-flex gap-2 mb-2">
            <select name="ingredients[][id]" class="form-select ingredient-select">
                {% for ing in inventory_items if ing.type == 'ingredient' %}
                <option value="{{ ing.id }}">{{ ing.name }}</option>
                {% endfor %}
            </select>
            <input type="number" step="0.01" name="ingredients[][amount]" class="form-control ingredient-amount">
            <select name="ingredients[][unit]" class="form-select ingredient-unit">
                {% for unit in units %}
                <option value="{{ unit.name }}">{{ unit.name }}</option>
                {% endfor %}
            </select>
            <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
        </div>
    `;
    document.getElementById('ingredient-list').insertAdjacentHTML('beforeend', template);
}

function addContainerRow() {
    const template = `
        <div class="container-row d-flex gap-2 mb-2">
            <select name="containers[]" class="form-select">
                {% for item in inventory_items if item.type == 'container' %}
                <option value="{{ item.id }}">{{ item.name }}</option>
                {% endfor %}
            </select>
            <input type="number" name="container_amounts[]" class="form-control" placeholder="Quantity">
            <input type="number" step="0.01" name="container_costs[]" class="form-control" placeholder="Cost Each">
            <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
        </div>
    `;
    document.getElementById('container-list').insertAdjacentHTML('beforeend', template);
}

function addTimerRow() {
    const template = `
        <div class="timer-row d-flex gap-2 mb-2">
            <input type="text" name="timers[]" class="form-control" placeholder="Timer Name">
            <input type="number" name="timer_durations[]" class="form-control" placeholder="Duration (seconds)">
            <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
        </div>
    `;
    document.getElementById('timer-list').insertAdjacentHTML('beforeend', template);
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
