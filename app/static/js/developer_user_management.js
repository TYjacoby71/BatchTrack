
// Developer User Management JavaScript Functions

function selectAllInCategory(category) {
    const checkboxes = document.querySelectorAll(`input[data-category="${category}"]`);
    const selectAllCheckbox = document.querySelector(`#selectAll${category}`);

    if (selectAllCheckbox && checkboxes.length > 0) {
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
        });
    }
}

function deleteDeveloperUser(userId, username) {
    if (confirm(`Are you sure you want to delete developer user ${username}? This action cannot be undone.`)) {
        fetch(`/developer/users/${userId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name=csrf-token]').getAttribute('content')
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert(result.message || 'User deleted successfully', 'success');
                location.reload();
            } else {
                showAlert(result.error || 'Failed to delete user', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Failed to delete user', 'error');
        });
    }
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    const container = document.querySelector('.container-fluid') || document.body;
    container.insertBefore(alertDiv, container.firstChild);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function getCSRFToken() {
    return document.querySelector('meta[name=csrf-token]').getAttribute('content');
}
