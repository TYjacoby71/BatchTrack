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
            console.log('🔧 PLAN_PRODUCTION: Initializing modules...');

            // Initialize modules
            this.containerManager = new ContainerManager();
            this.containerProgressBar = new ContainerProgressBar();

            // Make globally available for debugging
            window.containerManager = this.containerManager;
            window.containerProgressBar = this.containerProgressBar;

            // Initialize event listeners
            this.initializeEventListeners();

            // Load initial data if container management is enabled
            const requiresContainers = document.getElementById('requiresContainers');
            if (requiresContainers && requiresContainers.checked) {
                await this.loadInitialData();
            }

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

        // Container requirement toggle
        const requiresContainers = document.getElementById('requiresContainers');
        if (requiresContainers) {
            requiresContainers.addEventListener('change', () => {
                this.handleContainerToggle();
            });
        }

        // Stock check button
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => {
                this.handleStockCheck();
            });
        }
    }

    async loadInitialData() {
        try {
            console.log('🔧 PLAN_PRODUCTION: Loading initial container data...');
            if (this.containerManager) {
                await this.containerManager.refreshContainerOptions();
            }
        } catch (error) {
            console.error('🔧 PLAN_PRODUCTION: Error loading initial data:', error);
        }
    }

    async handleStockCheck() {
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        const stockCheckResults = document.getElementById('stockCheckResults');
        const stockCheckStatus = document.getElementById('stockCheckStatus');

        if (!window.recipeData?.id) {
            this.showStockError('Recipe data not available');
            return;
        }

        const scale = this.getCurrentScale();
        const recipeId = window.recipeData.id;

        try {
            // Update button state
            stockCheckBtn.disabled = true;
            stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';

            if (stockCheckStatus) {
                stockCheckStatus.innerHTML = '<div class="alert alert-info">Checking stock availability...</div>';
            }

            const response = await fetch(`/production-planning/${recipeId}/stock-check`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value || ''
                },
                body: JSON.stringify({
                    recipe_id: recipeId,
                    scale: scale
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Stock check failed');
            }

            this.renderStockCheckResults(result);

        } catch (error) {
            console.error('🔧 STOCK_CHECK: Error:', error);
            this.showStockError(error.message);
        } finally {
            // Reset button state
            stockCheckBtn.disabled = false;
            stockCheckBtn.innerHTML = '<i class="fas fa-search"></i> Check Stock Availability';

            if (stockCheckStatus) {
                stockCheckStatus.innerHTML = '';
            }
        }
    }

    renderStockCheckResults(result) {
        const stockCheckResults = document.getElementById('stockCheckResults');
        if (!stockCheckResults) return;

        const { ingredients, overall_sufficient } = result;

        let html = `
            <div class="alert ${overall_sufficient ? 'alert-success' : 'alert-warning'}">
                <i class="fas ${overall_sufficient ? 'fa-check-circle' : 'fa-exclamation-triangle'}"></i>
                <strong>${overall_sufficient ? 'Stock Available' : 'Stock Issues Found'}</strong>
            </div>
        `;

        if (ingredients && ingredients.length > 0) {
            html += '<div class="table-responsive"><table class="table table-sm">';
            html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Status</th></tr></thead><tbody>';

            ingredients.forEach(ingredient => {
                const statusClass = ingredient.sufficient ? 'text-success' : 'text-danger';
                const statusIcon = ingredient.sufficient ? 'fa-check' : 'fa-times';

                html += `
                    <tr>
                        <td>${ingredient.name}</td>
                        <td>${ingredient.required_amount} ${ingredient.unit}</td>
                        <td>${ingredient.available_amount} ${ingredient.unit}</td>
                        <td class="${statusClass}">
                            <i class="fas ${statusIcon}"></i>
                            ${ingredient.sufficient ? 'Available' : 'Insufficient'}
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table></div>';
        }

        stockCheckResults.innerHTML = html;
    }

    showStockError(message) {
        const resultsContainer = document.getElementById('stockCheckResults');
        if (resultsContainer) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Error: ${message}</div>`;
        }
    }

    async handleScaleChange() {
        console.log('🔧 PLAN_PRODUCTION: Scale changed, refreshing container options...');

        // Refresh container analysis when scale changes
        if (this.containerManager) {
            await this.containerManager.refreshContainerOptions();
        }
    }

    async handleContainerToggle() {
        const requiresContainersToggle = document.getElementById('requiresContainers');
        const containerManagementCard = document.getElementById('containerManagementCard');

        if (!requiresContainersToggle || !containerManagementCard) return;

        console.log('🔧 PLAN_PRODUCTION: Container toggle changed:', requiresContainersToggle.checked);

        if (requiresContainersToggle.checked) {
            // Show container management card
            containerManagementCard.style.display = 'block';

            // Refresh container options
            if (this.containerManager) {
                await this.containerManager.refreshContainerOptions();
            }
        } else {
            // Hide container management card
            containerManagementCard.style.display = 'none';

            // Clear container results
            if (this.containerManager && this.containerManager.renderer) {
                this.containerManager.renderer.clearResults();
            }
        }
    }

    getCurrentScale() {
        const scaleInput = document.getElementById('scaleFactorInput') || document.getElementById('scaleInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }

    showError(message) {
        console.error('🔧 PLAN_PRODUCTION: Error:', message);

        // Show error in container management if available
        if (this.containerManager) {
            this.containerManager.showError(message);
        }

        // Also show in stock check area
        const stockCheckResults = document.getElementById('stockCheckResults');
        if (stockCheckResults) {
            stockCheckResults.innerHTML = `<div class="alert alert-danger">Error: ${message}</div>`;
        }
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🔧 PLAN_PRODUCTION: DOM loaded, initializing app...');
    new PlanProductionApp();
});