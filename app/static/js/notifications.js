/**
 * Notification System for BatchTrack
 * Provides consistent toast-style notifications across the application
 */

(function(window) {
    'use strict';

    // Create notification container if it doesn't exist
    function ensureNotificationContainer() {
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Show a notification toast
     * @param {string} message - The message to display
     * @param {string} type - The type of notification: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in milliseconds (default: 4000, 0 = permanent)
     */
    function showNotification(message, type = 'info', duration = 4000) {
        const container = ensureNotificationContainer();
        
        // Map types to Bootstrap alert classes
        const typeMap = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'danger': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        };
        
        // Map types to icons
        const iconMap = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'danger': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        };

        const alertClass = typeMap[type] || 'alert-info';
        const iconClass = iconMap[type] || 'fas fa-info-circle';

        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show d-flex align-items-center mb-2`;
        notification.setAttribute('role', 'alert');
        notification.style.cssText = `
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideInRight 0.3s ease-out;
        `;
        
        notification.innerHTML = `
            <i class="${iconClass} me-2"></i>
            <span>${escapeHtml(message)}</span>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Add animation keyframes if not already added
        if (!document.getElementById('notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                @keyframes slideInRight {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                @keyframes slideOutRight {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        container.appendChild(notification);

        // Auto-dismiss if duration is set
        if (duration > 0) {
            setTimeout(() => {
                notification.style.animation = 'slideOutRight 0.3s ease-out';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }, duration);
        }

        return notification;
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Export globally
    window.showNotification = showNotification;

    // Alias for compatibility
    window.showAlert = showNotification;

})(window);
