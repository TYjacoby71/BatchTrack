// Import required modules
import { ContainerPlanFetcher } from './container-plan-fetcher.js';
import { ContainerRenderer } from './container-renderer.js';
import { ContainerProgressBar } from './container-progress-bar.js';
import { ManualContainerMode } from './manual-container-mode.js';

// Auto-Fill Container Mode Module
class AutoFillContainerMode {
    constructor(containerManager) {
        this.container = containerManager;
    }

    activate() {
        console.log('AUTO-FILL MODE: Activating auto-fill container selection');
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
        console.log('CONTAINER MANAGER DEBUG: Binding events');

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
    }

    handleModeToggle(autoFillEnabled) {
        console.log('AUTO-FILL TOGGLE:', autoFillEnabled);

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
            this.planFetcher.fetchContainerPlan();
        } else {
            this.containerPlan = null;
            this.renderer.clearResults();
        }
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