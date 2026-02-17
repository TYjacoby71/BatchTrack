// FIFO Modal functionality
let currentInventoryId = null;

function openFifoModal(inventoryId, batchId) {
    currentInventoryId = inventoryId;
    const modal = new bootstrap.Modal(document.getElementById('fifoInsightModal'));

    // Set modal title
    document.getElementById('fifoModalTitle').textContent = `FIFO Details for Inventory ID: ${inventoryId}`;

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
        const response = await fetch(`/batches/api/batch-inventory-summary/${batchId}`);

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const responseText = await response.text();
            throw new Error(`Response is not JSON. Content: ${responseText}`);
        }

        const data = await response.json();
        renderBatchSummary(data);
    } catch (error) {
        console.error('Error fetching batch summary:', error);
        showFifoError(`Failed to load batch inventory summary: ${error.message}`);
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
            const ageText = usage.age_days ? `${usage.age_days} days` : '1 day';
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
    const { batch, ingredient_summary, freshness_summary } = data;

    let html = `
        <div class="mb-3">
            <h6>Batch: ${batch.label_code}</h6>
            <p class="text-muted">Recipe: ${batch.recipe_name} • Scale: ${batch.scale}</p>
        </div>

        ${renderOverallFreshness(freshness_summary)}

        <div class="mb-3">
            <h6>Inventory Summary</h6>
    `;

    if (ingredient_summary && ingredient_summary.length > 0) {
        html += `
            <table class="table table-sm align-middle" id="batch-inv-summary">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Total Used</th>
                        <th>Weighted Freshness</th>
                    </tr>
                </thead>
                <tbody>
        `;

        ingredient_summary.forEach(ingredient => {
            const itemFreshness = getItemFreshnessPercent(freshness_summary, ingredient.inventory_item_id);
            const hasMultipleLots = Array.isArray(ingredient.fifo_usage) && ingredient.fifo_usage.length > 1;
            const caretBtn = hasMultipleLots
                ? `<button type="button" class="btn btn-link btn-sm p-0 me-1 align-baseline" data-item-id="${ingredient.inventory_item_id}" aria-label="Toggle lots" onclick="toggleLotsRow(${ingredient.inventory_item_id})">
                        <i id="caret-${ingredient.inventory_item_id}" class="fas fa-chevron-right"></i>
                   </button>`
                : '';

            html += `
                <tr id="item-row-${ingredient.inventory_item_id}">
                    <td>${caretBtn}<span>${ingredient.name}</span></td>
                    <td><strong>${ingredient.total_used} ${ingredient.unit}</strong></td>
                    <td>${itemFreshness !== null ? `<span class="badge ${getLifeBadgeClass(itemFreshness)}">${itemFreshness}%</span>` : '&mdash;'}</td>
                </tr>
            `;

            if (hasMultipleLots) {
                // Build hidden lots detail row
                let lotsHtml = `
                    <tr id="lots-row-${ingredient.inventory_item_id}" class="d-none">
                        <td colspan="3">
                            <div class="bg-light border rounded p-2">
                                <div class="d-flex text-muted small fw-semibold pb-1">
                                    <div class="flex-grow-1">Lot</div>
                                    <div class="text-end" style="width: 300px;">Used • Age • Life • Unit Cost</div>
                                </div>
                                <table class="table table-sm borderless m-0">
                                    <tbody>
                `;

                ingredient.fifo_usage.forEach(usage => {
                    const ageText = usage.age_days ? `${usage.age_days} days` : '1 day';
                    const lifeRemainingDisplay = usage.life_remaining_percent !== null && usage.life_remaining_percent !== undefined
                        ? `<span class="badge ${getLifeBadgeClass(usage.life_remaining_percent)}">${usage.life_remaining_percent}%</span>`
                        : '<span class="text-muted">Non-perishable</span>';
                    const unitCost = typeof usage.unit_cost === 'number' ? `$${Number(usage.unit_cost).toFixed(2)}` : '&mdash;';

                    lotsHtml += `
                        <div class="d-flex align-items-center py-1 border-top">
                            <div class="flex-grow-1">
                                <small class="text-muted">
                                    <a href="/inventory/view/${ingredient.inventory_item_id}#fifo-entry-${usage.fifo_id}"
                                       target="_blank" class="fifo-ingredient-link">
                                        #${usage.fifo_id}
                                    </a>
                                </small>
                            </div>
                            <div class="text-end" style="width: 300px;">
                                <span class="me-3">${usage.quantity_used} ${usage.unit}</span>
                                <span class="me-3">${ageText}</span>
                                ${lifeRemainingDisplay}
                                <span class="ms-3">${unitCost}</span>
                            </div>
                        </div>
                    `;
                });

                lotsHtml += `
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </td>
                    </tr>
                `;

                html += lotsHtml;
            }
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

function toggleLotsRow(inventoryItemId) {
    try {
        const row = document.getElementById(`lots-row-${inventoryItemId}`);
        const caret = document.getElementById(`caret-${inventoryItemId}`);
        if (!row || !caret) return;
        const isHidden = row.classList.contains('d-none');
        if (isHidden) {
            row.classList.remove('d-none');
            caret.classList.remove('fa-chevron-right');
            caret.classList.add('fa-chevron-down');
        } else {
            row.classList.add('d-none');
            caret.classList.remove('fa-chevron-down');
            caret.classList.add('fa-chevron-right');
        }
    } catch (e) {
        // no-op
    }
}

function renderOverallFreshness(freshness_summary) {
    if (!freshness_summary || freshness_summary.overall_freshness_percent === null || freshness_summary.overall_freshness_percent === undefined) {
        return '';
    }
    const pct = freshness_summary.overall_freshness_percent;
    const badge = `<span class="badge ${getLifeBadgeClass(pct)}">${pct}%</span>`;
    return `
        <div class="alert alert-info mb-3">
            <strong>Overall Freshness:</strong> ${badge}
        </div>
    `;
}

function getItemFreshnessPercent(freshness_summary, inventory_item_id) {
    try {
        if (!freshness_summary || !freshness_summary.items || !Array.isArray(freshness_summary.items)) return null;
        const match = freshness_summary.items.find(i => i.inventory_item_id === inventory_item_id);
        if (!match) return null;
        return match.weighted_freshness_percent ?? null;
    } catch (e) {
        return null;
    }
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

// Keep modal handlers available for inline template attributes.
// The bundler wraps files, so these must be explicitly attached to window.
if (typeof window !== 'undefined') {
    Object.assign(window, {
        openFifoModal,
        openBatchInventorySummary,
        toggleLotsRow,
    });
}