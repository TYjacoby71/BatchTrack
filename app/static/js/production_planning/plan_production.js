import { ContainerManager } from './modules/container-management.js';
import { StockCheckManager as StockChecker } from './modules/stock-check.js';
import { ValidationManager } from './modules/validation.js';
import { BatchManager } from './modules/batch-management.js';

class PlanProductionApp {
    constructor() {
        const data = window.recipeData || {};
        this.recipe = { id: data.id, name: data.name, yield_amount: data.yield_amount, yield_unit: data.yield_unit };
        this.baseYield = Number(data.yield_amount || 0);
        this.unit = data.yield_unit || 'units';
        this.scale = this._readScale();
        this.batchType = '';
        this.requiresContainers = false;

        this.containerManager = new ContainerManager(this);
        this.stockChecker = new StockChecker(this);
        this.validation = new ValidationManager(this);
        this.batchManager = new BatchManager(this);
    }

    init() {
        this._bindCoreEvents();
        this.containerManager.bindEvents();
        this.stockChecker.bindEvents();
        this.validation.bindEvents();
        this.batchManager.bindEvents();

        // Expose for inline onclicks in generated HTML
        window.stockChecker = this.stockChecker;

        // Initial UI sync
        this._updateProjectedYield();
        this.updateValidation();
    }

    _bindCoreEvents() {
        const scaleInput = document.getElementById('batchScale');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.scale = this._readScale();
                this._updateProjectedYield();
                if (this.requiresContainers) {
                    this.containerManager.onContainerRequirementChange();
                }
                this.updateValidation();
            });
        }

        const batchTypeSelect = document.getElementById('batchType');
        if (batchTypeSelect) {
            batchTypeSelect.addEventListener('change', (e) => {
                this.batchType = e.target.value;
                console.log('Batch type selected:', this.batchType);
                this.updateValidation();
            });
        }

        const requiresContainersCheckbox = document.getElementById('requiresContainers');
        if (requiresContainersCheckbox) {
            requiresContainersCheckbox.addEventListener('change', () => {
                this.requiresContainers = !!requiresContainersCheckbox.checked;
                const card = document.getElementById('containerManagementCard');
                if (card) {
                    card.style.display = this.requiresContainers ? 'block' : 'none';
                }
                if (this.requiresContainers) {
                    this.containerManager.onContainerRequirementChange();
                } else {
                    this.containerManager.clearContainerResults();
                }
                this.updateValidation();
            });
        }
    }

    _readScale() {
        const val = parseFloat(document.getElementById('batchScale')?.value || '1');
        return isNaN(val) || val <= 0 ? 1 : val;
    }

    _updateProjectedYield() {
        const el = document.getElementById('projectedYield');
        if (el) {
            const projected = (this.baseYield || 0) * (this.scale || 1);
            el.textContent = `${projected} ${this.unit}`;
        }
    }

    updateValidation() {
        this.validation.updateValidation();
    }

    getCSRFToken() {
        const input = document.querySelector('input[name="csrf_token"]');
        const meta = document.querySelector('meta[name="csrf-token"]');
        return input?.value || meta?.content || '';
    }

    async apiCall(endpoint, payload = {}, options = {}) {
        const resp = await fetch(endpoint, {
            method: options.method || 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
                ...(options.headers || {})
            },
            body: options.method === 'GET' ? undefined : JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new PlanProductionApp();
    app.init();
});