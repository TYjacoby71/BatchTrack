// Stock Check Management Module
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
        this.processedResults = null; // Added to store processed data for downloads
    }

    bindEvents() {
        console.log('🔍 STOCK CHECK DEBUG: Binding events...');
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        console.log('🔍 STOCK CHECK DEBUG: Stock check button found:', !!stockCheckBtn);

        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => {
                console.log('🔍 STOCK CHECK DEBUG: Button clicked!');
                this.performStockCheck();
            });
            console.log('🔍 STOCK CHECK DEBUG: Event listener added successfully');
        } else {
            console.error('🚨 STOCK CHECK ERROR: Stock check button not found in DOM');
        }
    }

    async performStockCheck() {
        console.log('🔍 STOCK CHECK DEBUG: performStockCheck called');

        if (!this.main.recipe) {
            console.warn('🔍 STOCK CHECK: No recipe available');
            alert('No recipe loaded');
            return;
        }

        console.log('🔍 STOCK CHECK: Starting stock check for recipe', this.main.recipe.id, 'scale:', this.main.scale);

        // Show loading state
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        const originalText = stockCheckBtn.innerHTML;
        stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
        stockCheckBtn.disabled = true;

        try {
            // Use the recipe stock check endpoint (internally uses USCS)
            const response = await fetch('/recipes/stock/check', {
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

            console.log('🔍 STOCK CHECK: Response status:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.stockCheckResults = await response.json();
            console.log('🔍 STOCK CHECK: Results received:', this.stockCheckResults);

            this.displayStockResults(this.stockCheckResults);

            // Handle any conversion errors that need drawer intervention
            if (this.stockCheckResults.stock_check) {
                this.handleConversionErrors(this.stockCheckResults.stock_check);
            }
        } catch (error) {
            console.error('🚨 STOCK CHECK ERROR:', error);

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
        console.log('🔍 STOCK CHECK: Displaying results');
        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults) {
            console.warn('🔍 STOCK CHECK: No results element found');
            return;
        }

        console.log('🔍 STOCK CHECK: Full results object:', this.stockCheckResults);

        // Handle the USCS response structure
        const stockData = this.stockCheckResults.stock_check || [];
        const allAvailable = this.stockCheckResults.status === 'ok';

        console.log('🔍 STOCK CHECK: Stock data:', stockData);
        console.log('🔍 STOCK CHECK: All available:', allAvailable);

        // All items from USCS are ingredients by default
        const ingredientData = stockData;

        if (!ingredientData || ingredientData.length === 0) {
            stockResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> There are no ingredients selected in this recipe. Please edit your recipe and add ingredients.</div>';
            this.main.stockChecked = true;
            this.main.stockCheckPassed = true;  // No ingredients means no stock issues
            this.main.updateValidation();
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
        html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Unit</th><th>Status</th></tr></thead><tbody>';

        let allIngredientsAvailable = true;

        ingredientData.forEach(result => {
            const needed = result.needed_amount || result.needed_quantity || result.quantity_needed || 0;
            const available = result.available_quantity || 0;

            let status, statusClass, displayAvailable = available.toFixed(2);

            // Check for conversion errors first
            if (result.conversion_details?.error_code) {
                status = 'CONVERSION ERROR';
                statusClass = 'bg-warning';
                displayAvailable = 'Fix Conversion';
                allIngredientsAvailable = false;
            } else {
                // Normal stock check logic
                const isAvailable = result.is_available !== false && available >= needed;
                if (!isAvailable) {
                    allIngredientsAvailable = false;
                }
                status = isAvailable ? 'OK' : 'NEEDED';
                statusClass = isAvailable ? 'bg-success' : 'bg-danger';
            }

            html += `<tr>
                <td>${result.ingredient_name || result.item_name || 'Unknown'}</td>
                <td>${needed.toFixed(2)}</td>
                <td>${displayAvailable}</td>
                <td>${result.unit || result.needed_unit || result.available_unit || ''}</td>
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

        // Check for conversion errors that need wall of drawers treatment
        this.handleConversionErrors(this.stockCheckResults.stock_check || []);

        // Update the main status
        this.main.stockChecked = true;
        this.main.stockCheckPassed = allIngredientsAvailable;
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
        console.error('🚨 STOCK CHECK ERROR: Displaying error:', message);

        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults) {
            console.error('🚨 STOCK CHECK ERROR: stockCheckResults element not found');
            return;
        }

        const statusElement = document.getElementById('stockCheckStatus');
        if (!statusElement) {
            console.error('🚨 STOCK CHECK ERROR: stockCheckStatus element not found');
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

    handleConversionErrors(stockResults) {
        for (const item of stockResults) {
            if (item.conversion_details?.error_code && item.conversion_details?.requires_drawer) {
                const errorCode = item.conversion_details.error_code;
                
                console.log(`🔍 STOCK CHECK: Conversion error ${errorCode} requires drawer intervention`);

                // Prepare drawer request data
                const drawerData = {
                    error_type: 'conversion',
                    error_code: errorCode,
                    error_message: item.conversion_details.error_message || 'Conversion error occurred',
                    modal_url: this.getModalUrlForError(errorCode, item),
                    success_event: this.getSuccessEventForError(errorCode),
                    retry_callback: () => {
                        console.log('🔍 RETRYING STOCK CHECK after fixing conversion error...');
                        this.performStockCheck();
                    }
                };

                // Send universal drawer request
                window.dispatchEvent(new CustomEvent('openDrawer', {
                    detail: drawerData
                }));
            } else if (item.conversion_details?.error_code) {
                // Log non-drawer errors for debugging
                console.log(`🔍 STOCK CHECK: Conversion error ${item.conversion_details.error_code} - no drawer needed`);
            }
        }
    }

    getModalUrlForError(errorCode, item) {
        switch (errorCode) {
            case 'MISSING_DENSITY':
                return `/api/drawer-actions/conversion/density-modal/${item.item_id || item.ingredient_id || item.id}`;
            
            case 'MISSING_CUSTOM_MAPPING':
            case 'UNSUPPORTED_CONVERSION':
                const params = new URLSearchParams({
                    from_unit: item.conversion_details.error_data?.from_unit || '',
                    to_unit: item.conversion_details.error_data?.to_unit || ''
                });
                return `/api/drawer-actions/conversion/unit-mapping-modal?${params}`;
            
            case 'UNKNOWN_SOURCE_UNIT':
            case 'UNKNOWN_TARGET_UNIT':
                // For unknown units, we redirect to unit manager instead of modal
                window.open('/conversion/units', '_blank');
                return null;
            
            default:
                return null;
        }
    }

    getSuccessEventForError(errorCode) {
        switch (errorCode) {
            case 'MISSING_DENSITY':
                return 'densityUpdated';
            case 'MISSING_CUSTOM_MAPPING':
            case 'UNSUPPORTED_CONVERSION':
                return 'unitMappingCreated';
            default:
                return null;
        }
    }

    retryStockCheck() {
        console.log('🔍 RETRY: Retrying stock check after fixing conversion error');
        this.performStockCheck();
    }

    async openDensityModal(errorDetails) {
        try {
            const response = await fetch(`/api/drawer-actions/density-modal/${errorDetails.ingredient_id}`);
            const data = await response.json();

            if (data.success) {
                // Inject modal HTML into page
                document.body.insertAdjacentHTML('beforeend', data.modal_html);

                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('densityFixModal'));
                modal.show();

                // Listen for density update
                window.addEventListener('densityUpdated', (event) => {
                    console.log('🔍 DENSITY UPDATED:', event.detail);
                    // Retry stock check automatically
                    this.performStockCheck();
                }, { once: true });

                // Clean up modal when closed
                document.getElementById('densityFixModal').addEventListener('hidden.bs.modal', function() {
                    this.remove();
                }, { once: true });
            }
        } catch (error) {
            console.error('🔍 DENSITY MODAL ERROR:', error);
        }
    }

    async openUnitMappingModal(errorDetails) {
        try {
            const params = new URLSearchParams({
                from_unit: errorDetails.from_unit,
                to_unit: errorDetails.to_unit
            });

            const response = await fetch(`/api/drawer-actions/unit-mapping-modal?${params}`);
            const data = await response.json();

            if (data.success) {
                // Inject modal HTML into page
                document.body.insertAdjacentHTML('beforeend', data.modal_html);

                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('unitMappingFixModal'));
                modal.show();

                // Listen for mapping creation
                window.addEventListener('unitMappingCreated', (event) => {
                    console.log('🔍 UNIT MAPPING CREATED:', event.detail);
                    // Retry stock check automatically
                    this.retryStockCheck();
                }, { once: true });

                // Clean up modal when closed
                document.getElementById('unitMappingFixModal').addEventListener('hidden.bs.modal', function() {
                    this.remove();
                }, { once: true });
            }
        } catch (error) {
            console.error('🔍 UNIT MAPPING MODAL ERROR:', error);
        }
    }

    openUnitCreationModal(errorDetails) {
        // For now, redirect to unit manager
        // TODO: Implement inline unit creation modal
        window.open('/conversion/units', '_blank');
    }

    retryStockCheck() {
        console.log('🔍 RETRYING STOCK CHECK after fixing conversion error...');
        // Trigger stock check again
        this.performStockCheck();
    }
}

// Export alias for backward compatibility
export { StockCheckManager as StockChecker };