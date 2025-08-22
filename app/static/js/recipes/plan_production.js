// Plan Production JavaScript functionality
// This file provides additional functionality for the plan production page

console.log('Plan production JavaScript loaded');

// Alpine.js component for Plan Production
document.addEventListener('alpine:init', () => {
  Alpine.data('planProductionApp', () => ({
    recipeId: null,
    scale: 1,
    csrfToken: null,
    batchCode: '',
    batchType: 'ingredient',
    
    // Alert messages
    alertMessage: '',
    errorMessage: '',
    
    // Loading states
    loading: false,
    
    // Stock check properties
    stockChecked: false,
    stockCheckPassed: false,
    stockResults: [],
    
    // Container properties
    requiresContainers: false,
    containersSelected: [],
    containerToggleEnabled: false,
    containers: [],
    containmentPercent: 0,
    liveContainmentMessage: 'No containers selected',
    containmentIssue: '',
    
    // Batch actions
    canStartBatch: false,
    allOk: true,
    costInfo: {},
    containerDebug: {
      lastCall: null,
      responseCount: 0,
      error: null
    },

    init() {
      // Attempt to get CSRF token from meta tag
      const csrfMetaTag = document.querySelector('meta[name="csrf-token"]');
      if (csrfMetaTag) {
        this.csrfToken = csrfMetaTag.getAttribute('content');
      } else {
        console.warn('CSRF token meta tag not found.');
      }

      // Initialize recipeId from URL path
      const pathParts = window.location.pathname.split('/');
      const recipeIndex = pathParts.indexOf('recipes');
      if (recipeIndex !== -1 && pathParts[recipeIndex + 1]) {
        this.recipeId = pathParts[recipeIndex + 1];
        console.log('Recipe ID found:', this.recipeId);
      } else {
        // Fallback to hidden input or data attribute
        const recipeIdInput = document.querySelector('input[name="recipe_id"]');
        if (recipeIdInput) {
          this.recipeId = recipeIdInput.value;
        } else {
          const recipeElement = document.querySelector('[data-recipe-id]');
          if (recipeElement) {
            this.recipeId = recipeElement.dataset.recipeId;
          } else {
            console.error('Recipe ID not found.');
          }
        }
      }
      
      // Initialize scale from input if available
      const scaleInput = document.querySelector('input[name="scale"]');
      if (scaleInput) {
        this.scale = parseFloat(scaleInput.value);
      }

      // Check initial state of container toggle if it exists
      const containerToggle = document.querySelector('input[name="check_containers"]');
      if (containerToggle) {
        this.containerToggleEnabled = containerToggle.checked;
      }
    },

    async submitPlanProduction() {
      if (!this.recipeId) {
        alert('Recipe ID is missing.');
        return;
      }
      if (!this.csrfToken) {
        alert('CSRF token is missing. Please refresh the page.');
        return;
      }

      // Reset previous results
      this.stockResults = [];
      this.allOk = true;
      this.costInfo = {};

      // Fetch container plan if toggle is enabled
      if (this.containerToggleEnabled) {
        await this.fetchContainerPlan();
        // If container check failed or returned errors, stop further processing
        if (this.containerDebug.error || !this.allOk) {
          console.log('Stopping plan production due to container check issues.');
          return;
        }
      }

      // Proceed to plan production if containers are ok or toggle is off
      try {
        console.log('Submitting plan production request...');
        const response = await fetch(`/recipes/${this.recipeId}/plan`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken
          },
          body: JSON.stringify({
            scale: this.scale,
            check_containers: this.containerToggleEnabled // Pass the current state of the toggle
          })
        });

        if (!response.ok) {
          const errorData = await response.json();
          alert(`Error planning production: ${errorData.error || response.statusText}`);
          this.allOk = false;
          return;
        }

        const data = await response.json();
        console.log('Plan production response:', data);

        this.stockResults = data.stock_results || [];
        this.allOk = data.success;
        this.costInfo = data.cost_info || {};

        if (!this.allOk) {
          alert(`Production planning failed. Please check stock levels and container availability.`);
        }

      } catch (error) {
        console.error('Error during plan production submission:', error);
        alert(`An unexpected error occurred: ${error.message}`);
        this.allOk = false;
      }
    },

    async checkStock() {
      this.loading = true;
      this.errorMessage = '';
      this.alertMessage = '';
      
      try {
        const response = await fetch(`/recipes/${this.recipeId}/plan`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken
          },
          body: JSON.stringify({
            scale: this.scale,
            check_containers: this.requiresContainers
          })
        });

        if (!response.ok) {
          const errorData = await response.json();
          this.errorMessage = errorData.error || 'Stock check failed';
          this.stockChecked = false;
          this.stockCheckPassed = false;
          return;
        }

        const data = await response.json();
        this.stockResults = data.stock_results || [];
        this.stockChecked = true;
        this.stockCheckPassed = data.success;
        
        if (this.stockCheckPassed) {
          this.alertMessage = 'Stock check passed! All ingredients available.';
          this.canStartBatch = true;
        } else {
          this.errorMessage = 'Stock check failed. Some ingredients are not available.';
          this.canStartBatch = false;
        }

        // Handle container results if containers are required
        if (this.requiresContainers) {
          const containerResults = this.stockResults.filter(item => 
            item.category === 'container' || item.type === 'container'
          );
          this.containers = containerResults;
          this.updateContainmentInfo();
        }

      } catch (error) {
        this.errorMessage = `Stock check failed: ${error.message}`;
        this.stockChecked = false;
        this.stockCheckPassed = false;
        this.canStartBatch = false;
      } finally {
        this.loading = false;
      }
    },

    checkStockOrWarn() {
      if (!this.stockChecked) {
        this.checkStock();
      } else if (!this.stockCheckPassed) {
        this.alertMessage = 'Please resolve stock issues before proceeding.';
      }
    },

    resetForm() {
      this.scale = 1;
      this.batchCode = '';
      this.batchType = 'ingredient';
      this.requiresContainers = false;
      this.stockChecked = false;
      this.stockCheckPassed = false;
      this.stockResults = [];
      this.containers = [];
      this.containersSelected = [];
      this.canStartBatch = false;
      this.alertMessage = '';
      this.errorMessage = '';
      this.containmentPercent = 0;
      this.liveContainmentMessage = 'No containers selected';
      this.containmentIssue = '';
    },

    toggleContainerCheck(event) {
      this.requiresContainers = event.target.checked;
      if (!this.requiresContainers) {
        this.containers = [];
        this.containersSelected = [];
        this.containmentPercent = 0;
        this.liveContainmentMessage = 'Container check disabled';
        this.containmentIssue = '';
      }
    },

    updateContainmentInfo() {
      if (!this.requiresContainers || this.containers.length === 0) {
        this.containmentPercent = 0;
        this.liveContainmentMessage = 'No containers available';
        return;
      }

      const totalSelected = this.containersSelected.length;
      const totalAvailable = this.containers.length;
      
      if (totalSelected === 0) {
        this.containmentPercent = 0;
        this.liveContainmentMessage = 'No containers selected';
        this.containmentIssue = 'Please select containers for this batch';
      } else {
        this.containmentPercent = Math.min((totalSelected / totalAvailable) * 100, 100);
        this.liveContainmentMessage = `${totalSelected} of ${totalAvailable} containers selected`;
        
        if (this.containmentPercent < 100) {
          this.containmentIssue = 'Additional containers may be needed';
        } else {
          this.containmentIssue = '';
        }
      }
    },

    async fetchContainerPlan() {
      // Update debug info
      this.containerDebug.lastCall = new Date().toLocaleTimeString();
      this.containerDebug.responseCount++;
      this.containerDebug.error = null;

      if (!this.containerToggleEnabled) {
        this.containers = [];
        return;
      }

      try {
        console.log(`[CONTAINER DEBUG ${this.containerDebug.responseCount}] Making container check call...`);

        const response = await fetch(`/recipes/${this.recipeId}/plan`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken
          },
          body: JSON.stringify({
            scale: this.scale,
            check_containers: true
          })
        });

        console.log(`[CONTAINER DEBUG ${this.containerDebug.responseCount}] Response status:`, response.status);
        const data = await response.json();
        console.log(`[CONTAINER DEBUG ${this.containerDebug.responseCount}] USCS Container response:`, data);

        if (!data.success) {
          this.containerDebug.error = data.error;
          console.error('[CONTAINER DEBUG] Error in response:', data.error);

          // Show error alert
          if (data.error) {
            alert(`Container check failed: ${data.error}`);
          }
          this.allOk = false; // Mark as not OK if container check fails
          return;
        }

        const containerResults = (data.stock_results || []).filter(item => 
          item.category === 'container' || item.type === 'container'
        );

        console.log(`[CONTAINER DEBUG ${this.containerDebug.responseCount}] Processed containers:`, containerResults);

        // Check if user has container toggle enabled but no containers available
        if (this.containerToggleEnabled && containerResults.length === 0) {
          console.warn('[CONTAINER DEBUG] No containers found despite toggle being enabled');

          // Check if recipe has no allowed containers specified
          alert('⚠️ No containers available!\n\nThe container toggle is selected but either:\n• No containers are specified as allowable for this recipe, or\n• No containers are currently in stock\n\nPlease add containers to inventory or specify allowed containers for this recipe.');
          this.allOk = false; // Mark as not OK if no containers are found
        }

        this.containers = containerResults;

      } catch (error) {
        console.error('[CONTAINER DEBUG] Fetch error:', error);
        this.containerDebug.error = error.message;
        alert(`Container check failed: ${error.message}`);
        this.allOk = false; // Mark as not OK if fetch fails
      }
    },

    // Helper to toggle container check based on the input element's state
    toggleContainerCheck(event) {
      this.containerToggleEnabled = event.target.checked;
      if (!this.containerToggleEnabled) {
        this.containers = []; // Clear containers if toggle is turned off
      }
    },

    // Method to update scale from input, also triggers plan if needed
    updateScale(event) {
      this.scale = parseFloat(event.target.value);
      // Optionally re-run planning or container check if scale changes
      // For now, it's only triggered by the main submit button
    }
  }));
});

// Additional helper functions can be added here as needed
// The main functionality is handled by Alpine.js in the template