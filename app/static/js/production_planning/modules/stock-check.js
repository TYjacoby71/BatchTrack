import { logger as baseLogger } from '../../utils/logger.js';
const logger = {
    debug: (msg, ...args) => baseLogger.debug(`STOCK_CHECK: ${msg}`, ...args),
    info: (msg, ...args) => baseLogger.info(`STOCK_CHECK: ${msg}`, ...args),
    warn: (msg, ...args) => baseLogger.warn(`STOCK_CHECK: ${msg}`, ...args),
    error: (msg, ...args) => baseLogger.error(`STOCK_CHECK: ${msg}`, ...args)
};

const BLOCKING_STATUSES = new Set(['NEEDED', 'OUT_OF_STOCK', 'DENSITY_MISSING', 'ERROR']);

// Stock Check Management Module
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
        this.processedResults = null; // Added to store processed data for downloads
        this.stockCheckTimeout = null; // For debouncing
    }

    bindEvents() {
        logger.debug('Binding events...');
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        logger.debug('Stock check button found:', !!stockCheckBtn);

        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => {
                logger.debug('Button clicked!');
                this.performStockCheck();
            });
            logger.debug('Event listener added successfully');
        } else {
            logger.error('Stock check button not found in DOM');
        }
    }

    async performStockCheck() {
        const recipeId = this.main.recipe ? this.main.recipe.id : 'N/A';
        const scale = this.main.scale || 'N/A';
        logger.debug(`Performing stock check: recipe=${recipeId}, scale=${scale}`);

        if (!this.main.recipe) {
            logger.warn('No recipe available');
            alert('No recipe loaded');
            return;
        }

        // Show loading state
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        const originalText = stockCheckBtn.innerHTML;
        stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
        stockCheckBtn.disabled = true;

        try {
            // Use the recipe stock check endpoint (internally uses USCS)
            const response = await fetch('/production-planning/stock/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.main.getCSRFToken()
                },
                body: JSON.stringify({
                    recipe_id: this.main.recipe.id,
                    scale: this.main.scale
                })
            });

            logger.debug(`Stock check response status: ${response.status}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.stockCheckResults = data;

            // Drawer opening is now handled globally by DrawerInterceptor.
            // We still display the partial results as usual.

            this.displayStockResults(this.stockCheckResults);
            logger.debug(`Stock check completed - status: ${response.status}, all_ok: ${data.all_ok}`);

        } catch (error) {
            logger.error('Stock check failed:', error);

            // More specific error handling
            let errorMessage = 'Stock check failed';
            if (error.message.includes('Cannot read properties of undefined')) {
                errorMessage = 'Stock check failed: Missing required components. Please refresh the page.';
            } else if (error.name === 'TypeError') {
                errorMessage = `Stock check failed: ${error.message}`;
            } else {
                errorMessage = `Stock check failed: ${error.message}`;
            }

            this.displayStockError(errorMessage);
        } finally {
            // Restore button state
            stockCheckBtn.innerHTML = originalText;
            stockCheckBtn.disabled = false;
        }
    }

    displayStockResults() {
        logger.debug('Displaying results');
        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults) {
            logger.warn('No results element found');
            return;
        }

        logger.debug('Full results object:', this.stockCheckResults);

        // Handle the USCS response structure
        const ingredientData = this.stockCheckResults.stock_check || [];
        const blockingItems = [];
        const allAvailable = this.stockCheckResults.status === 'ok'; // Assuming 'ok' means all available

        logger.debug('Stock data:', ingredientData);
        logger.debug('All available:', allAvailable);

        if (!ingredientData || ingredientData.length === 0) {
            stockResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> There are no ingredients selected in this recipe. Please edit your recipe and add ingredients.</div>';
            this.main.stockChecked = true;
            this.main.stockCheckPassed = true;  // No ingredients means no stock issues
            this.main.stockIssues = [];
            this.main.stockOverrideAcknowledged = false;
            this.main.updateValidation();
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
        html += '<thead><tr><th>Item</th><th>Required</th><th>Available</th><th>Unit</th><th>Status</th></tr></thead><tbody>';

        let allIngredientsAvailable = true;

        ingredientData.forEach(result => {
            logger.debug('Stock check item:', result.ingredient_name || result.item_name, {
                needed_quantity: result.needed_quantity,
                available_quantity: result.available_quantity,
                raw_stock: result.raw_stock,
                formatted_available: result.formatted_available,
                formatted_needed: result.formatted_needed
            });

            const needed = result.needed_amount || result.needed_quantity || result.quantity_needed || 0;

            // Use raw_stock if available (actual inventory), otherwise fall back to available_quantity
            const available = result.raw_stock !== undefined ? result.raw_stock : (result.available_quantity || 0);

            let status, statusClass, displayAvailable, displayNeeded;

            // Always set displayNeeded first
            displayNeeded = result.formatted_needed || `${needed.toFixed(2)} ${result.needed_unit || result.unit || ''}`;

            // Check for conversion errors first
            if (result.conversion_details?.error_code) {
                status = 'CONVERSION ERROR';
                statusClass = 'bg-warning';
                displayAvailable = result.formatted_available || 'Fix Conversion';
                allIngredientsAvailable = false;
                blockingItems.push({
                    name: result.ingredient_name || result.item_name || 'Unknown',
                    needed,
                    available,
                    unit: result.available_unit || result.needed_unit || result.unit || '',
                    status
                });

                // Debug: log the full result structure for conversion errors
                console.log('🔧 STOCK CHECK DEBUG: Full conversion error result:', JSON.stringify(result, null, 2));

                // Note: Drawer opening is handled globally by DrawerInterceptor
                // The response already contains drawer_payload at the top level which triggers the global handler
                // No need to manually dispatch drawer events here to avoid duplicates
                if (result.conversion_details?.drawer_payload) {
                    console.log('🔧 STOCK CHECK: Drawer payload found in conversion_details (handled by global interceptor)');
                } else if (result.drawer_payload) {
                    console.log('🔧 STOCK CHECK: Drawer payload found at result level (handled by global interceptor)');
                } else if (result.conversion_result?.drawer_payload) {
                    console.log('🔧 STOCK CHECK: Drawer payload found in conversion_result (handled by global interceptor)');
                } else {
                    console.log('🔧 STOCK CHECK DEBUG: No drawer_payload found in any expected location for conversion error');
                }
            } else {
                // Normal stock check logic
                const isAvailable = result.is_available !== false && available >= needed;
                if (!isAvailable) {
                    allIngredientsAvailable = false;
                }
                status = isAvailable ? 'OK' : 'NEEDED';
                statusClass = isAvailable ? 'bg-success' : 'bg-danger';

                // Use formatted_available if provided, otherwise format the raw value
                displayAvailable = result.formatted_available || `${available.toFixed(2)} ${result.stock_unit || result.available_unit || ''}`;

                const normalizedStatus = (result.status || status || '').toString().toUpperCase();
                if (!isAvailable || BLOCKING_STATUSES.has(normalizedStatus)) {
                    blockingItems.push({
                        name: result.ingredient_name || result.item_name || 'Unknown',
                        needed,
                        available,
                        unit: result.available_unit || result.needed_unit || result.unit || '',
                        status: normalizedStatus || (isAvailable ? 'OK' : 'NEEDED')
                    });
                }
            }

            const displayUnit = result.available_unit || result.needed_unit || result.unit || '';

            html += `<tr>
                <td>${result.ingredient_name || result.item_name || 'Unknown'}</td>
                <td>${displayNeeded}</td>
                <td>${displayAvailable}</td>
                <td>${displayUnit}</td>
                <td><span class="badge ${statusClass}">${status}</span></td>
            </tr>`;
        });

        html += '</tbody></table></div>';

        // Add action buttons
        html += `
            <div class="d-flex gap-2 mt-3">
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="stockChecker.downloadCSV()">
                    <i class="fas fa-download"></i> Download CSV
                </button>
                <button type="button" class="btn btn-outline-primary btn-sm" onclick="stockChecker.downloadShoppingList()">
                    <i class="fas fa-shopping-cart"></i> Shopping List
                </button>
            </div>
        `;

        stockResults.innerHTML = html;

        // Update the main status
        this.main.stockChecked = true;
        this.main.stockCheckPassed = allIngredientsAvailable && blockingItems.length === 0;
        this.main.stockOverrideAcknowledged = false;
        this.main.stockIssues = blockingItems;
        this.main.stockCheckResults = ingredientData;
        this.main.updateValidation();

        // Store processed results for CSV/shopping list
        this.processedResults = ingredientData.map(result => ({
            ingredient: result.ingredient_name || result.item_name || 'Unknown',
            needed: result.needed_amount || result.needed_quantity || result.quantity_needed || 0,
            available: result.available_quantity || 0,
            unit: result.unit || result.needed_unit || result.available_unit || '',
            status: (result.is_available !== false && (result.available_quantity || 0) >= (result.needed_amount || result.needed_quantity || result.quantity_needed || 0)) ? 'OK' : 'NEEDED'
        }));
    }

    displayStockError(message) {
        logger.error('Displaying error:', message);

        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults) {
            logger.error('stockCheckResults element not found');
            return;
        }

        const statusElement = document.getElementById('stockCheckStatus');
        if (!statusElement) {
            logger.error('stockCheckStatus element not found');
            return;
        }

        stockResults.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> ${message}
            </div>
        `;

        statusElement.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> Stock check failed: ${message}
            </div>
        `;
    }

    downloadCSV() {
        if (!this.processedResults?.length) return;

        let csv = "Ingredient,Required,Available,Unit,Status\n";
        this.processedResults.forEach(row => {
            csv += `${row.ingredient},${row.needed.toFixed(2)},${row.available.toFixed(2)},${row.unit},${row.status}\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'stock_check_report.csv';
        link.click();
    }

    downloadShoppingList() {
        if (!this.processedResults?.length) return;

        const needed = this.processedResults.filter(item => item.status === 'NEEDED');
        if (!needed.length) {
            alert('No items need restocking!');
            return;
        }

        let text = "Shopping List\n=============\n\n";
        needed.forEach(item => {
            const missing = Math.max(0, item.needed - item.available);
            text += `${item.ingredient}: ${missing.toFixed(2)} ${item.unit}\n`;
        });

        const blob = new Blob([text], { type: 'text/plain' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'shopping_list.txt';
        link.click();
    }


}

// Export alias for backward compatibility
export { StockCheckManager as StockChecker };