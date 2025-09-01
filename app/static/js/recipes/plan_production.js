/**
 * Plan Production Main Script
 * 
 * Coordinates the production planning interface using the simplified module architecture.
 */

import { ContainerManager } from './modules/container-management.js';
import { ContainerProgressBar } from './modules/container-progress-bar.js';

class PlanProductionApp {
    constructor() {
        this.containerManager = null;
        this.containerProgressBar = null;
        this.isInitialized = false;

        this.init();
    }

    async init() {
        if (this.isInitialized) return;

        try {
            // Initialize modules
            this.containerManager = new ContainerManager();
            this.containerProgressBar = new ContainerProgressBar();

            // Make globally available
            window.containerManager = this.containerManager;
            window.containerProgressBar = this.containerProgressBar;

            // Initialize event listeners
            this.initializeEventListeners();

            // Load initial data
            await this.loadInitialData();

            this.isInitialized = true;
            console.log('Plan Production App initialized successfully');

        } catch (error) {
            console.error('Error initializing Plan Production App:', error);
            this.showError('Failed to initialize production planning interface');
        }
    }

    initializeEventListeners() {
        // Scale factor changes
        const scaleInput = document.getElementById('scaleFactorInput');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.handleScaleChange();
            });
        }

        // Stock check button
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => {
                this.performStockCheck();
            });
        }

        // Start batch button
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (startBatchBtn) {
            startBatchBtn.addEventListener('click', () => {
                this.startBatch();
            });
        }
    }

    async loadInitialData() {
        // Load initial container data if needed
        if (this.containerManager && window.recipeData?.id) {
            await this.containerManager.refreshContainerOptions();
        }
    }

    async performStockCheck() {
        if (!window.recipeData?.id) {
            console.error('Recipe ID not available for stock check');
            return;
        }

        try {
            const scaleInput = document.getElementById('scaleInput');
            const scale = scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;

            const response = await fetch(`/production-planning/${window.recipeData.id}/plan`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    recipe_id: window.recipeData.id,
                    scale: scale
                })
            });

            const result = await response.json();

            if (result.success) {
                this.displayStockResults(result.stock_results || []);
            } else {
                console.error('Stock check failed:', result.error);
                this.showStockError(result.error);
            }

        } catch (error) {
            console.error('Error performing stock check:', error);
            this.showStockError('Failed to perform stock check');
        }
    }

    displayStockResults(stockResults) {
        const resultsContainer = document.getElementById('stockCheckResults');
        if (!resultsContainer) return;

        if (stockResults.length === 0) {
            resultsContainer.innerHTML = '<div class="alert alert-info">No ingredients to check for this recipe.</div>';
            return;
        }

        const allOk = stockResults.every(result => result.status === 'OK');
        const alertClass = allOk ? 'alert-success' : 'alert-warning';

        let html = `<div class="alert ${alertClass}">
            ${allOk ? '✅ All ingredients are available!' : '⚠ Some ingredients need attention'}
        </div>
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>Ingredient</th>
                    <th>Required</th>
                    <th>Available</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>`;

        stockResults.forEach(result => {
            const statusClass = result.status === 'OK' ? 'text-success' : 
                               result.status === 'LOW' ? 'text-warning' : 'text-danger';
            html += `
                <tr>
                    <td>${result.name || result.item_name}</td>
                    <td>${result.formatted_needed || `${result.needed} ${result.needed_unit}`}</td>
                    <td>${result.formatted_available || `${result.available} ${result.available_unit}`}</td>
                    <td><span class="${statusClass}">${result.status}</span></td>
                </tr>`;
        });

        html += '</tbody></table>';
        resultsContainer.innerHTML = html;
    }

    showStockError(message) {
        const resultsContainer = document.getElementById('stockCheckResults');
        if (resultsContainer) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Error: ${message}</div>`;
        }
    }

    async handleScaleChange() {
        // Refresh container analysis when scale changes
        if (this.containerManager) {
            await this.containerManager.refreshContainerOptions();
        }
    }

    async performStockCheck() {
        try {
            const stockCheckBtn = document.getElementById('stockCheckBtn');
            const stockCheckResults = document.getElementById('stockCheckResults');

            if (stockCheckBtn) {
                stockCheckBtn.disabled = true;
                stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
            }

            const recipeData = window.recipeData;
            const scaleFactor = this.getScaleFactor();

            const response = await fetch('/api/check-stock-availability', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    recipe_id: recipeData.id,
                    scale_factor: scaleFactor
                })
            });

            const result = await response.json();

            if (stockCheckResults) {
                if (result.success) {
                    this.renderStockCheckResults(result);
                } else {
                    stockCheckResults.innerHTML = `<div class="alert alert-danger">${result.error}</div>`;
                }
            }

        } catch (error) {
            console.error('Error performing stock check:', error);
            const stockCheckResults = document.getElementById('stockCheckResults');
            if (stockCheckResults) {
                stockCheckResults.innerHTML = '<div class="alert alert-danger">Failed to check stock availability</div>';
            }
        } finally {
            const stockCheckBtn = document.getElementById('stockCheckBtn');
            if (stockCheckBtn) {
                stockCheckBtn.disabled = false;
                stockCheckBtn.innerHTML = '<i class="fas fa-search"></i> Check Stock Availability';
            }
        }
    }

    renderStockCheckResults(result) {
        const stockCheckResults = document.getElementById('stockCheckResults');
        if (!stockCheckResults) return;

        const { ingredients, overall_sufficient } = result;

        let html = `<div class="alert ${overall_sufficient ? 'alert-success' : 'alert-warning'}">
            <strong>${overall_sufficient ? 'Stock Available' : 'Stock Issues Found'}</strong>
        </div>`;

        if (ingredients && ingredients.length > 0) {
            html += '<div class="table-responsive"><table class="table table-sm">';
            html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Status</th></tr></thead><tbody>';

            ingredients.forEach(ingredient => {
                const statusClass = ingredient.is_sufficient ? 'text-success' : 'text-danger';
                const statusIcon = ingredient.is_sufficient ? '✅' : '❌';

                html += `<tr>
                    <td>${ingredient.ingredient_name}</td>
                    <td>${ingredient.required_amount} ${ingredient.required_unit}</td>
                    <td>${ingredient.available_amount} ${ingredient.available_unit}</td>
                    <td class="${statusClass}">${statusIcon} ${ingredient.is_sufficient ? 'Sufficient' : 'Insufficient'}</td>
                </tr>`;
            });

            html += '</tbody></table></div>';
        }

        stockCheckResults.innerHTML = html;
    }

    async startBatch() {
        try {
            const selectedContainers = this.containerManager.getSelectedContainers();
            if (!selectedContainers || selectedContainers.length === 0) {
                this.showError('Please select containers before starting the batch');
                return;
            }

            const recipeData = window.recipeData;
            const scaleFactor = this.getScaleFactor();

            const response = await fetch('/batches/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    recipe_id: recipeData.id,
                    scale_factor: scaleFactor,
                    selected_containers: selectedContainers
                })
            });

            const result = await response.json();

            if (result.success) {
                window.location.href = result.redirect_url || '/batches/';
            } else {
                this.showError(result.error || 'Failed to start batch');
            }

        } catch (error) {
            console.error('Error starting batch:', error);
            this.showError('Failed to start batch');
        }
    }

    getScaleFactor() {
        const scaleInput = document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }

    showError(message) {
        // Show error in a consistent way across the app
        const errorContainer = document.getElementById('globalErrors') || document.body;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        errorContainer.appendChild(errorDiv);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.planProductionApp = new PlanProductionApp();
});