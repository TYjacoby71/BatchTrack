// Utility functions for BatchTrack

// Safe querySelector that prevents empty selector errors
function safeQuerySelector(selector) {
    if (!selector || selector === '#' || selector === '.') {
        console.warn('Invalid selector:', selector);
        return null;
    }
    try {
        return document.querySelector(selector);
    } catch (e) {
        console.warn('Invalid selector:', selector, e);
        return null;
    }
}

function getCSRFToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content;
}

function handleModalTransition(fromModalId, toModalId, focusElementId) {
  const fromModal = document.getElementById(fromModalId);
  const bootstrapFromModal = bootstrap.Modal.getInstance(fromModal);
  bootstrapFromModal?.hide();

  if (toModalId) {
    const toModal = document.getElementById(toModalId);
    const bootstrapToModal = new bootstrap.Modal(toModal);
    bootstrapToModal.show();
    if (focusElementId) {
      toModal.addEventListener('shown.bs.modal', function () {
        document.getElementById(focusElementId)?.focus();
      });
    }
  }
}

// Add alert dismissal functionality
        document.querySelectorAll('.alert .btn-close').forEach(button => {
            button.addEventListener('click', function() {
                const alertType = this.closest('.alert').dataset.alertType;
                if (alertType) {
                    fetch('/api/dismiss-alert', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCSRFToken()
                        },
                        body: JSON.stringify({ alert_type: alertType })
                    }).catch(console.error);
                }
            });
        });

// Make functions globally available
window.getCSRFToken = getCSRFToken;
window.handleModalTransition = handleModalTransition;