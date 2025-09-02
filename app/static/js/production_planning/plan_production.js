import { ContainerManager } from './modules/container-management.js';
import { StockChecker } from './modules/stock-check.js';
import { FormValidator } from './modules/validation.js';

document.addEventListener('DOMContentLoaded', () => {
    const containerManager = new ContainerManager();
    const stockChecker = new StockChecker(containerManager);
    const formValidator = new FormValidator();

    document.getElementById('plan-production-form').addEventListener('submit', (event) => {
        event.preventDefault();

        if (formValidator.validateForm(event.target)) {
            // Handle form submission logic
            console.log('Form submitted successfully!');
            // Example: Send data to server
            // const formData = new FormData(event.target);
            // fetch('/api/plan_production', {
            //     method: 'POST',
            //     body: formData
            // })
            // .then(response => response.json())
            // .then(data => {
            //     console.log('Success:', data);
            // })
            // .catch((error) => {
            //     console.error('Error:', error);
            // });
        } else {
            console.log('Form validation failed.');
        }
    });

    // Initialize other components or logic as needed
    containerManager.initialize();
    stockChecker.checkStockLevels();
});