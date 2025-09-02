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
        this.init(); // Initialize the module
    }

    init() {
        try {
            // Initialize DOM elements
            this.initializeDOMElements();

            // Show the container card immediately
            this.showContainerCard();

            // Set up event listeners
            this.setupEventListeners();

            // Load initial container data
            this.refreshContainerOptions();

            console.log('🔧 CONTAINER_MANAGEMENT: Module initialized successfully');

        } catch (error) {
            console.error('🔧 CONTAINER_MANAGEMENT: Initialization error:', error);
            // Still show the card even if there's an error
            this.showContainerCard();
            this.showError('Failed to initialize container management');
        }
    }

    showContainerCard() {
        const containerCard = document.getElementById('containerManagementCard');
        if (containerCard) {
            containerCard.style.display = 'block';
            console.log('🔧 CONTAINER_MANAGEMENT: Container card displayed');
        }
    }

    initializeDOMElements() {
        // Placeholder for any specific element initializations if needed
        // For example, if you need to pre-render templates or set initial states
    }

    setupEventListeners() {
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
            console.warn('🔧 CONTAINER_MANAGEMENT: No recipe data available');
            this.showContainerCard(); // Still show the card
            this.showMessage('No recipe data available for container analysis');
            return;
        }

        try {
            const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
            const scale = scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;

            console.log('🔧 CONTAINER_MANAGEMENT: Sending request:', {
                recipe_id: window.recipeData.id,
                scale: scale
            });

            const response = await fetch(`/production-planning/${window.recipeData.id}/auto-fill-containers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value || ''
                },
                body: JSON.stringify({
                    recipe_id: window.recipeData.id,
                    scale: scale
                })
            });

            console.log('🔧 CONTAINER_MANAGEMENT: Response status:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error(`Expected JSON response, got ${contentType}. Response may be a redirect or HTML page.`);
            }

            const result = await response.json();

            if (result.success) {
                this.autoFillStrategy = result.strategy;
                this.allContainerOptions = result.options || [];
                this.displayContainerResults();
            } else {
                this.showError(result.error || 'Failed to analyze containers');
            }

        } catch (error) {
            console.error('🔧 CONTAINER_MANAGEMENT: Network/parsing error:', error);

            // More specific error handling
            let errorMessage = 'Failed to load container options';
            if (error.message.includes('Permission denied')) {
                errorMessage = 'You do not have permission to access container options';
            } else if (error.message.includes('redirect')) {
                errorMessage = 'Authentication required - please refresh the page';
            } else if (error.message.includes('JSON')) {
                errorMessage = 'Server returned invalid response - please try again';
            } else if (error.message.startsWith('HTTP')) {
                errorMessage = error.message.replace('HTTP ', 'Error ');
            }

            this.showError(errorMessage);
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

    calculateMetrics() {
        // General metrics calculation for both auto and manual modes
        if (this.mode === 'auto' && this.autoFillStrategy) {
            this.currentMetrics = this.autoFillStrategy.metrics;
        } else if (this.mode === 'manual') {
            this.calculateManualMetrics();
        }
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
            const response = await fetch(`/production-planning/${recipeData.id}/calculate-container-metrics`, {
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
            if (result.success) {
                this.currentMetrics = result.metrics;
            }

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

    getScaleFactor() {
        return this.getCurrentScale();
    }

    showMessage(message, type = 'info') {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            const alertClass = type === 'error' ? 'alert-danger' : 
                             type === 'warning' ? 'alert-warning' : 'alert-info';
            const icon = type === 'error' ? 'fas fa-exclamation-circle' : 
                        type === 'warning' ? 'fas fa-exclamation-triangle' : 'fas fa-info-circle';

            containerResults.innerHTML = `
                <div class="alert ${alertClass}">
                    <i class="${icon}"></i> ${message}
                </div>
            `;
        }
    }

    showError(message) {
        this.showMessage(message, 'error');
    }

    displayContainerResults() {
        // This method is called when fetchContainerOptions is successful
        // and should render the results or update the UI accordingly.
        // For now, it just calls renderContainerOptions and updateContainerProgress.
        this.renderContainerOptions();
        this.updateContainerProgress();

        // Ensure the card is visible after data is loaded
        this.showContainerCard();
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