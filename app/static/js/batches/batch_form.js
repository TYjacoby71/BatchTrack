
// Global batch ID for this page
let currentBatchId;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Extract batch ID from URL
    const pathParts = window.location.pathname.split('/');
    currentBatchId = pathParts[pathParts.indexOf('batches') + 1];
    
    console.log('Batch form initialized for batch:', currentBatchId);
});

// Extra items management
function addExtraItemRow(type) {
    const container = document.getElementById('extra-ingredients-container');
    const template = document.getElementById(`extra-${type}-template`);
    
    if (!template || !container) {
        console.error('Template or container not found:', type);
        return;
    }
    
    const clone = template.content.cloneNode(true);
    container.appendChild(clone);
}

function updateRowCost(selectElement) {
    const row = selectElement.closest('.extra-row');
    const costInput = row.querySelector('.cost');
    const unitSelect = row.querySelector('.unit');
    
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const cost = selectedOption.dataset.cost || '0';
    const unit = selectedOption.dataset.unit;
    
    if (costInput) {
        costInput.value = parseFloat(cost).toFixed(2);
    }
    
    if (unitSelect && unit) {
        // Set the unit if it's an ingredient
        for (let option of unitSelect.options) {
            if (option.value === unit) {
                option.selected = true;
                break;
            }
        }
    }
}

function saveExtras() {
    if (!currentBatchId) {
        alert('Batch ID not found');
        return;
    }
    
    const extraRows = document.querySelectorAll('.extra-row');
    const extraIngredients = [];
    const extraContainers = [];
    
    extraRows.forEach(row => {
        const type = row.dataset.type;
        const itemSelect = row.querySelector('.item-select');
        const qtyInput = row.querySelector('.qty');
        const costInput = row.querySelector('.cost');
        
        if (!itemSelect.value || !qtyInput.value) return;
        
        const itemData = {
            item_id: parseInt(itemSelect.value),
            quantity: parseFloat(qtyInput.value),
            cost: parseFloat(costInput.value) || 0
        };
        
        if (type === 'ingredient') {
            const unitSelect = row.querySelector('.unit');
            itemData.unit = unitSelect ? unitSelect.value : 'g';
            extraIngredients.push(itemData);
        } else if (type === 'container') {
            extraContainers.push(itemData);
        }
    });
    
    // Send data to server
    fetch(`/batches/${currentBatchId}/add-extras`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('.csrf-token').value
        },
        body: JSON.stringify({
            extra_ingredients: extraIngredients,
            extra_containers: extraContainers
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            alert('Extra items saved successfully');
            location.reload();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error saving extras: ' + error.message);
    });
}

// Timer Functions
function startTimer(name, duration) {
    if (!currentBatchId) {
        alert('Batch ID not found');
        return;
    }
    
    fetch(`/timers/start`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('.csrf-token').value
        },
        body: JSON.stringify({
            batch_id: currentBatchId,
            name: name,
            duration: duration
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            location.reload();
        } else {
            alert('Error starting timer: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error starting timer');
    });
}

function stopTimer(timerId) {
    fetch(`/timers/${timerId}/stop`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('.csrf-token').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            location.reload();
        } else {
            alert('Error stopping timer: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error stopping timer');
    });
}

// Batch action functions
function cancelBatch() {
    if (!currentBatchId) {
        alert('Batch ID not found');
        return;
    }
    
    if (confirm('Are you sure you want to cancel this batch? This cannot be undone.')) {
        window.location.href = `/batches/${currentBatchId}/cancel`;
    }
}

function markBatchFailed() {
    if (!currentBatchId) {
        alert('Batch ID not found');
        return;
    }
    
    if (confirm('Are you sure you want to mark this batch as failed? This cannot be undone.')) {
        window.location.href = `/batches/${currentBatchId}/mark-failed`;
    }
}

function validateBatchForm() {
    // Add any validation logic here
    return true;
}

function saveBatchNotes() {
    if (!currentBatchId) {
        return Promise.reject('Batch ID not found');
    }
    
    const notesTextarea = document.querySelector('textarea[name="notes"]');
    const tagsInput = document.querySelector('input[name="tags"]');
    
    const data = {
        notes: notesTextarea ? notesTextarea.value : '',
        tags: tagsInput ? tagsInput.value : ''
    };
    
    return fetch(`/batches/${currentBatchId}/save-notes`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('.csrf-token').value
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status !== 'success') {
            throw new Error(data.message || 'Failed to save notes');
        }
        return data;
    });
}

function openBatchInventorySummary(batchId) {
    window.open(`/batches/${batchId}/inventory-summary`, '_blank');
}
