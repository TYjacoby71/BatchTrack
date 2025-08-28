// Plan Production Main Script - Modular Version
import { StockChecker } from './modules/stock-check.js';
import { ContainerManager } from './modules/container-management.js';
import { ContainerPlanFetcher } from './modules/container-plan-fetcher.js';
import { ContainerRenderer } from './modules/container-renderer.js';
import { ContainerProgressBar } from './modules/container-progress-bar.js';
import { ManualContainerMode } from './modules/manual-container-mode.js';
import { FormValidator } from './modules/validation.js';

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
        this.validationManager = new FormValidator(this); // Changed to FormValidator as per the provided changes
        // Removed BatchManager as it was not included in the provided changes.
        // If BatchManager is still needed, it should be imported and instantiated here.

        this.init();
    }

    init() {
        console.log('🔍 INIT: Starting plan production app');
        console.log('🔍 INIT DEBUG: Container manager:', !!this.containerManager);
        console.log('🔍 INIT DEBUG: Stock checker:', !!this.stockChecker);
        console.log('🔍 INIT DEBUG: Validation manager:', !!this.validationManager);
        // console.log('🔍 INIT DEBUG: Batch manager:', !!this.batchManager); // Commented out as BatchManager is not used

        this.loadRecipeData();
        this.bindEvents();
        this.updateProjectedYield(); // Initialize projected yield display
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
        // The following calls assume that the imported modules now have their own bindEvents or similar initialization methods
        // that should be called here. If ContainerManager itself doesn't handle all sub-module binding, those would need explicit calls.
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
        if (this.validationManager && typeof this.validationManager.bindEvents === 'function') {
            this.validationManager.bindEvents();
        } else {
            console.warn('WARN: FormValidator.bindEvents not found or not applicable.');
        }
        // Removed call to BatchManager.bindEvents() as it's no longer imported.
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
        // Ensure validationManager is an instance of FormValidator (or has a similar method)
        if (this.validationManager && typeof this.validationManager.updateValidation === 'function') {
            this.validationManager.updateValidation();
        } else {
            console.error('🚨 VALIDATION ERROR: Validation manager or updateValidation method not available.');
        }
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