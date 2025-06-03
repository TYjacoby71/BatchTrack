
// FIFO Modal functionality
let currentInventoryId = null;

function openFifoModal(inventoryId, ingredientName, batchId) {
    currentInventoryId = inventoryId;
    const modal = new bootstrap.Modal(document.getElementById('fifoInsightModal'));
    
    // Set modal title
    document.getElementById('fifoModalTitle').textContent = `FIFO Details: ${ingredientName}`;
    
    // Show loading content
    document.getElementById('fifoModalContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading FIFO details...</p>
        </div>
    `;
    
    // Show modal
    modal.show();
    
    // Fetch FIFO data
    fetchFifoDetails(inventoryId, batchId);
}

function openBatchInventorySummary(batchId) {
    const modal = new bootstrap.Modal(document.getElementById('fifoInsightModal'));
    
    // Set modal title
    document.getElementById('fifoModalTitle').textContent = 'Batch Inventory Summary';
    
    // Show loading content
    document.getElementById('fifoModalContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading batch inventory summary...</p>
        </div>
    `;
    
    // Show modal
    modal.show();
    
    // Fetch batch summary
    fetchBatchInventorySummary(batchId);
}

async function fetchFifoDetails(inventoryId, batchId) {
    try {
        const response = await fetch(`/api/fifo-details/${inventoryId}?batch_id=${batchId}`);
        const data = await response.json();
        
        if (response.ok) {
            renderFifoDetails(data);
        } else {
            showFifoError(data.error || 'Failed to load FIFO details');
        }
    } catch (error) {
        console.error('Error fetching FIFO details:', error);
        showFifoError('Network error occurred');
    }
}

async function fetchBatchInventorySummary(batchId) {
    try {
        const response = await fetch(`/api/batch-inventory-summary/${batchId}`);
        const data = await response.json();
        
        if (response.ok) {
            renderBatchSummary(data);
        } else {
            showFifoError(data.error || 'Failed to load batch summary');
        }
    } catch (error) {
        console.error('Error fetching batch summary:', error);
        showFifoError('Network error occurred');
    }
}

function renderFifoDetails(data) {
    const { inventory_item, fifo_entries, batch_usage } = data;
    
    let html = `
        <div class="mb-3">
            <h6>Item: ${inventory_item.name}</h6>
            <p class="text-muted">${inventory_item.type} • Current Stock: ${inventory_item.quantity} ${inventory_item.unit}</p>
        </div>
    `;
    
    if (batch_usage && batch_usage.length > 0) {
        html += `
            <div class="mb-4">
                <h6>Usage in This Batch</h6>
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>FIFO Entry</th>
                            <th>Amount Used</th>
                            <th>Age</th>
                            <th>Life Remaining</th>
                            <th>Cost/Unit</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        batch_usage.forEach(usage => {
            const ageText = usage.age_days ? `${usage.age_days} days` : 'N/A';
            const lifeRemaining = usage.life_remaining_percent !== null 
                ? `<span class="badge ${getLifeBadgeClass(usage.life_remaining_percent)}">${usage.life_remaining_percent}%</span>`
                : '<span class="text-muted">Non-perishable</span>';
            
            html += `
                <tr>
                    <td><small class="text-muted">#${usage.fifo_id}</small></td>
                    <td><strong>${usage.quantity_used} ${usage.unit}</strong></td>
                    <td>${ageText}</td>
                    <td>${lifeRemaining}</td>
                    <td>$${(usage.unit_cost || 0).toFixed(2)}</td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
    }
    
    if (fifo_entries && fifo_entries.length > 0) {
        html += `
            <div class="mb-3">
                <h6>Current FIFO Entries (Available Stock)</h6>
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>FIFO ID</th>
                            <th>Available</th>
                            <th>Age</th>
                            <th>Life Remaining</th>
                            <th>Date Added</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        fifo_entries.forEach(entry => {
            const ageText = entry.age_days ? `${entry.age_days} days` : 'N/A';
            const lifeRemaining = entry.life_remaining_percent !== null 
                ? `<span class="badge ${getLifeBadgeClass(entry.life_remaining_percent)}">${entry.life_remaining_percent}%</span>`
                : '<span class="text-muted">Non-perishable</span>';
            
            html += `
                <tr>
                    <td><small class="text-muted">#${entry.fifo_id}</small></td>
                    <td><strong>${entry.remaining_quantity} ${entry.unit}</strong></td>
                    <td>${ageText}</td>
                    <td>${lifeRemaining}</td>
                    <td>${new Date(entry.timestamp).toLocaleDateString()}</td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
    } else {
        html += '<div class="alert alert-info">No FIFO entries available for this item.</div>';
    }
    
    document.getElementById('fifoModalContent').innerHTML = html;
}

function renderBatchSummary(data) {
    const { batch, ingredient_summary } = data;
    
    let html = `
        <div class="mb-3">
            <h6>Batch: ${batch.label_code}</h6>
            <p class="text-muted">Recipe: ${batch.recipe_name} • Scale: ${batch.scale}</p>
        </div>
        
        <div class="mb-3">
            <h6>Inventory Sources Summary</h6>
    `;
    
    if (ingredient_summary && ingredient_summary.length > 0) {
        html += `
            <div class="accordion" id="batchSummaryAccordion">
        `;
        
        ingredient_summary.forEach((ingredient, index) => {
            const collapseId = `collapse${index}`;
            const headingId = `heading${index}`;
            
            html += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="${headingId}">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" 
                                data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
                            ${ingredient.name} 
                            <span class="ms-2 badge bg-primary">${ingredient.total_used} ${ingredient.unit}</span>
                        </button>
                    </h2>
                    <div id="${collapseId}" class="accordion-collapse collapse" 
                         aria-labelledby="${headingId}" data-bs-parent="#batchSummaryAccordion">
                        <div class="accordion-body">
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>FIFO Entry</th>
                                        <th>Used</th>
                                        <th>Age</th>
                                        <th>Life Remaining</th>
                                    </tr>
                                </thead>
                                <tbody>
            `;
            
            ingredient.fifo_usage.forEach(usage => {
                const ageText = usage.age_days ? `${usage.age_days} days` : 'N/A';
                const lifeRemaining = usage.life_remaining_percent !== null 
                    ? `<span class="badge ${getLifeBadgeClass(usage.life_remaining_percent)}">${usage.life_remaining_percent}%</span>`
                    : '<span class="text-muted">Non-perishable</span>';
                
                html += `
                    <tr>
                        <td><small class="text-muted">#${usage.fifo_id}</small></td>
                        <td>${usage.quantity_used} ${usage.unit}</td>
                        <td>${ageText}</td>
                        <td>${lifeRemaining}</td>
                    </tr>
                `;
            });
            
            html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
            </div>
        `;
    } else {
        html += '<div class="alert alert-info">No ingredient usage data available for this batch.</div>';
    }
    
    html += '</div>';
    
    document.getElementById('fifoModalContent').innerHTML = html;
}

function getLifeBadgeClass(percent) {
    if (percent === null) return 'bg-secondary';
    if (percent >= 70) return 'bg-success';
    if (percent >= 30) return 'bg-warning';
    return 'bg-danger';
}

function showFifoError(message) {
    document.getElementById('fifoModalContent').innerHTML = `
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-triangle"></i>
            <strong>Error:</strong> ${message}
        </div>
    `;
}

// Set up the "View Full Inventory" button click handler
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('viewFullInventory').addEventListener('click', function() {
        if (currentInventoryId) {
            window.open(`/inventory/view/${currentInventoryId}?fifo=true`, '_blank');
        }
    });
});
