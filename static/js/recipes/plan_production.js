
function downloadCSV(stockResults) {
  if (!stockResults?.length) return;

  let csv = "Ingredient,Required,Available,Unit,Status\n";
  stockResults.forEach(row => {
    csv += `${row.ingredient},${row.required},${row.available},${row.unit},${row.status}\n`;
  });

  const blob = new Blob([csv], { type: 'text/csv' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'stock_check_report.csv';
  link.click();
}

// Make functions globally available
window.downloadCSV = downloadCSV;
