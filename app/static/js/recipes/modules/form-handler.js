
// Form Handler Module
export class FormHandler {
    constructor(mainApp) {
        this.main = mainApp;
    }

    bindEvents() {
        // Form submission
        const form = document.getElementById('planProductionForm');
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
    }

    handleFormSubmit(e) {
        e.preventDefault();
        
        if (!this.main.batchType) {
            alert('Please select a batch type');
            return;
        }
        
        console.log('Form submitted with data:', {
            scale: this.main.scale,
            batchType: this.main.batchType,
            requiresContainers: this.main.requiresContainers
        });
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value;
    }
}
