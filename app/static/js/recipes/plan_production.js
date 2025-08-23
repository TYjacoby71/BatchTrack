// Plan Production Main Orchestrator
// This file coordinates between specialized modules

import { StockCheckManager } from './modules/stock-check.js';
import { ContainerManager } from './modules/container-management.js';
import { ValidationManager } from './modules/validation.js';
import { BatchManager } from './modules/batch-management.js';

console.log('Plan production JavaScript loaded');

class PlanProductionManager {
    constructor() {
        this.recipe = null;
        this.scale = 1.0;
        this.baseYield = 0;
        this.unit = 'units';
        this.batchType = '';
        this.requiresContainers = false;

        // Initialize managers
        this.stockManager = new StockCheckManager(this);
        this.containerManager = new ContainerManager(this);
        this.validationManager = new ValidationManager(this);
        this.batchManager = new BatchManager(this);

        this.init();
    }

    init() {
        // Get recipe data from page
        const recipeElement = document.querySelector('[data-recipe-id]');
        if (recipeElement) {
            this.recipe = {
                id: parseInt(recipeElement.dataset.recipeId),
                name: recipeElement.dataset.recipeName || 'Unknown Recipe'
            };
            this.baseYield = parseFloat(recipeElement.dataset.baseYield) || 0;
            this.unit = recipeElement.dataset.yieldUnit || 'units';
        }

        this.bindEvents();
        this.updateProjectedYield();
    }

    bindEvents() {
        // Scale input changes
        const scaleInput = document.getElementById('scale');
        if (scaleInput) {
            scaleInput.addEventListener('input', (e) => {
                this.scale = parseFloat(e.target.value) || 1.0;
                this.updateProjectedYield();
                this.stockManager.fetchStockCheck();
                if (this.requiresContainers) {
                    this.containerManager.fetchContainerPlan();
                }
            });
        }

        // Batch type selection
        const batchTypeSelect = document.getElementById('batchType');
        if (batchTypeSelect) {
            batchTypeSelect.addEventListener('change', (e) => {
                this.batchType = e.target.value;
                this.validationManager.validateForm();
            });
        }

        // Container requirement toggle
        const containerToggle = document.getElementById('requiresContainers');
        if (containerToggle) {
            containerToggle.addEventListener('change', (e) => {
                this.requiresContainers = e.target.checked;
                this.containerManager.onContainerRequirementChange();
            });
        }

        // Delegate other events to managers
        this.stockManager.bindEvents();
        this.containerManager.bindEvents();
        this.batchManager.bindEvents();

        // Initial stock check
        setTimeout(() => this.stockManager.fetchStockCheck(), 500);
    }

    updateProjectedYield() {
        const projectedYieldElement = document.getElementById('projectedYield');
        if (projectedYieldElement) {
            const projectedYield = (this.baseYield * this.scale).toFixed(2);
            projectedYieldElement.textContent = `${projectedYield} ${this.unit}`;
        }
    }

    // Shared utilities
    async apiCall(endpoint, data) {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    new PlanProductionManager();
});