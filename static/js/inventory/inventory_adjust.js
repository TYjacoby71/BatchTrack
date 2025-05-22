
// Inventory adjustment functionality
document.addEventListener('DOMContentLoaded', function() {
  const adjustForm = document.getElementById('inventoryAdjustForm');
  const updateForm = document.getElementById('updateInventoryForm');
  
  if (adjustForm) {
    adjustForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const amount = document.getElementById('adjustAmount').value;
      const itemId = document.getElementById('itemId').value;
      
      fetch('/inventory/adjust', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
        },
        body: JSON.stringify({ item_id: itemId, amount: amount })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          window.location.reload();
        } else {
          alert('Error adjusting inventory: ' + data.error);
        }
      });
    });
  }
});
