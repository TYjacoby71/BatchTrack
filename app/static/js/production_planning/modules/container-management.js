// Import required modules
import { ContainerPlanFetcher } from './container-plan-fetcher.js';
import { ContainerRenderer } from './container-renderer.js';
import { ContainerProgressBar } from './container-progress-bar.js';
import { ManualContainerMode } from './manual-container-mode.js';
import { logger } from '../../utils/logger.js';

// Auto-Fill Container Mode Module
class AutoFillContainerMode {
    constructor(containerManager) {
        this.container = containerManager;
    }

    activate() {
        logger.debug('AUTO-FILL MODE: Activating auto-fill container selection');
        this.container.planFetcher.fetchContainerPlan();
    }
}
// Container Management Main Controller
export class ContainerManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.containerPlan = null;
        this.fetchingPlan = false;
        this.lastPlanResult = null;

        // Initialize sub-modules
        this.planFetcher = new ContainerPlanFetcher(this);
        this.renderer = new ContainerRenderer(this);
        this.progressBar = new ContainerProgressBar(this);
        this.manualMode = new ManualContainerMode(this);
        this.autoFillMode = new AutoFillContainerMode(this);
    }

    bindEvents() {
        logger.debug('CONTAINER MANAGER DEBUG: Binding events');

        // Add container button
        const addContainerBtn = document.getElementById('addContainerBtn');
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => this.manualMode.addContainerRow());
        }

        // Auto-fill toggle
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => this.handleModeToggle(e.target.checked));
        }

        // Fill % toggle
        const fillToggle = document.getElementById('useFillPctToggle');
        const fillGroup = document.getElementById('fillPctInputGroup');
        const fillInfo = document.getElementById('fillPctInfo');
        if (fillToggle && fillGroup) {
            fillToggle.addEventListener('change', () => {
                fillGroup.style.display = fillToggle.checked ? 'flex' : 'none';
                // Recompute with UI fill % if enabled
                if (this.main.requiresContainers) {
                    this.planFetcher.fetchContainerPlan({ fill_pct: this.getEffectiveFillPct() });
                }
            });
        }
        const fillInput = document.getElementById('fillPctInput');
        if (fillInput) {
            fillInput.addEventListener('input', () => {
                const v = parseFloat(fillInput.value||'100');
                if (isFinite(v) && v>0 && this.main.requiresContainers) {
                    this.planFetcher.fetchContainerPlan({ fill_pct: this.getEffectiveFillPct() });
                }
            });
        }
    }

    handleModeToggle(autoFillEnabled) {
        logger.debug('AUTO-FILL TOGGLE:', autoFillEnabled);

        this.toggleContainerSections(autoFillEnabled);

        if (autoFillEnabled && this.main.requiresContainers) {
            this.autoFillMode.activate();
        } else if (!autoFillEnabled) {
            this.manualMode.activate();
        }
    }

    toggleContainerSections(autoFillEnabled) {
        const autoFillResults = document.getElementById('autoFillResults');
        const manualSection = document.getElementById('manualContainerSection');

        if (autoFillResults) {
            autoFillResults.style.display = autoFillEnabled ? 'block' : 'none';
        }

        if (manualSection) {
            manualSection.style.display = autoFillEnabled ? 'none' : 'block';
        }

        // When switching to manual mode, populate manual rows from auto-fill results
        if (!autoFillEnabled && this.containerPlan?.success && this.containerPlan.container_selection) {
            this.manualMode.populateFromAutoFill();
        }

        this.progressBar.update();
    }

    onContainerRequirementChange() {
        if (this.main.requiresContainers) {
            const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked ?? true;
            this.toggleContainerSections(autoFillEnabled);
            this.planFetcher.fetchContainerPlan({ fill_pct: this.getEffectiveFillPct() });
        } else {
            this.containerPlan = null;
            this.renderer.clearResults();
        }
    }

    getEffectiveFillPct() {
        // If recipe provides fill pct via window.recipeData, use it; otherwise use UI toggle
        const recipePct = parseFloat(window.recipeData?.category_data?.vessel_fill_pct || '');
        if (isFinite(recipePct) && recipePct>0) {
            const info = document.getElementById('fillPctInfo');
            if (info) info.textContent = `(Recipe fill ${recipePct}%)`;
            // Hide UI toggle when recipe provides value
            const toggle = document.getElementById('useFillPctToggle');
            const group = document.getElementById('fillPctInputGroup');
            if (toggle) toggle.style.display = 'none';
            if (group) group.style.display = 'none';
            return recipePct;
        }
        const toggle = document.getElementById('useFillPctToggle');
        const input = document.getElementById('fillPctInput');
        const enabled = !!(toggle && toggle.checked);
        const val = parseFloat(input?.value || '100');
        const info = document.getElementById('fillPctInfo');
        if (info) info.textContent = enabled ? `(Fill ${val}%)` : '';
        return enabled && isFinite(val) && val>0 ? val : null;
    }

    displayContainerPlan() {
        this.renderer.displayPlan();
        this.progressBar.update();
    }

    displayContainerError(message) {
        this.renderer.displayError(message);
    }

    clearContainerResults() {
        this.containerPlan = null;
        this.renderer.clearResults();
    }

    fetchContainerPlan() {
        return this.planFetcher.fetchContainerPlan();
    }
}