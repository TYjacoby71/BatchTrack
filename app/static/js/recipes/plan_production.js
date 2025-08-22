// Plan Production JavaScript functionality
// This file provides additional functionality for the plan production page

console.log('Plan production JavaScript loaded');

document.addEventListener('DOMContentLoaded', function() {
    // Simple form enhancements only
    const scaleInput = document.getElementById('scale');
    const projectedYieldInput = document.querySelector('input[readonly]');
    const baseYield = parseFloat(projectedYieldInput?.value || 0);

    // Update projected yield when scale changes
    if (scaleInput && projectedYieldInput) {
        scaleInput.addEventListener('input', function() {
            const scale = parseFloat(this.value || 1);
            const newYield = (baseYield * scale).toFixed(2);
            projectedYieldInput.value = newYield;
        });
    }

    // Container toggle functionality
    const containerToggle = document.getElementById('requiresContainers');
    // The selector for containerCard might need to be adjusted if the HTML structure is different
    // Assuming a card element that contains an element with id="containerToggle"
    const containerCard = document.querySelector('.card:has(#containerToggle)');


    if (containerToggle && containerCard) {
        // Initialize the display based on the initial state of the toggle
        containerCard.style.display = containerToggle.checked ? 'block' : 'none';

        containerToggle.addEventListener('change', function() {
            containerCard.style.display = this.checked ? 'block' : 'none';
        });
    }

    // Form submission feedback
    const form = document.querySelector('form[method="POST"]');
    if (form) {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                // Using Bootstrap spinner classes for visual feedback
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Planning...';
                submitBtn.disabled = true;
            }
        });
    }
});