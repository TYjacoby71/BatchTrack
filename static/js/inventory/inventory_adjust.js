
// Inventory adjustment functionality
document.addEventListener('DOMContentLoaded', function() {
    // Prevent multiple script loading
if (window.inventoryAdjustmentLoaded) {
    return;
}
window.inventoryAdjustmentLoaded = true;
console.log('Inventory adjustment JS loaded');
    
    // Initialize any inventory adjustment specific functionality here
    const adjustmentForms = document.querySelectorAll('.adjustment-form');
    
    adjustmentForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Add any form validation or processing here
            console.log('Adjustment form submitted');
        });
    });
});
