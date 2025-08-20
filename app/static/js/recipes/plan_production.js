
// Plan Production Methods for Alpine.js component
window.PlanProductionMethods = {
  getRemainingStock(containerId, currentIndex) {
    const match = this.allowedContainers.find(c => c.id == containerId);
    if (!match) return 0;

    const allocated = this.containersSelected.reduce((sum, c, idx) => {
      if (idx !== currentIndex && c.id == containerId) {
        return sum + (c.quantity || 0);
      }
      return sum;
    }, 0);

    return match.stock_qty - allocated;
  },

  get totalContained() {
    return this.containersSelected.reduce((sum, c) => sum + (c.capacity * c.quantity), 0);
  },

  get liveContainmentMessage() {
    if (this.containersSelected.length === 0) return '';
    if (this.containmentPercent < 100) {
      return `There will be ${this.remainingToContain.toFixed(2)} ${this.unit} left uncontained.`;
    }
    return 'Full containment achieved.';
  },

  get canStartBatch() {
    const batchTypeSelected = this.batchType !== '';
    if (this.requiresContainers) {
      return batchTypeSelected && this.containmentPercent >= 100 && this.stockChecked && this.stockCheckPassed;
    }
    return batchTypeSelected && this.stockChecked && this.stockCheckPassed;
  },

  onContainerRequirementChange() {
    if (!this.requiresContainers) {
      this.containersSelected = [];
      this.containmentPercent = 0;
      this.remainingToContain = 0;
      this.containmentIssue = '';
      this.allowedContainers = [];
    } else {
      this.$nextTick(() => {
        this.fetchContainerPlan();
      });
    }
  },

  // Updated to use new stock check service
  fetchContainerPlan() {
    if (!this.requiresContainers) {
      this.allowedContainers = [];
      this.containersSelected = [];
      this.updateProgress();
      return;
    }

    const scale = this.scale || 1.0;
    
    // Use the Universal Stock Check Service for container availability
    fetch('/api/stock/check-containers', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-CSRF-Token': this.getCSRFToken()
      },
      body: JSON.stringify({ 
        recipe_id: parseInt(this.recipeId), 
        scale: parseFloat(scale)
      })
    })
      .then(res => res.json())
      .then(data => {
        console.log('Container stock check response:', data);
        this.allowedContainers = data.available_containers || [];

        if (this.autoFill && this.requiresContainers && this.allowedContainers.length > 0) {
          this.performAutoFill();
        } else if (!this.autoFill) {
          this.validateExistingSelections();
        }

        this.refreshContainmentStatus();
      })
      .catch(err => {
        console.error('Error fetching container plan:', err);
        this.allowedContainers = [];
        this.containersSelected = [];
        this.updateProgress();
      });
  },

  performAutoFill() {
    const projected = this.baseYield * this.scale;
    let remainingVolume = projected;

    const availableContainers = [...this.allowedContainers]
      .filter(c => c.stock_qty > 0)
      .sort((a, b) => b.storage_amount - a.storage_amount);

    let selectedContainers = [];
    
    for (const container of availableContainers) {
      if (remainingVolume <= 0) break;
      
      const capacity = container.storage_amount;
      const maxNeeded = Math.floor(remainingVolume / capacity);
      const qtyToUse = Math.min(maxNeeded, container.stock_qty);

      if (qtyToUse > 0) {
        selectedContainers.push({
          id: container.id,
          quantity: qtyToUse,
          name: container.name,
          capacity: capacity,
          unit: container.storage_unit
        });
        remainingVolume -= qtyToUse * capacity;
      }
    }

    if (remainingVolume > 0) {
      for (const container of availableContainers) {
        const alreadyUsed = selectedContainers.find(s => s.id === container.id);
        const remainingStock = container.stock_qty - (alreadyUsed ? alreadyUsed.quantity : 0);
        
        if (remainingStock > 0) {
          if (alreadyUsed) {
            alreadyUsed.quantity += 1;
          } else {
            selectedContainers.push({
              id: container.id,
              quantity: 1,
              name: container.name,
              capacity: container.storage_amount,
              unit: container.storage_unit
            });
          }
          break;
        }
      }
    }

    this.containersSelected = selectedContainers;
    this.updateProgress();
    this.evaluateContainment();
  },

  validateExistingSelections() {
    this.containersSelected = this.containersSelected.filter(selected => {
      const container = this.allowedContainers.find(c => c.id === selected.id);
      if (!container) return false;
      
      selected.name = container.name;
      selected.capacity = container.storage_amount;
      selected.unit = container.storage_unit;
      
      const remainingStock = this.getRemainingStock(selected.id, -1);
      if (selected.quantity > remainingStock) {
        selected.quantity = Math.max(0, remainingStock);
      }
      
      return selected.quantity > 0;
    });
    
    this.updateProgress();
    this.evaluateContainment();
  },

  updateProgress() {
    const projected = this.baseYield * this.scale;
    const contained = this.totalContained;
    this.containmentPercent = Math.min((contained / projected) * 100, 100).toFixed(0);
    this.remainingToContain = Math.max(projected - contained, 0);
  },

  refreshContainmentStatus() {
    this.updateProgress();
    this.evaluateContainment();
  },

  evaluateContainment() {
    const projected = this.baseYield * this.scale;
    const totalAvailable = this.allowedContainers.reduce((sum, c) => sum + (c.storage_amount * c.stock_qty), 0);

    this.containmentIssue = '';

    if (totalAvailable < projected) {
      const sizes = this.allowedContainers.map(c => c.storage_amount);
      const smallestContainer = sizes.length ? Math.min(...sizes) : 1;
      const missingUnits = Math.ceil((projected - totalAvailable) / smallestContainer);
      this.containmentIssue = `Error: You need ${missingUnits} more containers to make this batch.`;
      return;
    }

    const totalContained = this.totalContained;
    const containmentRatio = totalContained / projected;
    const isExactMatch = Math.abs(containmentRatio - 1) < 0.001;
    
    if (totalContained < projected) {
      this.containmentIssue = 'Warning: Need one more container for partial fill';
    } else if (totalContained > projected && !isExactMatch) {
      const lastContainer = this.containersSelected[this.containersSelected.length - 1];
      if (lastContainer) {
        const partialAmount = projected - (totalContained - lastContainer.capacity);
        if (partialAmount < lastContainer.capacity && partialAmount > 0) {
          this.containmentIssue = `Warning: Last container will be partially filled (${partialAmount.toFixed(2)} ${this.unit})`;
        }
      }
    }
  },

  updateContainer(index) {
    const container = this.containersSelected[index];
    if (!container || !container.id) return;

    const match = this.allowedContainers.find(c => c.id == container.id);
    if (match) {
      container.capacity = match.storage_amount;
      container.unit = match.storage_unit;
      container.name = match.name;
      const remainingStock = this.getRemainingStock(container.id, index);

      if (remainingStock <= 0) {
        container.quantity = 0;
      } else if (container.quantity > remainingStock) {
        container.quantity = remainingStock;
      }
    }
    this.updateProgress();
    this.evaluateContainment();
  },

  removeContainer(index) {
    this.containersSelected.splice(index, 1);
    this.updateProgress();
    this.evaluateContainment();
  },

  manualAddContainer() {
    if (this.autoFill) {
      alert('Please uncheck Auto-Fill to add containers manually.');
      return;
    }
    const availableContainers = this.allowedContainers.filter(c => {
      const remainingStock = this.getRemainingStock(c.id, -1);
      return remainingStock > 0;
    });
    
    if (availableContainers.length === 0) {
      alert('No containers available in stock.');
      return;
    }
    
    this.containersSelected.push({ 
      id: '', 
      name: '', 
      capacity: 0, 
      quantity: 1, 
      unit: '' 
    });
    this.updateProgress();
    this.evaluateContainment();
  },

  // Updated to use proper stock check service
  checkStock() {
    const csrfToken = this.getCSRFToken();
    fetch('/api/stock/check-stock', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
      },
      body: JSON.stringify({ 
        recipe_id: parseInt(this.recipeId), 
        scale: parseFloat(this.scale)
      })
    })
      .then(res => res.json())
      .then(data => {
        this.stockChecked = true;
        this.stockCheckPassed = data.all_ok;
        this.stockResults = data.stock_results || [];
      })
      .catch(err => {
        this.stockChecked = false;
        this.stockResults = [];
        console.error('Stock check error:', err);
      });
  },

  downloadCSV() {
    if (!this.stockResults?.length) return;
    let csv = "Ingredient,Required,Available,Unit,Status\n";
    this.stockResults.forEach(row => {
      csv += `${row.ingredient},${row.needed},${row.available},${row.unit},${row.status}\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'stock_check_report.csv';
    link.click();
  },

  downloadShoppingList() {
    if (!this.stockResults?.length) return;
    const needed = this.stockResults.filter(item => item.status === 'LOW' || item.status === 'NEEDED');
    if (!needed.length) {
      alert('No items need restocking!');
      return;
    }
    let text = "Shopping List\n=============\n\n";
    needed.forEach(item => {
      const missing = item.needed - item.available;
      text += `${item.ingredient}: ${missing.toFixed(2)} ${item.unit}\n`;
    });
    const blob = new Blob([text], { type: 'text/plain' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'shopping_list.txt';
    link.click();
  },

  // Updated to use new batch service
  async startBatch() {
    if (!this.canStartBatch) {
      if (this.batchType === '') {
        alert('Please select a batch type before starting the batch');
        return;
      }
      alert('Please check stock and ensure containers are properly allocated before starting batch');
      return;
    }

    const csrfToken = this.getCSRFToken();
    try {
      // Use the new batch service endpoint
      const response = await fetch('/api/batches/start-batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({
          recipe_id: this.recipeId,
          scale: this.scale,
          batch_type: this.batchType,
          requires_containers: this.requiresContainers,
          notes: '',
          containers: this.containersSelected.map(c => ({
            id: c.id,
            quantity: c.quantity
          }))
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Network response was not ok');
      }

      const data = await response.json();
      if (data.batch_id) {
        window.location.href = `/batches/in-progress/${data.batch_id}`;
      } else {
        throw new Error('No batch ID returned');
      }
    } catch (error) {
      alert('Error starting batch: ' + error.message);
    }
  },

  getCSRFToken() {
    const csrfToken = document.querySelector('input[name="csrf_token"]');
    return csrfToken ? csrfToken.value : '';
  }
};
