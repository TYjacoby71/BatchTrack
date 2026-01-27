
// Batch Management Module
export class BatchManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.overrideModal = null;
    }

    bindEvents() {
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (startBatchBtn) {
            startBatchBtn.addEventListener('click', () => this.startBatch());
        }

        const queueBatchBtn = document.getElementById('queueBatchBtn');
        if (queueBatchBtn) {
            queueBatchBtn.addEventListener('click', () => this.addToQueue());
        }

        const confirmForceBtn = document.getElementById('confirmForceStartBtn');
        if (confirmForceBtn) {
            confirmForceBtn.addEventListener('click', () => {
                this.main.stockOverrideAcknowledged = true;
                this.hideOverrideModal();
                this.startBatch(true);
            });
        }
    }

    async startBatch(forceOverride = false) {
        if (!this.main.recipe) return;

        if (!this.main.stockChecked) {
            this.showErrorMessage('Please run a stock check before starting a batch.');
            return;
        }

        const shouldForce = forceOverride || this.main.stockOverrideAcknowledged;
        if (!shouldForce && !this.main.stockCheckPassed) {
            this.showInsufficientModal();
            return;
        }

        try {
            const flatPortion = this.getFlatPortionFields();
            const payload = {
                recipe_id: this.main.recipe.id,
                scale: this.main.scale,
                batch_type: this.main.batchType || 'ingredient',
                notes: document.getElementById('batchNotes')?.value || '',
                requires_containers: !!this.main.requiresContainers,
                containers: this.getSelectedContainers(),
                // Absolute: send flat portion fields only
                ...(flatPortion || {}),
                projected_yield: this.main.getProjectedYield(),
                projected_yield_unit: this.main.unit,
                force_start: shouldForce
            };

            const result = await this.main.apiCall('/batches/api/start-batch', payload);

            if (result.requires_override) {
                this.main.stockIssues = result.stock_issues || [];
                this.main.stockOverrideAcknowledged = false;
                this.showInsufficientModal(result.stock_issues || []);
                return;
            }

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

    async addToQueue() {
        if (!this.main.recipe) return;

        if (!this.main.stockChecked) {
            this.showErrorMessage('Please run a stock check before adding to the queue.');
            return;
        }

        if (!this.main.stockCheckPassed) {
            this.showErrorMessage('Queueing requires all ingredients in stock.');
            return;
        }

        try {
            const flatPortion = this.getFlatPortionFields();
            const payload = {
                recipe_id: this.main.recipe.id,
                scale: this.main.scale,
                batch_type: this.main.batchType || 'ingredient',
                notes: document.getElementById('batchNotes')?.value || '',
                requires_containers: !!this.main.requiresContainers,
                containers: this.getSelectedContainers(),
                ...(flatPortion || {}),
                projected_yield: this.main.getProjectedYield(),
                projected_yield_unit: this.main.unit
            };

            const result = await this.main.apiCall('/production-planning/queue', payload);

            if (result.success) {
                const queueLabel = result.queue_code ? ` (${result.queue_code})` : '';
                const queueLink = result.queue_url
                    ? ` <a href="${result.queue_url}" class="alert-link">View Queue</a>`
                    : '';
                this.showSuccessMessage(`Added to queue${queueLabel}.${queueLink}`);
            } else {
                this.showErrorMessage(result.message || 'Unable to add to queue.');
            }
        } catch (error) {
            console.error('Add to queue error:', error);
            this.showErrorMessage(error.message || 'Error adding to queue. Please try again.');
        }
    }

    showInsufficientModal(issues = null) {
        const modalEl = document.getElementById('insufficientStockModal');
        if (!modalEl) {
            alert('Insufficient inventory detected. Please add stock before continuing.');
            return;
        }

        const listEl = document.getElementById('insufficientStockList');
        const shortages = (issues && issues.length ? issues : this.main.stockIssues) || [];
        if (listEl) {
            if (!shortages.length) {
                listEl.innerHTML = `
                    <tr>
                        <td colspan="4" class="text-muted text-center">
                            <em>No shortages detected.</em>
                        </td>
                    </tr>
                `;
            } else {
                listEl.innerHTML = shortages.map(item => {
                    const needed = Number(item.needed || item.needed_quantity || item.quantity_needed || 0);
                    const available = Number(item.available ?? item.available_quantity ?? 0);
                    const unit = item.unit || item.needed_unit || item.available_unit || '';
                    const status = (item.status || 'NEEDED').toString().toUpperCase();
                    return `
                        <tr>
                            <td>${item.name || item.item_name || 'Unknown'}</td>
                            <td>${needed.toFixed(2)} ${unit}</td>
                            <td>${available.toFixed(2)} ${unit}</td>
                            <td><span class="badge bg-danger">${status}</span></td>
                        </tr>
                    `;
                }).join('');
            }
        }

        if (!this.overrideModal && window.bootstrap?.Modal) {
            this.overrideModal = new window.bootstrap.Modal(modalEl);
        }

        if (this.overrideModal) {
            this.overrideModal.show();
        } else {
            alert('Insufficient inventory detected. Bootstrap modal is not available.');
        }
    }

    hideOverrideModal() {
        if (this.overrideModal) {
            this.overrideModal.hide();
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

    getFlatPortionFields() {
        const p = this.main?.recipe?.portioning_data;
        if (!p || !p.is_portioned) return null;
        // Absolute: do not scale; portions are derived at finish using final yield
        return {
            is_portioned: true,
            portion_name: p.portion_name || '',
            portion_count: (p.portion_count || null)
        };
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
