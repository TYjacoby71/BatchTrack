
/**
 * Container Progress Bar Module - Display Logic Only
 * 
 * Displays containment and efficiency metrics from backend data.
 * No business logic calculations performed here.
 */

export class ContainerProgressBar {
    constructor(containerId = 'containerProgressBar') {
        this.container = document.getElementById(containerId);
        this.progressBar = null;
        this.messageArea = null;
        
        this.initializeElements();
    }
    
    initializeElements() {
        if (!this.container) return;
        
        this.progressBar = this.container.querySelector('.progress-bar');
        this.messageArea = this.container.querySelector('#containerMessages');
        
        if (!this.progressBar || !this.messageArea) {
            console.warn('Progress bar elements not found');
        }
    }
    
    updateProgress(metrics) {
        if (!metrics || !this.progressBar || !this.messageArea) return;
        
        const {
            containment_percentage,
            last_container_fill_percentage,
            total_containers,
            total_capacity
        } = metrics;
        
        // Update progress bar (containment percentage)
        const displayPercentage = Math.min(100, containment_percentage);
        this.progressBar.style.width = `${displayPercentage}%`;
        this.progressBar.setAttribute('aria-valuenow', displayPercentage);
        
        // Update progress bar color based on containment
        this.progressBar.className = 'progress-bar';
        if (containment_percentage >= 100) {
            this.progressBar.classList.add('bg-success');
        } else if (containment_percentage >= 80) {
            this.progressBar.classList.add('bg-warning');
        } else {
            this.progressBar.classList.add('bg-danger');
        }
        
        // Generate messages based on metrics
        this.updateMessages(metrics);
    }
    
    updateMessages(metrics) {
        const {
            containment_percentage,
            last_container_fill_percentage,
            total_containers,
            total_capacity
        } = metrics;
        
        let messages = [];
        let alertClass = 'alert-info';
        
        // Containment status
        if (containment_percentage >= 100) {
            messages.push(`✅ <strong>Sufficient Capacity:</strong> ${containment_percentage.toFixed(1)}% containment`);
            alertClass = 'alert-success';
        } else {
            messages.push(`❌ <strong>Insufficient Capacity:</strong> ${containment_percentage.toFixed(1)}% containment`);
            alertClass = 'alert-danger';
        }
        
        // Efficiency warnings
        if (last_container_fill_percentage < 75 && containment_percentage >= 100) {
            messages.push(`⚠️ <strong>Low Efficiency:</strong> Last container only ${last_container_fill_percentage.toFixed(1)}% filled`);
            if (alertClass === 'alert-success') {
                alertClass = 'alert-warning';
            }
        } else if (last_container_fill_percentage >= 90) {
            messages.push(`🎯 <strong>High Efficiency:</strong> Optimal container utilization`);
        }
        
        // Container count summary
        if (total_containers > 1) {
            messages.push(`📦 Using ${total_containers} containers with total capacity of ${total_capacity.toFixed(2)} units`);
        }
        
        // Render messages
        this.messageArea.innerHTML = `
            <div class="alert ${alertClass} mb-0">
                ${messages.join('<br>')}
            </div>
        `;
    }
    
    clear() {
        if (this.progressBar) {
            this.progressBar.style.width = '0%';
            this.progressBar.className = 'progress-bar';
        }
        
        if (this.messageArea) {
            this.messageArea.innerHTML = '<div class="alert alert-secondary mb-0">No containers selected</div>';
        }
    }
    
    showError(message) {
        if (this.messageArea) {
            this.messageArea.innerHTML = `<div class="alert alert-danger mb-0">${message}</div>`;
        }
    }
}

// Initialize global progress bar
let containerProgressBar;
document.addEventListener('DOMContentLoaded', () => {
    containerProgressBar = new ContainerProgressBar();
    window.containerProgressBar = containerProgressBar;
});
