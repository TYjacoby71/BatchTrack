// Stock Check Management Module
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
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
            // Use the recipe plan route which includes stock checking
            const response = await fetch(`/recipes/${this.main.recipe.id}/plan`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.main.getCSRFToken()
                },
                body: JSON.stringify({
                    scale: this.main.scale,
                    check_containers: false
                })
            });

            console.log('🔍 STOCK CHECK: Response status:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.stockCheckResults = await response.json();
            console.log('🔍 STOCK CHECK: Results received:', this.stockCheckResults);

            if (this.stockCheckResults.success) {
                this.displayStockResults();
            } else {
                this.displayStockError(this.stockCheckResults.error || 'Stock check failed');
            }
        } catch (error) {
            console.error('🚨 STOCK CHECK ERROR:', error);
            this.displayStockError(`Network error during stock check: ${error.message}`);
        } finally {
            // Restore button state
            stockCheckBtn.innerHTML = originalText;
            stockCheckBtn.disabled = false;
        }
    }

    displayStockResults() {
        console.log('🔍 STOCK CHECK: Displaying results');
        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults || !this.stockCheckResults?.success) {
            console.warn('🔍 STOCK CHECK: No results element or unsuccessful result');
            return;
        }

        console.log('🔍 STOCK CHECK: Full results object:', this.stockCheckResults);

        // Handle the actual structure from the production planning service
        const stockData = this.stockCheckResults.stock_results || [];
        const allAvailable = this.stockCheckResults.all_available || false;
        const feasible = this.stockCheckResults.feasible || false;
        const status = this.stockCheckResults.status || 'unknown';
        const issues = this.stockCheckResults.issues || [];
        const recommendations = this.stockCheckResults.recommendations || [];

        console.log('🔍 STOCK CHECK: Stock data:', stockData);
        console.log('🔍 STOCK CHECK: All available:', allAvailable, 'Feasible:', feasible, 'Status:', status);

        if (!stockData || stockData.length === 0) {
            stockResults.innerHTML = '<div class="alert alert-info">No ingredients found for this recipe.</div>';
            return;
        }

        // Show status alert
        let statusAlert = '';
        if (!feasible) {
            if (status === 'insufficient_ingredients') {
                statusAlert = '<div class="alert alert-warning mb-3"><strong>Production Not Feasible:</strong> Some ingredients have insufficient stock. See details below.</div>';
            } else if (status === 'no_containers') {
                statusAlert = '<div class="alert alert-warning mb-3"><strong>Production Not Feasible:</strong> No suitable containers available.</div>';
            } else if (status === 'cost_prohibitive') {
                statusAlert = '<div class="alert alert-warning mb-3"><strong>Production Not Feasible:</strong> Cost exceeds budget constraints.</div>';
            }
        } else {
            statusAlert = '<div class="alert alert-success mb-3"><strong>Production Feasible:</strong> All ingredients are available!</div>';
        }

        let html = statusAlert;
        html += '<div class="table-responsive"><table class="table table-sm">';
        html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Status</th></tr></thead><tbody>';

        stockData.forEach(ingredient => {
            const statusClass = ingredient.available ? 'text-success' : 'text-danger';
            const statusIcon = ingredient.available ? '✓' : '⚠';
            const shortageText = ingredient.shortage > 0 ? ` (short: ${ingredient.shortage})` : '';
            
            html += `<tr>
                <td>${ingredient.ingredient_name || 'Unknown'}</td>
                <td>${ingredient.needed_amount} ${ingredient.unit}</td>
                <td>${ingredient.available_quantity} ${ingredient.unit}</td>
                <td class="${statusClass}">${statusIcon} ${ingredient.available ? 'Available' : 'Insufficient'}${shortageText}</td>
            </tr>`;
        });

        html += '</tbody></table></div>';

        // Add issues and recommendations
        if (issues.length > 0) {
            html += '<div class="mt-3"><h6>Issues:</h6><ul>';
            issues.forEach(issue => {
                html += `<li class="text-warning">${issue}</li>`;
            });
            html += '</ul></div>';
        }

        if (recommendations.length > 0) {
            html += '<div class="mt-3"><h6>Recommendations:</h6><ul>';
            recommendations.forEach(rec => {
                html += `<li class="text-info">${rec}</li>`;
            });
            html += '</ul></div>';
        }

        stockResults.innerHTML = html;ilable</th><th>Status</th></tr></thead><tbody>';

        stockData.forEach(ingredient => {
            console.log('🔍 STOCK CHECK: Processing ingredient:', ingredient);
            
            const needed = ingredient.needed_amount || ingredient.required_quantity || 0;
            const available = ingredient.available_quantity || 0;
            const unit = ingredient.unit || ingredient.needed_unit || '';
            const name = ingredient.ingredient_name || ingredient.name || 'Unknown';
            const isAvailable = ingredient.available !== false && available >= needed;
            
            const status = isAvailable ? 'Available' : 'Insufficient';
            const statusClass = isAvailable ? 'text-success' : 'text-warning';

            html += `
                <tr>
                    <td>${name}</td>
                    <td>${needed.toFixed(2)} ${unit}</td>
                    <td>${available.toFixed(2)} ${unit}</td>
                    <td class="${statusClass}"><i class="fas fa-${isAvailable ? 'check' : 'exclamation-triangle'}"></i> ${status}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
        stockResults.innerHTML = html;

        const statusElement = document.getElementById('stockCheckStatus');
        if (statusElement) {
            statusElement.className = `alert ${allAvailable ? 'alert-success' : 'alert-warning'}`;
            statusElement.innerHTML = allAvailable
                ? '<i class="fas fa-check-circle"></i> All ingredients available for production'
                : '<i class="fas fa-exclamation-triangle"></i> Some ingredients have insufficient stock';
        }

        // Update validation
        if (this.main && this.main.validationManager && typeof this.main.validationManager.updateValidation === 'function') {
            this.main.validationManager.updateValidation();
        } else {
            console.warn("🔍 STOCK CHECK: ValidationManager or updateValidation method not available");
        }
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
}

// Export alias for backward compatibility
export { StockCheckManager as StockChecker };