
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
        try {
            console.log('🔧 CONTAINER_MANAGEMENT: Refreshing container options...');
            
            const result = await this.fetcher.fetchContainerPlan();
            
            if (result && result.success) {
                // Store the data
                this.containerPlan = result;
                this.allContainerOptions = result.all_container_options || [];
                this.autoFillStrategy = result.auto_fill_strategy;
                
                console.log('🔧 CONTAINER_MANAGEMENT: Data stored:', {
                    plan: !!this.containerPlan,
                    options: this.allContainerOptions.length,
                    strategy: !!this.autoFillStrategy
                });
                
                // Update displays
                this.renderer.displayPlan();
                this.updateProgressDisplay();
            } else {
                console.error('🔧 CONTAINER_MANAGEMENT: No valid response received');
                this.renderer.displayError('Failed to load container options');
            }
        } catch (error) {
            console.error('🔧 CONTAINER_MANAGEMENT: Error refreshing options:', error);
            this.showError('Failed to refresh container options');
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
            this.progressBar.updateProgress(metrics);
        }
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
