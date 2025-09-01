/**
 * Container Management Module - Display Logic Only
 * 
 * This module handles container selection UI and fetches data from backend.
 * All business logic resides in the backend service.
 */

export class ContainerManager {
    constructor(containerId = 'containerManagementCard') {
        this.container = document.getElementById(containerId);
        this.mode = 'auto'; // 'auto' or 'manual'
        this.selectedContainers = [];
        this.allContainerOptions = [];
        this.autoFillStrategy = null;
        this.currentMetrics = null;

        this.initializeEventListeners();
    }

    initializeEventListeners() {
        if (!this.container) return;

        // Mode toggle
        const modeToggle = this.container.querySelector('#containerModeToggle');
        if (modeToggle) {
            modeToggle.addEventListener('change', (e) => {
                this.switchMode(e.target.value);
            });
        }

        // Refresh containers button
        const refreshBtn = this.container.querySelector('#refreshContainersBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshContainerOptions();
            });
        }
    }

    async refreshContainerOptions() {
        if (!window.recipeData?.id) {
            console.error('Recipe ID not available');
            return;
        }

        try {
            const requestData = {
                recipe_id: window.recipeData.id,
                scale: this.getCurrentScale()
            };

            console.log('🔧 CONTAINER_MANAGEMENT: Sending request:', requestData);

            const response = await fetch(`/production-planning/${window.recipeData.id}/auto-fill-containers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify(requestData)
            });

            console.log('🔧 CONTAINER_MANAGEMENT: Response status:', response.status);

            const result = await response.json();
            console.log('🔧 CONTAINER_MANAGEMENT: Response data:', result);

            if (result.success) {
                console.log('🔧 CONTAINER_MANAGEMENT: Success! Processing results...');

                this.allContainerOptions = result.all_container_options || [];
                this.autoFillStrategy = result;  // The entire result is the strategy

                console.log('🔧 CONTAINER_MANAGEMENT: Container options count:', this.allContainerOptions.length);
                console.log('🔧 CONTAINER_MANAGEMENT: Strategy:', this.autoFillStrategy);

                this.renderContainerOptions();
                this.updateContainerProgress();
            } else {
                console.error('🔧 CONTAINER_MANAGEMENT: Request failed:', result.error);
                console.log('🔧 CONTAINER_MANAGEMENT: Debug info:', result.debug_info);
                this.showError(result.error || 'Failed to load container options');
            }

        } catch (error) {
            console.error('🔧 CONTAINER_MANAGEMENT: Network/parsing error:', error);
            this.showError('Failed to refresh container options: ' + error.message);
        }
    }

    switchMode(newMode) {
        this.mode = newMode;
        this.renderContainerOptions();
        this.updateContainerProgress();

        // Show/hide relevant sections
        const autoSection = this.container.querySelector('#autoContainerSection');
        const manualSection = this.container.querySelector('#manualContainerSection');

        if (autoSection && manualSection) {
            if (newMode === 'auto') {
                autoSection.style.display = 'block';
                manualSection.style.display = 'none';
            } else {
                autoSection.style.display = 'none';
                manualSection.style.display = 'block';
            }
        }
    }

    renderContainerOptions() {
        if (this.mode === 'auto') {
            this.renderAutoFillStrategy();
        } else {
            this.renderManualSelection();
        }
    }

    renderAutoFillStrategy() {
        const autoSection = this.container.querySelector('#autoContainerSection');
        if (!autoSection || !this.autoFillStrategy) return;

        const containersHtml = this.autoFillStrategy.container_selection.map((container, index) => `
            <div class="container-item mb-2 p-2 border rounded">
                <div class="d-flex justify-content-between align-items-center">
                    <span><strong>${container.container_name}</strong></span>
                    <span class="text-muted">${container.capacity} units</span>
                </div>
                <div class="progress mt-1" style="height: 8px;">
                    <div class="progress-bar" role="progressbar" 
                         style="width: ${(container.containers_needed * container.capacity / this.autoFillStrategy.total_capacity * 100).toFixed(1)}%"
                         aria-valuenow="${(container.containers_needed * container.capacity / this.autoFillStrategy.total_capacity * 100).toFixed(1)}" 
                         aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                <small class="text-muted">${container.containers_needed} containers needed</small>
            </div>
        `).join('');

        autoSection.innerHTML = `
            <h6>Recommended Container Selection:</h6>
            ${containersHtml}
        `;

        this.currentMetrics = this.autoFillStrategy.metrics;
    }

    renderManualSelection() {
        const manualSection = this.container.querySelector('#manualContainerSection');
        if (!manualSection || !this.allContainerOptions) return;

        const optionsHtml = this.allContainerOptions.map(option => `
            <div class="container-option mb-2 p-2 border rounded" data-container-id="${option.container_id}">
                <div class="d-flex justify-content-between align-items-center">
                    <label class="form-check-label">
                        <input type="checkbox" class="form-check-input me-2" 
                               value="${option.container_id}"
                               onchange="containerManager.updateManualSelection()">
                        <strong>${option.container_name}</strong>
                    </label>
                    <span class="text-muted">${option.capacity} units</span>
                </div>
                <div class="mt-1">
                    <small class="text-muted">
                        Needs ${option.containers_needed} container(s) | 
                        ${option.fill_percentage ? option.fill_percentage.toFixed(1) : 100}% efficiency
                    </small>
                </div>
            </div>
        `).join('');

        manualSection.innerHTML = `
            <h6>Select Containers Manually:</h6>
            ${optionsHtml}
            <div id="manualSelectionSummary" class="mt-3"></div>
        `;
    }

    updateManualSelection() {
        const checkboxes = this.container.querySelectorAll('#manualContainerSection input[type="checkbox"]:checked');
        this.selectedContainers = Array.from(checkboxes).map(cb => {
            const containerId = parseInt(cb.value);
            return this.allContainerOptions.find(option => option.container_id === containerId);
        }).filter(Boolean);

        // Calculate metrics for selected containers
        this.calculateManualMetrics();
        this.updateContainerProgress();
    }

    async calculateManualMetrics() {
        if (this.selectedContainers.length === 0) {
            this.currentMetrics = null;
            return;
        }

        try {
            const recipeData = window.recipeData;
            const scaleFactor = this.getScaleFactor();
            const totalYield = recipeData.yield_amount * scaleFactor;

            // Use backend service to calculate metrics
            const response = await fetch('/api/calculate-container-metrics', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    selected_containers: this.selectedContainers,
                    total_yield: totalYield
                })
            });

            const result = await response.json();
            this.currentMetrics = result.metrics;

        } catch (error) {
            console.error('Error calculating manual metrics:', error);
        }
    }

    updateContainerProgress() {
        // Update progress bar component with current metrics
        if (window.containerProgressBar && this.currentMetrics) {
            window.containerProgressBar.updateProgress(this.currentMetrics);
        }
    }

    getCurrentScale() {
        const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }

    showError(message) {
        const errorDiv = this.container.querySelector('#containerError');
        if (errorDiv) {
            errorDiv.innerHTML = `<div class="alert alert-danger">${message}</div>`;
            errorDiv.style.display = 'block';
        }
    }

    getSelectedContainers() {
        if (this.mode === 'auto' && this.autoFillStrategy) {
            return this.autoFillStrategy.containers_to_use;
        } else {
            return this.selectedContainers;
        }
    }
}

// Initialize global container manager
let containerManager;
document.addEventListener('DOMContentLoaded', () => {
    containerManager = new ContainerManager();
    window.containerManager = containerManager;
});