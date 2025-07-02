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
        showFifoError('Failed to load batch source list');
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
        showFifoError('Failed to load batch source list');
    }
}

function renderFifoDetails(data) {
    const { inventory_item, batch_usage } = data;

    let html = `
        <div class="mb-3">
            <h6>${inventory_item.name}</h6>
            <p class="text-muted">Current Stock: ${inventory_item.quantity} ${inventory_item.unit}</p>
        </div>
    `;

    if (batch_usage && batch_usage.length > 0) {
        html += `
            <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead>
                        <tr>
                            <th>FIFO Source</th>
                            <th>Amount Used</th>
                            <th>Age</th>
                            <th>Freshness</th>
                            <th>Line Cost</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        batch_usage.forEach(usage => {
            const ageText = usage.age_days ? `${usage.age_days} days` : 'N/A';
            const freshnessDisplay = usage.life_remaining_percent !== null 
                ? `<span class="badge ${getLifeBadgeClass(usage.life_remaining_percent)}">${usage.life_remaining_percent}%</span>`
                : '<span class="text-muted">Non-perishable</span>';

            const lineCost = (usage.quantity_used * (usage.unit_cost || 0)).toFixed(2);

            html += `
                <tr>
                    <td>
                        <a href="/inventory/view/${inventory_item.id}#fifo-entry-${usage.fifo_id}" 
                           target="_blank" class="fifo-ingredient-link">
                            #${usage.fifo_id}
                        </a>
                    </td>
                    <td><strong>${usage.quantity_used} ${usage.unit}</strong></td>
                    <td>${ageText}</td>
                    <td>${freshnessDisplay}</td>
                    <td>$${lineCost}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
    } else {
        html += '<div class="alert alert-info">No usage data available for this ingredient in this batch.</div>';
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
            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>Ingredient</th>
                        <th>Total Used</th>
                        <th>FIFO Entry</th>
                        <th>Used</th>
                        <th>Age</th>
                        <th>Life Remaining</th>
                    </tr>
                </thead>
                <tbody>
        `;

        ingredient_summary.forEach(ingredient => {
            ingredient.fifo_usage.forEach(usage => {
                const ageText = usage.age_days ? `${usage.age_days} days` : 'N/A';
                const lifeRemainingDisplay = usage.life_remaining_percent !== null
                    ? `<span class="badge ${getLifeBadgeClass(usage.life_remaining_percent)}">${usage.life_remaining_percent}% remaining</span>`
                    : '<span class="text-muted">Non-perishable</span>';

                html += `
                    <tr>
                        <td>${ingredient.name}</td>
                        <td>${ingredient.total_used} ${ingredient.unit}</td>
                        <td><small class="text-muted">#${usage.fifo_id}</small></td>
                        <td>${usage.quantity_used} ${usage.unit}</td>
                        <td>${ageText}</td>
                        <td>${lifeRemainingDisplay}</td>
                    </tr>
                `;
            });

        });

        html += `
                </tbody>
            </table>
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

async function getLifeRemaining(fifoId) {
    try {
        const response = await fetch(`/expiration/api/life-remaining/${fifoId}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching life remaining:', error);
        return { life_remaining_percent: null, non_perishable: true };
    }
}

function showFifoError(message) {
    document.getElementById('fifoModalContent').innerHTML = `
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-triangle"></i>
            <strong>Error:</strong> ${message}
        </div>
    `;
}

);