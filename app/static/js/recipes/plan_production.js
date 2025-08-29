// Plan Production Main Script - Modular Version
import { StockChecker } from './modules/stock-check.js';
import { ContainerManager } from './modules/container-management.js';

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

        this.init();
    }

    init() {
        console.log('🔍 INIT: Starting plan production app');
        console.log('🔍 INIT DEBUG: Container manager:', !!this.containerManager);
        console.log('🔍 INIT DEBUG: Stock checker:', !!this.stockChecker);

        this.loadRecipeData();
        this.bindEvents();
        this.updateProjectedYield(); // Initialize projected yield display
        this.updateValidation();
    }

    loadRecipeData() {
        // Get recipe data from data attributes on the container
        const container = document.querySelector('[data-recipe-id]');
        if (container) {
            this.recipe = {
                id: parseInt(container.dataset.recipeId),
                name: container.dataset.recipeName,
                predicted_yield: parseFloat(container.dataset.baseYield) || 0,
                predicted_yield_unit: container.dataset.yieldUnit || 'ml'
            };
            console.log('🔍 RECIPE: Loaded recipe data from data attributes:', this.recipe);
        } else if (window.recipeData) {
            this.recipe = window.recipeData;
            console.log('🔍 RECIPE: Loaded recipe data from window:', this.recipe);
        } else {
            // Try to load from script tag as fallback
            const recipeDataScript = document.getElementById('recipeData');
            if (recipeDataScript) {
                try {
                    this.recipe = JSON.parse(recipeDataScript.textContent);
                    console.log('🔍 RECIPE: Loaded recipe data from script tag:', this.recipe);
                } catch (e) {
                    console.error('🚨 RECIPE: Failed to parse recipe data:', e);
                    this.recipe = null;
                }
            } else {
                console.error('🚨 RECIPE: No recipe data found');
                this.recipe = null;
            }
        }

        if (this.recipe) {
            // Use the correct field names from the Recipe model
            this.baseYield = parseFloat(this.recipe.predicted_yield) || 0;
            this.unit = this.recipe.predicted_yield_unit || 'ml';

            // Add compatibility fields for any legacy code
            this.recipe.yield_amount = this.recipe.predicted_yield;
            this.recipe.yield_unit = this.recipe.predicted_yield_unit;

            console.log('🔍 RECIPE: Base yield:', this.baseYield, 'Unit:', this.unit);
        }
    }

    bindEvents() {
        // Scale input
        const scaleInput = document.getElementById('batchScale');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                const newScale = parseFloat(scaleInput.value) || 1.0;
                console.log('🔍 SCALE DEBUG: Scale changed from', this.scale, 'to', newScale);
                this.scale = newScale;
                this.updateProjectedYield();

                // Update container plan if containers are required
                if (this.requiresContainers) {
                    console.log('🔍 SCALE DEBUG: Updating container plan for new scale');
                    // Assuming ContainerManager now delegates to ContainerPlanFetcher
                    if (this.containerManager && typeof this.containerManager.fetchContainerPlan === 'function') {
                        this.containerManager.fetchContainerPlan();
                    } else {
                        console.error('🚨 SCALE DEBUG ERROR: Container manager or fetchContainerPlan not available');
                    }
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
        console.log('🔍 CONTAINER TOGGLE DEBUG: Element found:', !!containerToggle);

        if (containerToggle) {
            console.log('🔍 CONTAINER TOGGLE DEBUG: Adding event listener');
            containerToggle.addEventListener('change', () => {
                this.requiresContainers = containerToggle.checked;
                console.log('🔍 CONTAINER TOGGLE: Requirements changed to:', this.requiresContainers);

                const containerCard = document.getElementById('containerManagementCard');
                console.log('🔍 CONTAINER TOGGLE DEBUG: Container card found:', !!containerCard);

                if (containerCard) {
                    containerCard.style.display = this.requiresContainers ? 'block' : 'none';
                    console.log('🔍 CONTAINER TOGGLE: Card display set to:', containerCard.style.display);
                    console.log('🔍 CONTAINER TOGGLE DEBUG: Card visibility classes:', containerCard.className);
                }

                if (this.requiresContainers) {
                    console.log('🔍 CONTAINER TOGGLE: Fetching container plan...');
                    console.log('🔍 CONTAINER TOGGLE DEBUG: Container manager available:', !!this.containerManager);
                    if (this.containerManager && typeof this.containerManager.fetchContainerPlan === 'function') {
                        this.containerManager.fetchContainerPlan();
                    } else {
                        console.error('🚨 CONTAINER TOGGLE ERROR: Container manager or fetchContainerPlan not available');
                    }
                } else {
                    console.log('🔍 CONTAINER TOGGLE: Clearing container results...');
                    if (this.containerManager && typeof this.containerManager.clearContainerResults === 'function') {
                        this.containerManager.clearContainerResults();
                    } else {
                        console.error('🚨 CONTAINER TOGGLE ERROR: Container manager or clearContainerResults not available');
                    }
                }

                this.updateValidation();
            });
        } else {
            console.error('🚨 CONTAINER TOGGLE ERROR: requiresContainers element not found');
            // Try to find elements with similar IDs for debugging
            const allInputs = document.querySelectorAll('input[type="checkbox"]');
            console.log('🔍 CONTAINER TOGGLE DEBUG: All checkboxes found:', allInputs.length);
            allInputs.forEach((input, index) => {
                console.log(`🔍 CONTAINER TOGGLE DEBUG: Checkbox ${index}: id="${input.id}", name="${input.name}"`);
            });
        }

        // Form submission
        const form = document.getElementById('planProductionForm');
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // Bind module events
        if (this.containerManager && typeof this.containerManager.bindEvents === 'function') {
            this.containerManager.bindEvents();
        } else {
            console.warn('WARN: ContainerManager.bindEvents not found or not applicable.');
        }
        if (this.stockChecker && typeof this.stockChecker.bindEvents === 'function') {
            this.stockChecker.bindEvents();
        } else {
            console.warn('WARN: StockChecker.bindEvents not found or not applicable.');
        }
    }

    updateProjectedYield() {
        const projectedYieldElement = document.getElementById('projectedYield');
        console.log('🔍 PROJECTED YIELD DEBUG: Element found:', !!projectedYieldElement);
        console.log('🔍 PROJECTED YIELD DEBUG: Base yield:', this.baseYield, 'Scale:', this.scale, 'Unit:', this.unit);

        if (projectedYieldElement) {
            const projectedValue = (this.baseYield * this.scale).toFixed(2);
            projectedYieldElement.textContent = `${projectedValue} ${this.unit}`;
            console.log('🔍 PROJECTED YIELD DEBUG: Updated to:', `${projectedValue} ${this.unit}`);
        }
    }

    updateValidation() {
        // Basic validation - check if batch type is selected
        const batchTypeSelect = document.getElementById('batchType');
        const isValid = batchTypeSelect && batchTypeSelect.value !== '';

        console.log('🔍 VALIDATION: Checking form validity...');
        console.log('🔍 VALIDATION: Valid:', isValid, 'Reasons:', isValid ? [] : ['Select batch type'], 'Warnings:', []);

        // You can add more validation logic here as needed
        return isValid;
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

        // Additional submission logic might go here, potentially using other modules.
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

        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json();
                console.error(`API Error (${response.status}):`, errorData);
                throw new Error(`API request failed: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API Call Exception:', error);
            throw error; // Re-throw the error to be handled by the caller
        }
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content ||
               document.querySelector('input[name="csrf_token"]')?.value;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if recipeData is available before initializing
    if (window.recipeData) {
        window.planProductionApp = new PlanProductionApp();
    } else {
        console.error('🚨 DOMContentLoaded Error: window.recipeData not found. Cannot initialize PlanProductionApp.');
        // Optionally, provide a fallback or disable functionality if recipeData is essential.
    }
});