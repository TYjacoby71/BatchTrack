// Plan Production Main Script - Modular Version
import { ContainerManager } from './modules/container-management.js';
import { StockChecker } from './modules/stock-check.js';
import { ValidationManager } from './modules/validation.js';
import { BatchManager } from './modules/batch-management.js';

console.log('Plan production JavaScript loaded');

class PlanProductionApp {
    constructor() {
        this.recipe = null;
        this.scale = 1.0;
        this.baseYield = 0;
        this.unit = '';
        this.batchType = '';
        this.requiresContainers = false;
        this.stockCheckResults = null;

        // Initialize managers
        this.containerManager = new ContainerManager(this);
        this.stockChecker = new StockChecker(this);
        this.validationManager = new ValidationManager(this);
        this.batchManager = new BatchManager(this);

        this.init();
    }

    init() {
        console.log('🔍 INIT: Starting plan production app');
        this.loadRecipeData();
        this.bindEvents();
        this.updateValidation();
    }

    loadRecipeData() {
        // Get recipe data from template
        const recipeData = window.recipeData;
        if (recipeData) {
            this.recipe = recipeData;
            this.baseYield = parseFloat(recipeData.yield_amount) || 0;
            this.unit = recipeData.yield_unit || '';
            console.log('🔍 RECIPE: Loaded recipe data:', this.recipe);
        }
    }

    bindEvents() {
        // Scale input
        const scaleInput = document.getElementById('batchScale');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.scale = parseFloat(scaleInput.value) || 1.0;
                this.updateProjectedYield();
                if (this.requiresContainers) {
                    this.containerManager.fetchContainerPlan();
                }
            });
        }

        // Batch type select
        const batchTypeSelect = document.getElementById('batchType');
        if (batchTypeSelect) {
            batchTypeSelect.addEventListener('change', () => {
                this.batchType = batchTypeSelect.value;
                this.updateValidation();
            });
        }

        // Container requirement toggle
        const containerToggle = document.getElementById('requiresContainers');
        if (containerToggle) {
            containerToggle.addEventListener('change', () => {
                this.requiresContainers = containerToggle.checked;
                console.log('🔍 CONTAINER TOGGLE: Requirements changed to:', this.requiresContainers);
                
                const containerCard = document.getElementById('containerManagementCard');
                if (containerCard) {
                    containerCard.style.display = this.requiresContainers ? 'block' : 'none';
                    console.log('🔍 CONTAINER TOGGLE: Card display set to:', containerCard.style.display);
                }
                
                if (this.requiresContainers) {
                    console.log('🔍 CONTAINER TOGGLE: Fetching container plan...');
                    this.containerManager.fetchContainerPlan();
                } else {
                    this.containerManager.clearContainerResults();
                }
                
                this.updateValidation();
            });
        }

        // Form submission
        const form = document.getElementById('planProductionForm');
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // Bind module events
        this.containerManager.bindEvents();
        this.stockChecker.bindEvents();
        this.validationManager.bindEvents();
        this.batchManager.bindEvents();
    }

    updateProjectedYield() {
        const projectedYield = this.baseYield * this.scale;
        const yieldDisplay = document.getElementById('projectedYield');
        if (yieldDisplay) {
            yieldDisplay.textContent = projectedYield.toFixed(2) + ' ' + this.unit;
        }
    }

    updateValidation() {
        this.validationManager.updateValidation();
    }

    handleFormSubmit(e) {
        e.preventDefault();

        if (!this.batchType) {
            alert('Please select a batch type');
            return;
        }

        console.log('Form submitted with data:', {
            scale: this.scale,
            batchType: this.batchType,
            requiresContainers: this.requiresContainers
        });
    }

    // Utility method for API calls
    async apiCall(url, data = null) {
        const options = {
            method: data ? 'POST' : 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            }
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(url, options);
        return await response.json();
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.planProductionApp = new PlanProductionApp();
});