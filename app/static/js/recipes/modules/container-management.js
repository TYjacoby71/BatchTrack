
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
        console.log('🔍 AUTO-FILL MODE: Activating auto-fill container selection');
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
        console.log('🔍 CONTAINER MANAGER DEBUG: Binding events');

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
        console.log('🔍 AUTO-FILL TOGGLE:', autoFillEnabled);
        
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

    selectRecommendedContainers() {
        console.log('🔍 CONTAINER MANAGEMENT: Selecting all recommended containers');
        
        // Check all container checkboxes
        const checkboxes = document.querySelectorAll('.container-select-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        
        // Update the renderer's selection
        this.renderer.updateContainerSelection();
        
        // Show success message
        const resultsDiv = document.getElementById('autoFillResults');
        if (resultsDiv) {
            const successAlert = document.createElement('div');
            successAlert.className = 'alert alert-success alert-dismissible fade show mt-2';
            successAlert.innerHTML = `
                <i class="fas fa-check"></i> All recommended containers selected!
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            resultsDiv.appendChild(successAlert);
            
            // Auto-dismiss after 3 seconds
            setTimeout(() => {
                if (successAlert.parentNode) {
                    successAlert.remove();
                }
            }, 3000);
        }
    }

    onContainerRequirementChange() {
        if (this.main.requiresContainers) {
            const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked ?? true;
            this.toggleContainerSections(autoFillEnabled);
            this.fetchContainerPlan();
        } else {
            this.containerPlan = null;
            this.renderer.clearResults();
        }
    }

    async fetchContainerPlan() {
        console.log('🔍 CONTAINER MANAGEMENT: fetchContainerPlan called');
        return await this.planFetcher.fetchContainerPlan();
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


