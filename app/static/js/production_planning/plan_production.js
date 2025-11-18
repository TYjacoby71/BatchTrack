import { ContainerManager } from './modules/container-management.js';
import { StockCheckManager as StockChecker } from './modules/stock-check.js';
import { ValidationManager } from './modules/validation.js';
import { BatchManager } from './modules/batch-management.js';

class PlanProductionApp {
    constructor() {
        const data = window.recipeData || {};
        this.recipe = {
            id: data.id,
            name: data.name,
            yield_amount: data.yield_amount,
            yield_unit: data.yield_unit,
            // Ensure portioning data is available to BatchManager
            portioning_data: data.portioning || null,
            is_portioned: (data.is_portioned === true || data.is_portioned === 'true')
        };
        this.baseYield = Number(data.yield_amount || 0);
        this.unit = data.yield_unit || 'units';
        this.scale = this._readScale();
        this.batchType = '';
        this.requiresContainers = false;
        this.stockChecked = false;
        this.stockCheckPassed = false;
        this.stockIssues = [];
        this.stockOverrideAcknowledged = false;

        this.containerManager = new ContainerManager(this);
        this.stockChecker = new StockChecker(this);
        this.validation = new ValidationManager(this);
        this.batchManager = new BatchManager(this);
        window.planProductionApp = this;
    }

    init() {
        this._bindCoreEvents();
        this._registerGlobalEvents();
        this.containerManager.bindEvents();
        this.stockChecker.bindEvents();
        this.validation.bindEvents();
        this.batchManager.bindEvents();

        // Expose for inline onclicks in generated HTML
        window.stockChecker = this.stockChecker;

        // Initial UI sync
        this._updateProjectedYield();
        this._updateProjectedPortions();
        this.updateValidation();

        // Hide containers if recipe is portioned
        const initData = window.recipeData || {};
        if (initData.is_portioned === true || initData.is_portioned === 'true') {
            const requiresContainersCheckbox = document.getElementById('requiresContainers');
            if (requiresContainersCheckbox) {
                requiresContainersCheckbox.checked = false;
            }
            const card = document.getElementById('containerManagementCard');
            if (card) {
                card.style.display = 'none';
            }
        }
    }

    _registerGlobalEvents() {
        window.addEventListener('recipe.yield.updated', (event) => {
            const detail = event.detail || {};
            if (!detail || detail.recipe_id !== this.recipe.id) {
                return;
            }

            if (typeof detail.yield_amount !== 'undefined') {
                this.baseYield = Number(detail.yield_amount) || 0;
                window.recipeData.yield_amount = this.baseYield;
            }
            if (detail.yield_unit) {
                this.unit = detail.yield_unit;
                window.recipeData.yield_unit = detail.yield_unit;
            }

            this._updateProjectedYield();
            this._updateProjectedPortions();

            if (this.requiresContainers) {
                const fillPct = this.containerManager.getEffectiveFillPct();
                this.containerManager.planFetcher.fetchContainerPlan({ fill_pct: fillPct });
            }
        });

        window.addEventListener('container.requirements.disable', (event) => {
            const detail = event.detail || {};
            if (detail.recipe_id && detail.recipe_id !== this.recipe.id) {
                return;
            }
            this._disableContainersRequirement();
        });
    }

    _disableContainersRequirement() {
        const requiresContainersCheckbox = document.getElementById('requiresContainers');
        if (requiresContainersCheckbox) {
            requiresContainersCheckbox.checked = false;
        }
        this.requiresContainers = false;
        const card = document.getElementById('containerManagementCard');
        if (card) {
            card.style.display = 'none';
        }
        this.containerManager.clearContainerResults();
        this.updateValidation();
    }

    _bindCoreEvents() {
        const scaleInput = document.getElementById('batchScale');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.scale = this._readScale();
                this._invalidateStockCheck('the batch scale changed');
                this._updateProjectedYield();
                this._updateProjectedPortions();
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
                this._invalidateStockCheck('container requirements changed');
                const portioned = (window.recipeData?.is_portioned === true || window.recipeData?.is_portioned === 'true');
                if (portioned && requiresContainersCheckbox.checked) {
                    // Show info card with bounce instead of enabling containers
                    const notice = document.getElementById('portioningContainerNotice');
                    if (notice) {
                        notice.classList.remove('d-none');
                        // retrigger bounce
                        notice.classList.remove('bounce');
                        void notice.offsetWidth;
                        notice.classList.add('bounce');
                    }
                    requiresContainersCheckbox.checked = false;
                    return;
                }

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

    _invalidateStockCheck(reason = 'a configuration change') {
        this.stockChecked = false;
        this.stockCheckPassed = false;
        this.stockOverrideAcknowledged = false;
        this.stockIssues = [];

        const statusElement = document.getElementById('stockCheckStatus');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    Stock check required because ${reason}.
                </div>
            `;
        }

        this.updateValidation();
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

    _updateProjectedPortions() {
        const el = document.getElementById('projectedPortions');
        if (el && this.recipe.portioning_data && this.recipe.portioning_data.portion_count) {
            const basePortions = parseInt(this.recipe.portioning_data.portion_count) || 0;
            const scaledPortions = Math.round(basePortions * (this.scale || 1));
            const portionName = this.recipe.portioning_data.portion_name || 'units';
            el.textContent = `${scaledPortions} ${portionName}`;
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