/**
 * Container Management Module - Coordination Only
 * 
 * Pure coordination between display modules and data fetching.
 * No business logic calculations - just orchestration.
 */

import { ContainerPlanFetcher } from './container-plan-fetcher.js';
import { ContainerRenderer } from './container-renderer.js';
import { ContainerProgressBar } from './container-progress-bar.js';

export class ContainerManager {
    constructor(containerId = 'containerManagementCard') {
        this.container = document.getElementById(containerId);
        this.mode = 'auto'; // 'auto' or 'manual'

        // Initialize specialized modules
        this.fetcher = new ContainerPlanFetcher(this);
        this.renderer = new ContainerRenderer(this);
        this.progressBar = new ContainerProgressBar();

        // Data storage - populated by fetcher
        this.containerPlan = null;
        this.allContainerOptions = [];
        this.autoFillStrategy = null;

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

        // Refresh options button
        const refreshBtn = this.container.querySelector('#refreshContainerOptions');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshContainerOptions();
            });
        }

        // Add container button for manual mode
        const addContainerBtn = this.container.querySelector('#addContainerRow');
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => {
                this.addContainerRow();
            });
        }

        // Scale change listener
        const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.handleScaleChange();
            });
        }
    }

    async refreshContainerOptions() {
        console.log('🔍 CONTAINER MANAGEMENT: refreshContainerOptions called');

        try {
            this.showLoadingState();

            const planResult = await this.fetcher.fetchContainerPlan();
            console.log('🔍 CONTAINER MANAGEMENT: Raw plan result:', planResult);

            if (planResult) {
                // Ensure we have the expected structure
                const processedResult = {
                    container_options: planResult.container_options || planResult.options || [],
                    auto_fill_strategy: planResult.auto_fill_strategy || planResult.strategy,
                    success: planResult.success !== false,
                    error: planResult.error
                };

                console.log('🔍 CONTAINER MANAGEMENT: Processed result:', processedResult);

                if (processedResult.container_options.length > 0) {
                    this.renderer.displayContainerOptions(processedResult);
                    this.updateProgressBar(processedResult);
                } else {
                    console.warn('🔍 CONTAINER MANAGEMENT: No container options in result');
                    this.showNoOptionsState();
                }
            } else {
                console.warn('🔍 CONTAINER MANAGEMENT: No plan result received');
                this.showNoOptionsState();
            }
        } catch (error) {
            console.error('🚨 CONTAINER MANAGEMENT: Error refreshing options:', error);
            this.showErrorState(error.message);
        } finally {
            this.hideLoadingState();
        }
    }

    async handleScaleChange() {
        // Auto-refresh when scale changes
        await this.refreshContainerOptions();
    }

    handleAutoFillToggle(isEnabled) {
        const autoSection = this.container.querySelector('#autoContainerSection');
        const manualSection = this.container.querySelector('#manualContainerSection');

        if (autoSection && manualSection) {
            if (isEnabled) {
                autoSection.style.display = 'block';
                manualSection.style.display = 'none';
                this.mode = 'auto';
            } else {
                autoSection.style.display = 'none';
                manualSection.style.display = 'block';
                this.mode = 'manual';
                // Render manual options
                this.renderer.renderManualContainerOptions(manualSection, this.allContainerOptions);
            }

            // Update displays
            this.renderer.displayPlan();
        }
    }

    addContainerRow() {
        const template = document.getElementById('containerRowTemplate');
        const container = document.getElementById('containerSelectionRows');

        if (!template || !container) return;

        const newRow = template.cloneNode(true);
        newRow.style.display = 'block';
        newRow.id = '';

        // Populate select options with available containers
        const select = newRow.querySelector('.container-select');
        if (select && this.allContainerOptions) {
            this.allContainerOptions.forEach(option => {
                const optionEl = document.createElement('option');
                optionEl.value = option.container_id;
                optionEl.textContent = option.container_name;
                optionEl.dataset.capacity = option.capacity;
                optionEl.dataset.available = option.available_quantity;
                select.appendChild(optionEl);
            });
        }

        // Add event listeners for the new row
        this.attachRowEventListeners(newRow);

        container.appendChild(newRow);
    }

    attachRowEventListeners(row) {
        const removeBtn = row.querySelector('.remove-container-btn');
        const select = row.querySelector('.container-select');
        const quantity = row.querySelector('.container-quantity');

        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                row.remove();
                this.updateManualSummary();
            });
        }

        if (select) {
            select.addEventListener('change', () => {
                this.updateRowAvailability(row);
                this.updateManualSummary();
            });
        }

        if (quantity) {
            quantity.addEventListener('input', () => {
                this.updateManualSummary();
            });
        }
    }

    updateRowAvailability(row) {
        const select = row.querySelector('.container-select');
        const availableStock = row.querySelector('.available-stock');

        if (select && availableStock) {
            const selectedOption = select.options[select.selectedIndex];
            if (selectedOption && selectedOption.dataset.available) {
                availableStock.textContent = selectedOption.dataset.available;
                availableStock.className = 'badge bg-info fs-6 available-stock';
            } else {
                availableStock.textContent = '-';
                availableStock.className = 'badge bg-secondary fs-6 available-stock';
            }
        }
    }

    updateManualSummary() {
        // Delegate to renderer
        this.renderer.updateManualSelectionSummary();
    }

    updateProgressDisplay() {
        if (this.mode === 'auto' && this.autoFillStrategy) {
            const metrics = {
                containment_percentage: this.autoFillStrategy.containment_percentage || 0,
                total_capacity: this.autoFillStrategy.total_capacity || 0,
                total_containers: this.autoFillStrategy.container_selection?.length || 0,
                warnings: this.autoFillStrategy.warnings || []
            };
            this.progressBar.show();
            this.progressBar.updateProgress(metrics);
        } else {
            this.progressBar.hide();
        }
    }

    showError(message) {
        if (!this.container) return;
        
        let errorDiv = this.container.querySelector('#containerError');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'containerError';
            errorDiv.className = 'mt-3';
            const cardBody = this.container.querySelector('.card-body');
            if (cardBody) {
                cardBody.appendChild(errorDiv);
            }
        }

        errorDiv.innerHTML = `<div class="alert alert-danger">${message}</div>`;
        errorDiv.style.display = 'block';

        setTimeout(() => {
            if (errorDiv) errorDiv.style.display = 'none';
        }, 10000);
    }

    showLoadingState() {
        // Show loading state for container refresh
        const refreshBtn = this.container?.querySelector('#refreshContainerOptions');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
        }
    }

    hideLoadingState() {
        // Hide loading state
        const refreshBtn = this.container?.querySelector('#refreshContainerOptions');
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="fas fa-sync"></i> Refresh Options';
        }
    }

    showNoOptionsState() {
        if (this.renderer) {
            this.renderer.showNoData();
        }
    }

    showErrorState(message) {
        if (this.renderer) {
            this.renderer.displayError(message);
        }
    }

    getCurrentScale() {
        const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }

    getSelectedContainers() {
        if (this.mode === 'auto' && this.autoFillStrategy?.container_selection) {
            return this.autoFillStrategy.container_selection;
        } else {
            // Get manually selected containers
            const rows = document.querySelectorAll('#containerSelectionRows [data-container-row]');
            const selected = [];

            rows.forEach(row => {
                const select = row.querySelector('.container-select');
                const quantity = row.querySelector('.container-quantity');

                if (select && quantity && select.value) {
                    const qty = parseInt(quantity.value || 0);
                    if (qty > 0) {
                        selected.push({
                            container_id: parseInt(select.value),
                            container_name: select.options[select.selectedIndex].textContent,
                            quantity: qty
                        });
                    }
                }
            });

            return selected;
        }
    }
}