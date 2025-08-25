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
        console.log('🔍 INIT DEBUG: Container manager:', !!this.containerManager);
        console.log('🔍 INIT DEBUG: Stock checker:', !!this.stockChecker);
        console.log('🔍 INIT DEBUG: Validation manager:', !!this.validationManager);
        console.log('🔍 INIT DEBUG: Batch manager:', !!this.batchManager);

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
        this.containerManager.bindEvents();
        this.stockChecker.bindEvents();
        this.validationManager.bindEvents();
        this.batchManager.bindEvents();
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
    console.log('Plan production JavaScript loaded');

    // Ensure all required elements exist before initializing
    const requiredElements = [
        'batchConfigCard',
        'containerCard',
        'stockCheckBtn',
        'requiresContainersToggle'
    ];

    let missingElements = [];
    requiredElements.forEach(id => {
        if (!document.getElementById(id)) {
            missingElements.push(id);
        }
    });

    if (missingElements.length > 0) {
        console.error('Missing required elements:', missingElements);
        return;
    }

    // Initialize the main app
    const app = new PlanProductionApp();
    window.planProductionApp = app; // Make it globally accessible for debugging

    // Add explicit container toggle handler as backup
    const containerToggle = document.getElementById('requiresContainersToggle');
    if (containerToggle) {
        containerToggle.addEventListener('change', function() {
            const containerCard = document.getElementById('containerCard');
            if (containerCard) {
                containerCard.style.display = this.checked ? 'block' : 'none';
                console.log('Container card toggled:', this.checked);
            }
        });
    }

    // Ensure stock check button is clickable
    const stockBtn = document.getElementById('stockCheckBtn');
    if (stockBtn) {
        stockBtn.style.cursor = 'pointer';
        stockBtn.removeAttribute('disabled');
    }
});