
// Plan production functionality
const planProduction = {
  downloadCSV(stockResults) {
    if (!stockResults?.length) return;
    
    const items = stockResults.map(item => {
      return `${item.ingredient},${item.needed},${item.unit},${item.available}`;
    });
    
    const csv = ['Ingredient,Needed,Unit,Available', ...items].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    
    link.setAttribute('href', url);
    link.setAttribute('download', 'stock_check.csv');
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },

  setupEventListeners() {
    // Add event listeners here
  },

  init() {
    this.setupEventListeners();
  }
};

// Make functions globally available 
window.planProduction = planProduction;
