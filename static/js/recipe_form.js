
document.addEventListener('DOMContentLoaded', () => {
  const rows = document.querySelectorAll('.ingredient-row');

  rows.forEach(row => {
    const ingredientSelect = row.querySelector('[name^="ingredient_id"]');
    const unitSelect = row.querySelector('[name^="unit"]');
    const alertCell = row.querySelector('.conversion-warning');

    function validateUnit() {
      const ingredientId = ingredientSelect?.value;
      const toUnit = unitSelect?.value;

      if (!ingredientId || !toUnit) return;

      fetch(`/convert/1/${encodeURIComponent('inventory')}/${encodeURIComponent(toUnit)}?ingredient_id=${ingredientId}`)
        .then(res => res.json())
        .then(data => {
          alertCell.innerHTML = '';

          if (data.conversion_type === 'direct') {
            alertCell.innerHTML = '✅';
          } else if (data.conversion_type === 'custom') {
            alertCell.innerHTML = '⚠️ <small>Custom Mapping Used</small>';
          } else if (data.conversion_type === 'density') {
            alertCell.innerHTML = `⚠️ <small>Used density (${data.density_used})</small>`;
          } else if (data.conversion_type === 'error') {
            alertCell.innerHTML = `<span class="text-danger">❌ ${data.message}</span>`;
          }
        })
        .catch(err => {
          alertCell.innerHTML = '<span class="text-danger">⚠️ Conversion Failed</span>';
        });
    }

    if (ingredientSelect) ingredientSelect.addEventListener('change', validateUnit);
    if (unitSelect) unitSelect.addEventListener('change', validateUnit);
  });
});
