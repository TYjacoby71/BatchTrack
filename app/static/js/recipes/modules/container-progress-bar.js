
// Container Progress Bar - Display backend metrics ONLY
export class ContainerProgressBar {
    constructor(containerManager) {
        this.container = containerManager;
    }

    updateProgressDisplay() {
        const containerPlan = this.container.containerPlan;
        
        if (!containerPlan) {
            this.clearProgress();
            return;
        }

        // Use backend-calculated metrics directly
        this.displayContainmentMetrics(containerPlan);
        this.displayLastContainerFill(containerPlan);
    }

    displayContainmentMetrics(plan) {
        const containmentElement = document.querySelector('.containment-progress');
        
        if (!containmentElement) return;

        // Use backend containment percentage directly
        const containmentPercentage = plan.containment_percentage || 0;
        const progressClass = containmentPercentage >= 100 ? 'bg-success' : 'bg-warning';
        
        containmentElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span><strong>Containment:</strong></span>
                <span class="badge ${progressClass}">${containmentPercentage.toFixed(1)}%</span>
            </div>
            <div class="progress">
                <div class="progress-bar ${progressClass}" 
                     style="width: ${Math.min(containmentPercentage, 100)}%">
                </div>
            </div>
        `;
    }

    displayLastContainerFill(plan) {
        const fillElement = document.querySelector('.last-container-fill');
        
        if (!fillElement) return;

        // Use backend last container fill metrics directly
        const fillMetrics = plan.last_container_fill_metrics;
        
        if (!fillMetrics) {
            fillElement.innerHTML = '<p class="text-muted">No partial fill data</p>';
            return;
        }

        const fillPercentage = fillMetrics.fill_percentage || 0;
        const progressClass = fillMetrics.is_low_efficiency ? 'bg-warning' : 'bg-info';
        
        fillElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span><strong>Last ${fillMetrics.container_name}:</strong></span>
                <span class="badge ${progressClass}">${fillPercentage.toFixed(1)}% filled</span>
            </div>
            <div class="progress">
                <div class="progress-bar ${progressClass}" 
                     style="width: ${fillPercentage}%">
                </div>
            </div>
            ${fillMetrics.is_low_efficiency ? 
                '<small class="text-warning">⚠️ Low efficiency - consider different container size</small>' : 
                ''
            }
        `;
    }

    clearProgress() {
        const containmentElement = document.querySelector('.containment-progress');
        const fillElement = document.querySelector('.last-container-fill');
        
        if (containmentElement) {
            containmentElement.innerHTML = '<p class="text-muted">No containment data</p>';
        }
        
        if (fillElement) {
            fillElement.innerHTML = '<p class="text-muted">No fill data</p>';
        }
    }
}
