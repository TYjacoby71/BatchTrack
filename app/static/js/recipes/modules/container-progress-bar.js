
/**
 * Container Progress Bar Module - Pure Display Logic Only
 * 
 * Displays containment and efficiency metrics from backend data.
 * No calculations performed here - just visual display.
 */
export class ContainerProgressBar {
    constructor() {
        this.progressBar = document.getElementById('containmentProgressBar');
        this.percentageLabel = document.getElementById('containmentPercent');
        this.messageElement = document.getElementById('liveContainmentMessage');
        this.warningElement = document.getElementById('containmentIssue');
        this.warningText = document.getElementById('containmentIssueText');
    }

    updateProgress(metrics) {
        console.log('🔧 PROGRESS_BAR: Updating with metrics:', metrics);

        if (!this.progressBar || !this.percentageLabel) {
            console.warn('🔧 PROGRESS_BAR: Required elements not found');
            return;
        }

        const containmentPercentage = Math.min(100, Math.max(0, metrics.containment_percentage || 0));
        const totalCapacity = metrics.total_capacity || 0;
        const totalContainers = metrics.total_containers || 0;
        const warnings = metrics.warnings || [];

        // Update progress bar
        this.progressBar.style.width = `${containmentPercentage}%`;
        this.progressBar.textContent = `${containmentPercentage.toFixed(1)}%`;
        
        // Update percentage label
        this.percentageLabel.textContent = `${containmentPercentage.toFixed(1)}%`;

        // Set progress bar color based on percentage
        this.updateProgressBarColor(containmentPercentage);

        // Update containment message
        this.updateContainmentMessage(containmentPercentage, totalCapacity, totalContainers);

        // Show warnings if any
        this.displayWarnings(warnings, containmentPercentage);
    }

    updateProgressBarColor(percentage) {
        // Remove existing color classes
        this.progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
        
        if (percentage >= 100) {
            this.progressBar.classList.add('bg-success');
        } else if (percentage >= 90) {
            this.progressBar.classList.add('bg-warning');
        } else if (percentage >= 50) {
            this.progressBar.classList.add('bg-info');
        } else {
            this.progressBar.classList.add('bg-danger');
        }
    }

    updateContainmentMessage(percentage, totalCapacity, totalContainers) {
        if (!this.messageElement) return;

        let message = '';
        
        if (percentage >= 100) {
            message = `✅ Perfect containment with ${totalContainers} container(s) providing ${totalCapacity} total capacity`;
        } else if (percentage >= 90) {
            message = `⚠️ Good containment (${percentage.toFixed(1)}%) with ${totalContainers} container(s)`;
        } else if (percentage >= 50) {
            message = `⚠️ Partial containment (${percentage.toFixed(1)}%) - consider additional containers`;
        } else {
            message = `❌ Insufficient containment (${percentage.toFixed(1)}%) - more containers needed`;
        }

        this.messageElement.textContent = message;
    }

    displayWarnings(warnings, percentage) {
        if (!this.warningElement || !this.warningText) return;

        if (warnings.length > 0 || percentage < 100) {
            let warningMessage = '';
            
            if (warnings.length > 0) {
                warningMessage = warnings.join('; ');
            } else if (percentage < 100) {
                warningMessage = `Only ${percentage.toFixed(1)}% of batch can be contained with current selection`;
            }
            
            this.warningText.textContent = warningMessage;
            this.warningElement.style.display = 'block';
        } else {
            this.warningElement.style.display = 'none';
        }
    }

    clear() {
        if (this.progressBar) {
            this.progressBar.style.width = '0%';
            this.progressBar.textContent = '0%';
            this.progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
            this.progressBar.classList.add('bg-secondary');
        }
        
        if (this.percentageLabel) {
            this.percentageLabel.textContent = '0%';
        }
        
        if (this.messageElement) {
            this.messageElement.textContent = 'No containers selected';
        }
        
        if (this.warningElement) {
            this.warningElement.style.display = 'none';
        }
    }

    hide() {
        const progressContainer = document.getElementById('containerProgress');
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }
    }

    show() {
        const progressContainer = document.getElementById('containerProgress');
        if (progressContainer) {
            progressContainer.style.display = 'block';
        }
    }
}
