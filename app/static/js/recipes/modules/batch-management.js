
// Batch Management Module
export class BatchManager {
    constructor(mainManager) {
        this.main = mainManager;
    }

    bindEvents() {
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (startBatchBtn) {
            startBatchBtn.addEventListener('click', () => this.startBatch());
        }
    }

    async startBatch() {
        if (!this.main.recipe) return;

        try {
            const productQuantity = this.main.baseYield * this.main.scale;

            const result = await this.main.apiCall('/api/batches/api-start-batch', {
                recipe_id: this.main.recipe.id,
                product_quantity: productQuantity
            });

            if (result.success) {
                this.showSuccessMessage(result.message);
                setTimeout(() => {
                    window.location.href = `/batches/${result.batch_id}`;
                }, 2000);
            } else {
                this.showErrorMessage(result.message);
            }
        } catch (error) {
            console.error('Start batch error:', error);
            alert('Error starting batch. Please try again.');
        }
    }

    showSuccessMessage(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'alert alert-success';
        successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;

        const mainContent = document.querySelector('.container-fluid');
        mainContent.insertBefore(successDiv, mainContent.firstChild);
    }

    showErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;

        const mainContent = document.querySelector('.container-fluid');
        mainContent.insertBefore(errorDiv, mainContent.firstChild);
    }
}
