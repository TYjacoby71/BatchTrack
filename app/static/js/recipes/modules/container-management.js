
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
        
        // Current data - restored properties
        this.allContainerOptions = [];
        this.autoFillStrategy = null;
        this.currentMetrics = null;
        this.containerPlan = null; // Restored for compatibility

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

        // Add container button
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
                // Store the full response for compatibility
                this.containerPlan = result;
                this.allContainerOptions = result.all_container_options || [];
                this.autoFillStrategy = result.auto_fill_strategy;
                
                console.log('🔧 CONTAINER_MANAGEMENT: Data received:', {
                    strategy: !!this.autoFillStrategy,
                    options: this.allContainerOptions.length,
                    plan: !!this.containerPlan
                });
                
                // Update displays
                this.renderer.displayPlan();
                this.updateContainerProgress();
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
        
        // Populate select options
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
        const rows = document.querySelectorAll('#containerSelectionRows [data-container-row]');
        const summary = document.getElementById('manualSelectionSummary');
        
        if (!summary) return;
        
        let totalCapacity = 0;
        let validSelections = 0;
        
        rows.forEach(row => {
            const select = row.querySelector('.container-select');
            const quantity = row.querySelector('.container-quantity');
            
            if (select && quantity && select.value) {
                const selectedOption = select.options[select.selectedIndex];
                const capacity = parseFloat(selectedOption.dataset.capacity || 0);
                const qty = parseInt(quantity.value || 0);
                
                if (capacity > 0 && qty > 0) {
                    totalCapacity += capacity * qty;
                    validSelections++;
                }
            }
        });
        
        if (validSelections === 0) {
            summary.innerHTML = '<p class="text-muted">No containers selected</p>';
            return;
        }
        
        const recipeData = window.recipeData;
        const scale = this.getCurrentScale();
        const targetYield = (recipeData?.yield_amount || 0) * scale;
        const fillPercentage = targetYield > 0 ? (targetYield / totalCapacity) * 100 : 0;
        
        const fillClass = fillPercentage > 100 ? 'text-danger' : fillPercentage > 90 ? 'text-warning' : 'text-success';
        
        summary.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6>Manual Selection Summary:</h6>
                    <div class="d-flex justify-content-between">
                        <strong>Containers Selected:</strong>
                        <span>${validSelections}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <strong>Total Capacity:</strong>
                        <span>${totalCapacity} ${recipeData?.yield_unit || 'units'}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <strong>Target Yield:</strong>
                        <span>${targetYield} ${recipeData?.yield_unit || 'units'}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <strong>Fill Percentage:</strong>
                        <span class="${fillClass}">${fillPercentage.toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    updateContainerProgress() {
        if (this.mode === 'auto' && this.autoFillStrategy) {
            const metrics = {
                containment_percentage: this.autoFillStrategy.containment_percentage || 0,
                total_capacity: this.autoFillStrategy.total_capacity || 0,
                total_containers: this.autoFillStrategy.container_selection?.length || 0,
                last_container_fill_percentage: 100 // Default for single container
            };
            this.progressBar.updateProgress(metrics);
        } else if (this.mode === 'manual') {
            // Calculate manual metrics
            this.calculateManualMetrics();
        }
    }

    async calculateManualMetrics() {
        const rows = document.querySelectorAll('#containerSelectionRows [data-container-row]');
        let totalCapacity = 0;
        let containerCount = 0;
        
        rows.forEach(row => {
            const select = row.querySelector('.container-select');
            const quantity = row.querySelector('.container-quantity');
            
            if (select && quantity && select.value) {
                const selectedOption = select.options[select.selectedIndex];
                const capacity = parseFloat(selectedOption.dataset.capacity || 0);
                const qty = parseInt(quantity.value || 0);
                
                if (capacity > 0 && qty > 0) {
                    totalCapacity += capacity * qty;
                    containerCount += qty;
                }
            }
        });
        
        if (containerCount > 0) {
            const recipeData = window.recipeData;
            const scale = this.getCurrentScale();
            const targetYield = (recipeData?.yield_amount || 0) * scale;
            const containmentPercentage = targetYield > 0 ? Math.min(100, (totalCapacity / targetYield) * 100) : 0;
            
            const metrics = {
                containment_percentage: containmentPercentage,
                total_capacity: totalCapacity,
                total_containers: containerCount,
                last_container_fill_percentage: 100 // Simplified for manual mode
            };
            
            this.progressBar.updateProgress(metrics);
        } else {
            this.progressBar.clear();
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
