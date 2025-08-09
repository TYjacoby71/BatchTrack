
class BatchTrackApp {
    constructor() {
        this.config = {
            apiBase: '/api',
            csrfToken: document.querySelector('meta[name=csrf-token]')?.content
        };
        this.modules = new Map();
        this.init();
    }

    init() {
        this.setupGlobalErrorHandling();
        this.setupCSRF();
        this.loadModules();
    }

    setupGlobalErrorHandling() {
        window.addEventListener('error', (e) => {
            console.error('BatchTrack Error:', e.error);
            this.showNotification('An error occurred', 'error');
        });
    }

    setupCSRF() {
        // Set CSRF token for all AJAX requests
        const token = this.config.csrfToken;
        if (token) {
            document.addEventListener('DOMContentLoaded', () => {
                const forms = document.querySelectorAll('form');
                forms.forEach(form => {
                    if (!form.querySelector('input[name="csrf_token"]')) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'csrf_token';
                        input.value = token;
                        form.appendChild(input);
                    }
                });
            });
        }
    }

    async apiCall(endpoint, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.config.csrfToken,
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(`${this.config.apiBase}${endpoint}`, config);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            console.error('API Error:', error);
            this.showNotification(`API Error: ${error.message}`, 'error');
            throw error;
        }
    }

    showNotification(message, type = 'info', duration = 5000) {
        // Centralized notification system
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, duration);
    }

    registerModule(name, moduleClass) {
        this.modules.set(name, new moduleClass(this));
    }

    loadModules() {
        // Auto-load modules based on page context
        const body = document.body;
        
        if (body.classList.contains('inventory-page')) {
            import('./modules/InventoryModule.js').then(module => {
                this.registerModule('inventory', module.default);
            });
        }
        
        if (body.classList.contains('batch-page')) {
            import('./modules/BatchModule.js').then(module => {
                this.registerModule('batch', module.default);
            });
        }
    }
}

// Initialize app
window.BatchTrack = new BatchTrackApp();
