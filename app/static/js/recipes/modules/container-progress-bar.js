
// Container Progress Bar - Handles containment percentage calculations and display
export class ContainerProgressBar {
    constructor() {
        this.progressElement = null;
        this.findProgressElement();
    }

    findProgressElement() {
        this.progressElement = document.querySelector('#containerProgress, .container-progress, [data-container-progress]');
        if (!this.progressElement) {
            console.warn('🔧 PROGRESS_BAR: Progress element not found');
        }
    }

    update() {
        if (!this.progressElement) {
            this.findProgressElement();
        }

        try {
            const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
            let containmentData;

            if (autoFillEnabled) {
                containmentData = this.getAutoFillContainment();
            } else {
                containmentData = this.calculateManualContainment();
            }

            this.updateProgressBar(containmentData);
            
        } catch (error) {
            console.error('🔧 PROGRESS_BAR: Error updating progress bar:', error);
            this.clear();
        }
    }

    getAutoFillContainment() {
        const containerManager = window.containerManager;
        if (!containerManager?.containerPlan?.success) {
            return { percentage: 0, message: 'Auto-fill not available' };
        }

        const plan = containerManager.containerPlan;
        return {
            percentage: plan.containment_percentage || 0,
            message: plan.containment_percentage >= 100 
                ? 'Fully contained' 
                : `${plan.containment_percentage?.toFixed(1)}% contained`
        };
    }

    calculateManualContainment() {
        try {
            const targetYield = this.getTargetYield();
            if (targetYield <= 0) {
                return { percentage: 0, message: 'No yield to contain' };
            }

            let totalCapacity = 0;
            let hasSelections = false;

            // Sum up all manual container selections
            document.querySelectorAll('[data-container-row]').forEach(row => {
                const select = row.querySelector('.container-select');
                const quantityInput = row.querySelector('.container-quantity');

                if (select?.value && quantityInput?.value) {
                    const containerId = parseInt(select.value);
                    const quantity = parseInt(quantityInput.value) || 0;

                    if (quantity > 0) {
                        const containerOption = this.findContainerOption(containerId);
                        if (containerOption) {
                            totalCapacity += containerOption.capacity * quantity;
                            hasSelections = true;
                        }
                    }
                }
            });

            if (!hasSelections) {
                return { percentage: 0, message: 'No containers selected' };
            }

            const percentage = Math.min(100, (totalCapacity / targetYield) * 100);
            const message = percentage >= 100 
                ? 'Fully contained' 
                : `${percentage.toFixed(1)}% contained`;

            return { percentage, message };

        } catch (error) {
            console.error('🔧 PROGRESS_BAR: Error calculating manual containment:', error);
            return { percentage: 0, message: 'Calculation error' };
        }
    }

    findContainerOption(containerId) {
        const containerManager = window.containerManager;
        if (!containerManager?.containerOptions) return null;

        return containerManager.containerOptions.find(opt => opt.container_id === containerId);
    }

    updateProgressBar(containmentData) {
        if (!this.progressElement) return;

        const { percentage, message } = containmentData;
        
        // Update progress bar
        const progressBar = this.progressElement.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = `${Math.min(100, percentage)}%`;
            progressBar.textContent = `${percentage.toFixed(1)}%`;
            
            // Update color based on percentage
            progressBar.className = `progress-bar ${this.getProgressBarClass(percentage)}`;
        }

        // Update message
        const messageElement = this.progressElement.querySelector('.progress-message, .containment-message');
        if (messageElement) {
            messageElement.textContent = message;
        }

        console.log(`🔧 PROGRESS_BAR: Updated to ${percentage.toFixed(1)}% - ${message}`);
    }

    getProgressBarClass(percentage) {
        if (percentage >= 100) return 'bg-success';
        if (percentage >= 90) return 'bg-warning';
        if (percentage >= 50) return 'bg-info';
        return 'bg-secondary';
    }

    getTargetYield() {
        try {
            const baseYield = window.recipeData?.yield_amount || 0;
            const scale = this.getScaleFactor();
            return baseYield * scale;
        } catch (error) {
            console.error('🔧 PROGRESS_BAR: Error getting target yield:', error);
            return 0;
        }
    }

    getScaleFactor() {
        const scaleInput = document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }

    clear() {
        if (!this.progressElement) return;

        const progressBar = this.progressElement.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            progressBar.className = 'progress-bar bg-secondary';
        }

        const messageElement = this.progressElement.querySelector('.progress-message, .containment-message');
        if (messageElement) {
            messageElement.textContent = 'No containers configured';
        }
    }

    // Method to be called when container plan is updated
    onContainerPlanUpdated(containerPlan) {
        if (document.getElementById('autoFillEnabled')?.checked) {
            // Auto-fill mode - trigger update
            this.update();
        }
    }

    // Method to be called when manual selections change
    onManualSelectionsChanged() {
        if (!document.getElementById('autoFillEnabled')?.checked) {
            // Manual mode - trigger update
            this.update();
        }
    }
}
