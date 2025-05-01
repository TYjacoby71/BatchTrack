// All logic moved to Alpine.js component in plan_production.html template

checkStock() {
      const csrfToken = document.querySelector('input[name=csrf_token]').value;
      fetch('/api/check-stock', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ 
          recipe_id: parseInt(this.recipeId), 
          scale: parseFloat(this.scale),
          flex_mode: this.flexMode
        })
      })
        .then(res => res.json())
        .then(data => {
          this.stockChecked = true;
          this.stockCheckPassed = data.all_ok;
          this.stockResults = data.ingredients || [];
        })
        .catch(err => {
          console.log('Error checking stock:', err);
          this.stockChecked = false;
        });
    },

    downloadCSV() {
      if (!this.stockResults?.length) return;

      let csv = "Ingredient,Required,Available,Unit,Status\n";
      this.stockResults.forEach(row => {
        csv += `${row.ingredient},${row.required},${row.available},${row.unit},${row.status}\n`;
      });

      const blob = new Blob([csv], { type: 'text/csv' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'stock_check_report.csv';
      link.click();
    },

    async startBatch() {
        const recipeId = document.getElementById('recipeSelect').value;
        const scale = document.getElementById('scaleInput').value;
        const notes = document.getElementById('batchNotes').value;
        const token = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        try {
          const response = await fetch('/batches/start_batch', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'X-CSRF-Token': token
            },
            body: JSON.stringify({ 
              recipe_id: recipeId, 
              scale: parseFloat(scale),
              notes: notes
            })
          });
          //Further handling of the response could be added here.  For example:
          //if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
          //const data = await response.json();
          //Handle the data from the server response.

        } catch (error) {
          console.error('Error starting batch:', error);
          //Add error handling as needed. For example, display an error message to the user.
        }
      }