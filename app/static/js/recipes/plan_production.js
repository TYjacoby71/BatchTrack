/**
 * Plan Production Main Script
 * 
 * Coordinates the production planning interface using the simplified module architecture.
 */

import { ContainerManager } from './modules/container-management.js';
import { ContainerProgressBar } from './modules/container-progress-bar.js';
import { StockCheckManager } from './modules/stock-check-manager.js';


class PlanProductionApp {
    constructor() {
        this.containerManager = null;
        this.containerProgressBar = null;
        this.stockChecker = null;
        this.isInitialized = false;
        
        // Initialize recipe data from global window object
        this.recipe = window.recipeData || null;
        this.scale = 1.0;
        
        // Add validation state
        this.stockChecked = false;
        this.stockCheckPassed = false;

        this.init();
    }

    async init() {
        if (this.isInitialized) return;

        try {
            console.log('🔧 PLAN_PRODUCTION: Initializing modules...');

            // Initialize stock checker with proper separation
            this.stockChecker = new StockCheckManager(this);
            console.log('🔍 PLAN_PRODUCTION: Initializing stock checker...');
            this.stockChecker.bindEvents();

            // Initialize container manager separately
            this.containerManager = new ContainerManager();
            console.log('🔍 PLAN_PRODUCTION: Initializing container manager...');

            // Ensure both systems are independent
            console.log('🔍 PLAN_PRODUCTION: Both stock check and container management initialized independently');


            // Make globally available for debugging
            window.containerManager = this.containerManager;
            window.stockChecker = this.stockChecker; // Make stockChecker globally available
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

        // Stock check is handled by StockCheckManager
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

    

    async handleScaleChange() {
        // Update scale from input
        this.scale = this.getCurrentScale();
        console.log('🔧 PLAN_PRODUCTION: Scale changed to:', this.scale);

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

    getCSRFToken() {
        return document.querySelector('input[name="csrf_token"]')?.value || '';
    }

    updateValidation() {
        // Update UI based on validation state
        console.log('🔧 PLAN_PRODUCTION: Validation state updated - stockChecked:', this.stockChecked, 'stockCheckPassed:', this.stockCheckPassed);
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