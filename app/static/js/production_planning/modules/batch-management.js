
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
            const payload = {
                recipe_id: this.main.recipe.id,
                scale: this.main.scale,
                batch_type: this.main.batchType || 'ingredient',
                notes: document.getElementById('batchNotes')?.value || '',
                requires_containers: !!this.main.requiresContainers,
                containers: this.getSelectedContainers(),
                // Portioning snapshot is compiled server-side in the plan; client forwards it unchanged if present
                // Keep this field null here; a dedicated plan endpoint or page-embedded data should supply it when ready
                portioning_data: null
            };

            const result = await this.main.apiCall('/batches/api/start-batch', payload);

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

    getSelectedContainers() {
        if (!this.main.requiresContainers) return [];

        // Prefer manual selections if manual section is visible
        const manualSection = document.getElementById('manualContainerSection');
        const usingManual = manualSection && manualSection.style.display !== 'none';

        if (usingManual) {
            const rows = document.querySelectorAll('#manualContainerRows .container-row');
            const selections = [];
            rows.forEach(row => {
                const select = row.querySelector('select');
                const qtyEl = row.querySelector('input[type="number"]');
                const id = parseInt(select?.value || '');
                const quantity = parseInt(qtyEl?.value || '0');
                if (id && quantity > 0) selections.push({ id, quantity });
            });
            return selections;
        }

        // Otherwise use auto-fill container plan
        const plan = this.main.containerManager?.containerPlan;
        if (!plan?.container_selection?.length) return [];
        return plan.container_selection.map(c => ({ id: c.container_id, quantity: c.containers_needed || c.quantity || 0 })).filter(c => c.quantity > 0);
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
