
/**
 * Container Unit Mismatch Drawer
 * Handles recipe yield unit and container capacity unit mismatches
 */

class ContainerUnitMismatchDrawer {
    constructor() {
        this.setupEventListeners();
        console.log('🔧 CONTAINER DRAWER: Container unit mismatch drawer initialized');
    }

    setupEventListeners() {
        // Listen for drawer-specific events
        window.addEventListener('recipe.yield.updated', (event) => {
            console.log('🔧 CONTAINER DRAWER: Recipe yield updated', event.detail);
            this.handleYieldUpdate(event.detail);
        });

        window.addEventListener('container.requirements.disable', (event) => {
            console.log('🔧 CONTAINER DRAWER: Container requirements disabled', event.detail);
            this.handleContainerDisable(event.detail);
        });
    }

    /**
     * Handle recipe yield update - trigger container plan refresh
     */
    async handleYieldUpdate(detail) {
        console.log('🔧 CONTAINER DRAWER: Handling yield update for recipe', detail.recipe_id);
        
        // Trigger container plan refresh if the container plan fetcher is available
        if (window.containerPlanFetcher && window.containerPlanFetcher.fetchContainerPlan) {
            console.log('🔧 CONTAINER DRAWER: Triggering container plan refresh');
            try {
                await window.containerPlanFetcher.fetchContainerPlan();
                console.log('🔧 CONTAINER DRAWER: Container plan refresh completed');
            } catch (error) {
                console.error('🔧 CONTAINER DRAWER: Container plan refresh failed', error);
            }
        } else {
            console.warn('🔧 CONTAINER DRAWER: Container plan fetcher not available, falling back to page reload');
            // Fallback: reload the page to refresh the container plan
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    }

    /**
     * Handle container requirements disable
     */
    handleContainerDisable(detail) {
        console.log('🔧 CONTAINER DRAWER: Disabling container requirements for recipe', detail.recipe_id);
        
        // Switch to manual mode if available
        if (window.manualContainerMode && window.manualContainerMode.enableManualMode) {
            console.log('🔧 CONTAINER DRAWER: Switching to manual container mode');
            window.manualContainerMode.enableManualMode();
        } else {
            console.warn('🔧 CONTAINER DRAWER: Manual container mode not available');
        }
    }

    /**
     * Initialize modal-specific handlers when modal is opened
     */
    initializeModal(modalElement) {
        console.log('🔧 CONTAINER DRAWER: Initializing modal handlers');
        
        const form = modalElement.querySelector('#yieldFixForm');
        const successAlert = modalElement.querySelector('#yieldFixSuccess');
        const errorAlert = modalElement.querySelector('#yieldFixError');
        const disableBtn = modalElement.querySelector('#disableContainersBtn');

        if (form) {
            this.setupFormHandler(form, successAlert, errorAlert);
        }

        if (disableBtn) {
            this.setupDisableHandler(disableBtn);
        }
    }

    setupFormHandler(form, successAlert, errorAlert) {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            console.log('🔧 CONTAINER DRAWER: Form submission started');
            
            const submitBtn = form.querySelector('button[type="submit"]');
            const formData = new FormData(form);
            const updateUrl = form.dataset.updateUrl;

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving';
            }

            try {
                const response = await fetch(updateUrl, {
                    method: 'POST',
                    headers: { 'Accept': 'application/json' },
                    body: formData
                });
                
                const payload = await response.json();
                
                if (!response.ok || !payload.success) {
                    throw new Error(payload.error || 'Failed to update recipe yield');
                }

                this.showSuccess(successAlert, 'Yield updated. Refreshing plan…');
                
                // Extract recipe ID from the form or URL
                const recipeIdMatch = updateUrl.match(/\/(\d+)\/yield$/);
                const recipeId = recipeIdMatch ? parseInt(recipeIdMatch[1]) : null;

                window.dispatchEvent(new CustomEvent('recipe.yield.updated', {
                    detail: {
                        recipe_id: recipeId,
                        yield_amount: payload.yield_amount,
                        yield_unit: payload.yield_unit
                    }
                }));

                // Close modal after success
                setTimeout(() => {
                    const bootstrapModal = bootstrap.Modal.getInstance(form.closest('.modal'));
                    if (bootstrapModal) {
                        bootstrapModal.hide();
                    }
                }, 600);

            } catch (err) {
                console.error('🔧 CONTAINER DRAWER: Form submission failed', err);
                this.showError(errorAlert, err.message);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-sync-alt me-1"></i> Save &amp; Refresh';
                }
            }
        });
    }

    setupDisableHandler(disableBtn) {
        disableBtn.addEventListener('click', () => {
            console.log('🔧 CONTAINER DRAWER: Disable containers button clicked');
            
            // Extract recipe ID from button context
            const modal = disableBtn.closest('.modal');
            const recipeId = modal ? modal.dataset.recipeId : null;
            
            window.dispatchEvent(new CustomEvent('container.requirements.disable', {
                detail: { recipe_id: recipeId }
            }));
            
            const bootstrapModal = bootstrap.Modal.getInstance(modal);
            if (bootstrapModal) {
                bootstrapModal.hide();
            }
        });
    }

    showSuccess(successAlert, message) {
        if (successAlert) {
            successAlert.textContent = message || 'Yield updated. Refreshing plan…';
            successAlert.classList.remove('d-none');
        }
        const errorAlert = successAlert ? successAlert.parentElement.querySelector('.alert-danger') : null;
        if (errorAlert) {
            errorAlert.classList.add('d-none');
        }
    }

    showError(errorAlert, message) {
        if (errorAlert) {
            errorAlert.textContent = message || 'Unable to update yield.';
            errorAlert.classList.remove('d-none');
        }
        const successAlert = errorAlert ? errorAlert.parentElement.querySelector('.alert-success') : null;
        if (successAlert) {
            successAlert.classList.add('d-none');
        }
    }
}

// Initialize the drawer handler
if (!window.containerUnitMismatchDrawer) {
    window.containerUnitMismatchDrawer = new ContainerUnitMismatchDrawer();
}

// Export for modules
export { ContainerUnitMismatchDrawer };
