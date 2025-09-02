
// Container Renderer - Handles all container display logic
export class ContainerRenderer {
    constructor(containerManager) {
        this.containerManager = containerManager;
        this.listeners = new Map(); // Track event listeners for cleanup
        this.scaleMultiplier = 1.0; // Track current scale multiplier
        this.isAutoResetEnabled = true; // Auto-reset when scale changes
        
        this.initializeListeners();
    }

    initializeListeners() {
        // Scale factor change listener
        const scaleInput = document.getElementById('scaleFactorInput');
        if (scaleInput) {
            const scaleListener = (event) => {
                const newScale = parseFloat(event.target.value) || 1.0;
                this.handleScaleChange(newScale);
            };
            
            scaleInput.addEventListener('input', scaleListener);
            this.listeners.set('scaleInput', { element: scaleInput, event: 'input', handler: scaleListener });
        }

        // Auto-fill toggle listener
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle) {
            const autoFillListener = (event) => {
                this.handleAutoFillToggle(event.target.checked);
            };
            
            autoFillToggle.addEventListener('change', autoFillListener);
            this.listeners.set('autoFillToggle', { element: autoFillToggle, event: 'change', handler: autoFillListener });
        }

        // Container row change listeners (delegated)
        const containerRows = document.getElementById('containerRows');
        if (containerRows) {
            const containerChangeListener = (event) => {
                if (event.target.matches('.container-select, .container-quantity')) {
                    this.handleContainerRowChange(event);
                }
            };
            
            containerRows.addEventListener('change', containerChangeListener);
            this.listeners.set('containerRows', { element: containerRows, event: 'change', handler: containerChangeListener });
        }

        console.log('🔧 CONTAINER_RENDERER: Event listeners initialized');
    }

    handleScaleChange(newScale) {
        console.log(`🔧 CONTAINER_RENDERER: Scale changed from ${this.scaleMultiplier} to ${newScale}`);
        
        const previousScale = this.scaleMultiplier;
        this.scaleMultiplier = newScale;

        // Auto-reset containers when scale changes (if enabled)
        if (this.isAutoResetEnabled && previousScale !== newScale) {
            this.autoResetContainers();
        }

        // Update progress bar
        if (window.containerProgressBar) {
            window.containerProgressBar.update();
        }

        // Trigger container plan refresh
        if (this.containerManager) {
            this.containerManager.refreshContainerPlan();
        }
    }

    handleAutoFillToggle(isEnabled) {
        console.log(`🔧 CONTAINER_RENDERER: Auto-fill toggled: ${isEnabled}`);
        
        if (isEnabled) {
            // Switch to auto-fill mode
            this.renderAutoFillMode();
        } else {
            // Switch to manual mode
            this.renderManualMode();
        }

        // Update progress bar
        if (window.containerProgressBar) {
            window.containerProgressBar.update();
        }
    }

    handleContainerRowChange(event) {
        console.log('🔧 CONTAINER_RENDERER: Container row changed', event.target);
        
        // Update progress bar when manual selections change
        if (window.containerProgressBar) {
            window.containerProgressBar.update();
        }
    }

    autoResetContainers() {
        console.log('🔧 CONTAINER_RENDERER: Auto-resetting containers due to scale change');
        
        // Clear manual selections
        document.querySelectorAll('[data-container-row]').forEach(row => {
            const select = row.querySelector('.container-select');
            const quantityInput = row.querySelector('.container-quantity');
            
            if (select) select.value = '';
            if (quantityInput) quantityInput.value = '';
        });

        // If auto-fill is enabled, refresh the auto-fill
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        if (autoFillEnabled && this.containerManager) {
            this.containerManager.refreshContainerPlan();
        }
    }

    renderAutoFillMode() {
        console.log('🔧 CONTAINER_RENDERER: Rendering auto-fill mode');
        
        const containerPlan = this.containerManager?.containerPlan;
        if (!containerPlan?.success) {
            this.renderEmptyState('Auto-fill not available');
            return;
        }

        const containerRows = document.getElementById('containerRows');
        if (!containerRows) {
            console.error('Container rows element not found');
            return;
        }

        const autoFillSelections = containerPlan.container_selection || [];
        let html = '';

        autoFillSelections.forEach((selection, index) => {
            const fillPercentage = this.calculateFillPercentage(selection, index, autoFillSelections);
            
            html += `
                <div class="row mb-2 align-items-center" data-container-row data-auto-fill="true">
                    <div class="col-md-5">
                        <select class="form-select container-select" disabled>
                            <option value="${selection.container_id}" selected>
                                ${this.escapeHtml(selection.container_name)} (${selection.capacity} ${this.getYieldUnit()})
                            </option>
                        </select>
                    </div>
                    <div class="col-md-2">
                        <input type="number" 
                               class="form-control container-quantity" 
                               value="${selection.containers_needed}"
                               min="1"
                               disabled>
                    </div>
                    <div class="col-md-5">
                        <div class="d-flex align-items-center">
                            <div class="progress flex-grow-1 me-2" style="height: 20px;">
                                <div class="progress-bar ${this.getProgressBarClass(fillPercentage)}" 
                                     style="width: ${Math.min(100, fillPercentage)}%">
                                    ${fillPercentage.toFixed(1)}%
                                </div>
                            </div>
                            <small class="text-muted">${(selection.capacity * selection.containers_needed).toFixed(2)} ${this.getYieldUnit()}</small>
                        </div>
                    </div>
                </div>
            `;
        });

        containerRows.innerHTML = html;
        console.log(`🔧 CONTAINER_RENDERER: Rendered ${autoFillSelections.length} auto-fill rows`);
    }

    renderManualMode() {
        console.log('🔧 CONTAINER_RENDERER: Rendering manual mode');
        
        const containerRows = document.getElementById('containerRows');
        if (!containerRows) {
            console.error('Container rows element not found');
            return;
        }

        // Get available container options
        const containerOptions = this.containerManager?.containerOptions || [];
        if (containerOptions.length === 0) {
            this.renderEmptyState('No containers available');
            return;
        }

        // Create manual selection rows
        let html = '';
        for (let i = 0; i < 3; i++) { // Default 3 rows for manual mode
            html += this.createManualRow(containerOptions, i);
        }

        containerRows.innerHTML = html;
        console.log('🔧 CONTAINER_RENDERER: Rendered manual mode with 3 rows');
    }

    createManualRow(containerOptions, index) {
        const optionsHtml = containerOptions.map(option => 
            `<option value="${option.container_id}">${this.escapeHtml(option.container_name)} (${option.capacity} ${this.getYieldUnit()})</option>`
        ).join('');

        return `
            <div class="row mb-2 align-items-center" data-container-row data-manual="true">
                <div class="col-md-5">
                    <select class="form-select container-select">
                        <option value="">Select container...</option>
                        ${optionsHtml}
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="number" 
                           class="form-control container-quantity" 
                           placeholder="Qty"
                           min="1">
                </div>
                <div class="col-md-4">
                    <div class="container-capacity-display text-muted">
                        <small>Select container to see capacity</small>
                    </div>
                </div>
                <div class="col-md-1">
                    ${index > 0 ? `<button type="button" class="btn btn-sm btn-outline-danger remove-row" title="Remove row">×</button>` : ''}
                </div>
            </div>
        `;
    }

    calculateFillPercentage(selection, index, allSelections) {
        try {
            const targetYield = this.getTargetYield();
            const totalUsedYield = allSelections.slice(0, index).reduce((sum, s) => 
                sum + (s.capacity * s.containers_needed), 0
            );
            const remainingYield = targetYield - totalUsedYield;
            const thisContainerCapacity = selection.capacity * selection.containers_needed;
            
            if (remainingYield <= 0) return 0;
            
            const fillAmount = Math.min(remainingYield, thisContainerCapacity);
            return (fillAmount / thisContainerCapacity) * 100;
            
        } catch (error) {
            console.error('Error calculating fill percentage:', error);
            return 0;
        }
    }

    getProgressBarClass(percentage) {
        if (percentage >= 90) return 'bg-success';
        if (percentage >= 70) return 'bg-warning';
        return 'bg-info';
    }

    renderEmptyState(message) {
        const containerRows = document.getElementById('containerRows');
        if (containerRows) {
            containerRows.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-box-open fa-2x mb-2"></i>
                    <p>${this.escapeHtml(message)}</p>
                </div>
            `;
        }
    }

    // Utility methods
    getTargetYield() {
        try {
            const baseYield = window.recipeData?.yield_amount || 0;
            return baseYield * this.scaleMultiplier;
        } catch (error) {
            console.error('Error getting target yield:', error);
            return 0;
        }
    }

    getYieldUnit() {
        return window.recipeData?.yield_unit || 'units';
    }

    escapeHtml(text) {
        if (typeof text !== 'string') return String(text || '');
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Stock check integration
    updateContainerStockStatus(stockResults) {
        if (!stockResults?.containers) return;

        document.querySelectorAll('[data-container-row]').forEach(row => {
            const select = row.querySelector('.container-select');
            if (!select?.value) return;

            const containerId = parseInt(select.value);
            const containerStock = stockResults.containers.find(c => c.id === containerId);
            
            if (containerStock) {
                this.updateRowStockIndicator(row, containerStock);
            }
        });
    }

    updateRowStockIndicator(row, stockInfo) {
        // Remove existing stock indicators
        const existingIndicator = row.querySelector('.stock-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        // Add new stock indicator
        const quantityCol = row.querySelector('.col-md-2');
        if (quantityCol) {
            const indicator = document.createElement('div');
            indicator.className = 'stock-indicator mt-1';
            
            if (stockInfo.available >= stockInfo.needed) {
                indicator.innerHTML = `<small class="text-success">✓ ${stockInfo.available} available</small>`;
            } else {
                indicator.innerHTML = `<small class="text-danger">⚠ Only ${stockInfo.available} available</small>`;
            }
            
            quantityCol.appendChild(indicator);
        }
    }

    // Cleanup method
    destroy() {
        console.log('🔧 CONTAINER_RENDERER: Cleaning up listeners');
        
        this.listeners.forEach((listenerInfo, key) => {
            const { element, event, handler } = listenerInfo;
            if (element && handler) {
                element.removeEventListener(event, handler);
            }
        });
        
        this.listeners.clear();
    }
}
