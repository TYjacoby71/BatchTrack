// Plan Production Main Script
import { BatchConfig } from './modules/batch-config.js';
import { ContainerManager } from './modules/container-management.js';
import { Validator } from './modules/validation.js';
import { FormHandler } from './modules/form-handler.js';

console.log('Plan production JavaScript loaded');

class PlanProductionApp {
    constructor() {
        this.recipe = null;
        this.scale = 1.0;
        this.baseYield = 0;
        this.unit = '';
        this.batchType = '';
        this.requiresContainers = false;

        // Initialize modules
        this.batchConfig = new BatchConfig(this);
        this.containerManager = new ContainerManager(this);
        this.validator = new Validator(this);
        this.formHandler = new FormHandler(this);

        this.init();
    }

    init() {
        console.log('🔍 INIT: Starting plan production app');
        this.loadRecipeData();
        this.bindEvents();
        this.validator.updateValidation();
    }

    loadRecipeData() {
        const recipeData = window.recipeData;
        if (recipeData) {
            this.recipe = recipeData;
            this.baseYield = parseFloat(recipeData.yield_amount) || 0;
            this.unit = recipeData.yield_unit || '';
            console.log('🔍 RECIPE: Loaded recipe data:', this.recipe);
            this.batchConfig.updateProjectedYield();
        }
    }

    bindEvents() {
        this.batchConfig.bindEvents();
        this.containerManager.bindEvents();
        this.formHandler.bindEvents();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.planProductionApp = new PlanProductionApp();
});