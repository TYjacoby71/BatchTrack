
/**
 * Container Management Module - Coordinator Only
 * 
 * This module coordinates between specialized container modules.
 */

import { ContainerPlanFetcher } from './container-plan-fetcher.js';
import { ContainerRenderer } from './container-renderer.js';
import { ContainerProgressBar } from './container-progress-bar.js';

export class ContainerManager {
    constructor(containerId = 'containerManagementCard') {
        this.container = document.getElementById(containerId);
        this.mode = 'auto'; // 'auto' or 'manual'
        this.selectedContainers = [];
        
        // Initialize specialized modules
        this.fetcher = new ContainerPlanFetcher(this);
        this.renderer = new ContainerRenderer(this);
        this.progressBar = new ContainerProgressBar();
        
        // Current data
        this.allContainerOptions = [];
        this.autoFillStrategy = null;
        this.currentMetrics = null;

        this.initializeEventListeners();
    }

    initializeEventListeners() {
        if (!this.container) return;

        // Auto-fill toggle
        const autoFillToggle = this.container.querySelector('#autoFillEnabled');
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => {
                this.handleAutoFillToggle(e.target.checked);
            });
        }

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
        try {
            const result = await this.fetcher.fetchContainerPlan();
            
            if (result) {
                this.allContainerOptions = result.options || [];
                this.autoFillStrategy = result.strategy;
                this.renderContainerOptions();
                this.updateContainerProgress();
            }
        } catch (error) {
            console.error('🔧 CONTAINER_MANAGEMENT: Error refreshing options:', error);
            this.showError('Failed to refresh container options');
        }
    }

    handleAutoFillToggle(isEnabled) {
        const autoFillResults = this.container.querySelector('#autoFillResults');
        const manualContainerSection = this.container.querySelector('#manualContainerSection');

        if (autoFillResults && manualContainerSection) {
            if (isEnabled) {
                autoFillResults.style.display = 'block';
                manualContainerSection.style.display = 'none';
                this.mode = 'auto';
                this.refreshContainerOptions();
            } else {
                autoFillResults.style.display = 'none';
                manualContainerSection.style.display = 'block';
                this.mode = 'manual';
                this.renderContainerOptions();
            }
        }
    }

    switchMode(newMode) {
        this.mode = newMode;
        this.renderContainerOptions();
        this.updateContainerProgress();
    }

    renderContainerOptions() {
        if (this.mode === 'auto') {
            this.renderer.renderAutoFillStrategy(this.autoFillStrategy);
        } else {
            this.renderer.renderManualSelection(this.allContainerOptions, (selected) => {
                this.selectedContainers = selected;
                this.updateContainerProgress();
            });
        }
    }

    updateContainerProgress() {
        if (this.mode === 'auto' && this.autoFillStrategy) {
            this.currentMetrics = this.autoFillStrategy.metrics;
        } else if (this.mode === 'manual') {
            this.calculateManualMetrics();
        }

        if (this.currentMetrics) {
            this.progressBar.updateProgress(this.currentMetrics);
        }
    }

    async calculateManualMetrics() {
        if (this.selectedContainers.length === 0) {
            this.currentMetrics = null;
            return;
        }

        try {
            const recipeData = window.recipeData;
            const scaleFactor = this.getCurrentScale();
            const totalYield = recipeData.yield_amount * scaleFactor;

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

    getCurrentScale() {
        const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }

    showError(message) {
        let errorDiv = this.container.querySelector('#containerError');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'containerError';
            errorDiv.className = 'mt-3';
            this.container.querySelector('.card-body').appendChild(errorDiv);
        }
        
        errorDiv.innerHTML = `<div class="alert alert-danger">${message}</div>`;
        errorDiv.style.display = 'block';
        
        setTimeout(() => {
            if (errorDiv) errorDiv.style.display = 'none';
        }, 10000);
    }

    getSelectedContainers() {
        if (this.mode === 'auto' && this.autoFillStrategy) {
            return this.autoFillStrategy.containers_to_use;
        } else {
            return this.selectedContainers;
        }
    }
}
