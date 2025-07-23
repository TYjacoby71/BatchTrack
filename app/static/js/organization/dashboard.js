// Organization Dashboard JavaScript
function organizationDashboard() {
    return {
        organizationData: window.organizationData || {},
        currentUserData: window.currentUserData || {},

        init() {
            console.log('Organization dashboard initialized');
        },

        updateOrganizationSettings() {
            const formData = new FormData(document.getElementById('organizationSettingsForm'));
            const data = Object.fromEntries(formData.entries());

            fetch('/organization/update-settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrf_token]').value
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showAlert('Organization settings updated successfully', 'success');
                } else {
                    showAlert(result.error || 'Failed to update settings', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Failed to update settings', 'error');
            });
        }
    };
}

// Role and Permission Management Functions
function selectAllInCategory(category) {
    const checkboxes = document.querySelectorAll(`input[data-category="${category}"]`);
    const selectAllCheckbox = document.querySelector(`#selectAll${category}`);

    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
}

function createRole() {
    const form = document.getElementById('createRoleForm');
    const formData = new FormData(form);

    // Get selected permissions
    const selectedPermissions = [];
    document.querySelectorAll('input[name="permission_ids"]:checked').forEach(checkbox => {
        selectedPermissions.push(checkbox.value);
    });

    const data = {
        name: formData.get('name'),
        description: formData.get('description'),
        permission_ids: selectedPermissions
    };

    fetch('/organization/create-role', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrf_token]').value
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showAlert('Role created successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('createRoleModal')).hide();
            location.reload(); // Refresh to show new role
        } else {
            showAlert(result.error || 'Failed to create role', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Failed to create role', 'error');
    });
}

// User Management Functions
function editUser(userId) {
    fetch(`/organization/user/${userId}`)
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                populateEditUserModal(result.user);
                const modal = new bootstrap.Modal(document.getElementById('editUserModal'));
                modal.show();
            } else {
                showAlert(result.error || 'Failed to load user data', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Failed to load user data', 'error');
        });
}

function populateEditUserModal(user) {
    document.getElementById('editUserId').value = user.id;
    document.getElementById('editUserFirstName').value = user.first_name || '';
    document.getElementById('editUserLastName').value = user.last_name || '';
    document.getElementById('editUserEmail').value = user.email || '';
    document.getElementById('editUserPhone').value = user.phone || '';
    document.getElementById('editUserIsActive').checked = user.is_active;

    // Populate role assignments
    const roleContainer = document.getElementById('editUserRoles');
    roleContainer.innerHTML = '';

    if (user.role_assignments && user.role_assignments.length > 0) {
        user.role_assignments.forEach(assignment => {
            const roleDiv = document.createElement('div');
            roleDiv.className = 'mb-2';
            roleDiv.innerHTML = `
                <span class="badge bg-primary">${assignment.role_name}</span>
                <small class="text-muted ms-2">
                    Assigned: ${assignment.assigned_at ? new Date(assignment.assigned_at).toLocaleDateString() : 'Unknown'}
                </small>
            `;
            roleContainer.appendChild(roleDiv);
        });
    } else {
        roleContainer.innerHTML = '<p class="text-muted">No roles assigned</p>';
    }
}

function updateUser() {
    const form = document.getElementById('editUserForm');
    const formData = new FormData(form);
    const userId = formData.get('user_id');

    const data = {
        first_name: formData.get('first_name'),
        last_name: formData.get('last_name'),
        email: formData.get('email'),
        phone: formData.get('phone'),
        is_active: formData.has('is_active')
    };

    fetch(`/organization/user/${userId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrf_token]').value
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showAlert('User updated successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('editUserModal')).hide();
            location.reload(); // Refresh to show changes
        } else {
            showAlert(result.error || 'Failed to update user', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Failed to update user', 'error');
    });
}

function toggleUserStatus(userId) {
    if (confirm('Are you sure you want to change this user\'s status?')) {
        fetch(`/organization/user/${userId}/toggle-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrf_token]').value
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert(result.message, 'success');
                location.reload();
            } else {
                showAlert(result.error || 'Failed to update user status', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Failed to update user status', 'error');
        });
    }
}

function deleteUser(userId) {
    if (confirm('Are you sure you want to remove this user? This action can be undone later.')) {
        fetch(`/organization/user/${userId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrf_token]').value
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert(result.message, 'success');
                location.reload();
            } else {
                showAlert(result.error || 'Failed to remove user', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Failed to remove user', 'error');
        });
    }
}

// Developer-specific functions (for system roles page)
function deleteDeveloperUser(userId) {
    if (confirm('Are you sure you want to delete this developer user? This action cannot be undone.')) {
        fetch(`/developer/users/${userId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrf_token]').value
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

// Utility Functions
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

function exportReport(reportType) {
    window.location.href = `/organization/export/${reportType}`;
}

function viewAuditLog() {
    showAlert('Audit log functionality coming soon', 'info');
}

function openInviteModal() {
    const modal = new bootstrap.Modal(document.getElementById('inviteUserModal'));
    modal.show();
}

function showCreateRoleModal() {
    const modal = new bootstrap.Modal(document.getElementById('createRoleModal'));
    modal.show();
}

function manageUserRoles(userId) {
    fetch(`/organization/user/${userId}`)
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                populateRoleManagementModal(result.user);
                const modal = new bootstrap.Modal(document.getElementById('manageUserRolesModal'));
                modal.show();
            } else {
                showAlert(result.error || 'Failed to load user data', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Failed to load user data', 'error');
        });
}

function populateRoleManagementModal(user) {
    document.getElementById('roleManageUserId').value = user.id;
    document.getElementById('roleManageUserName').textContent = user.first_name && user.last_name 
        ? `${user.first_name} ${user.last_name}` 
        : user.username;
    document.getElementById('roleManageUserEmail').textContent = user.email || 'No email';
    
    // Show warning if user is organization owner
    const orgOwnerWarning = document.getElementById('orgOwnerWarning');
    if (user.user_type === 'organization_owner') {
        orgOwnerWarning.classList.remove('d-none');
        // Disable all role checkboxes
        document.querySelectorAll('input[name="role_ids"]').forEach(checkbox => {
            checkbox.disabled = true;
        });
        return;
    } else {
        orgOwnerWarning.classList.add('d-none');
        // Enable all role checkboxes
        document.querySelectorAll('input[name="role_ids"]').forEach(checkbox => {
            checkbox.disabled = false;
        });
    }
    
    // Clear all role checkboxes first
    document.querySelectorAll('input[name="role_ids"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Populate current roles
    const currentRolesContainer = document.getElementById('currentUserRoles');
    currentRolesContainer.innerHTML = '';
    
    if (user.role_assignments && user.role_assignments.length > 0) {
        user.role_assignments.forEach(assignment => {
            const roleDiv = document.createElement('div');
            roleDiv.className = 'mb-2';
            roleDiv.innerHTML = `
                <span class="badge bg-primary me-2">${assignment.role_name}</span>
                <small class="text-muted">
                    Assigned: ${assignment.assigned_at ? new Date(assignment.assigned_at).toLocaleDateString() : 'Unknown'}
                </small>
            `;
            currentRolesContainer.appendChild(roleDiv);
            
            // Check the corresponding checkbox
            const checkbox = document.querySelector(`input[name="role_ids"][value="${assignment.role_id}"]`);
            if (checkbox) {
                checkbox.checked = true;
            }
        });
    } else {
        currentRolesContainer.innerHTML = '<p class="text-muted">No roles assigned</p>';
    }
}

function saveUserRoles() {
    const form = document.getElementById('manageUserRolesForm');
    const formData = new FormData(form);
    const userId = formData.get('user_id');
    
    // Get selected role IDs
    const selectedRoles = [];
    document.querySelectorAll('input[name="role_ids"]:checked').forEach(checkbox => {
        selectedRoles.push(parseInt(checkbox.value));
    });
    
    const data = {
        role_ids: selectedRoles
    };
    
    fetch(`/organization/user/${userId}/roles`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrf_token]').value
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showAlert('User roles updated successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('manageUserRolesModal')).hide();
            location.reload();
        } else {
            showAlert(result.error || 'Failed to update user roles', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Failed to update user roles', 'error');
    });
}

function showOwnershipTransferInfo() {
    showAlert('Organization ownership transfer requires contacting support for security verification. This ensures billing continuity and account security.', 'info');
}

// Form submission handlers
document.addEventListener('DOMContentLoaded', function() {
    // Handle invite user form
    const inviteForm = document.getElementById('inviteUserForm');
    if (inviteForm) {
        inviteForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const data = Object.fromEntries(formData.entries());

            fetch('/organization/invite-user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrf_token]').value
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showAlert(result.message, 'success');
                    bootstrap.Modal.getInstance(document.getElementById('inviteUserModal')).hide();
                    this.reset();
                    location.reload();
                } else {
                    showAlert(result.error || 'Failed to invite user', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Failed to invite user', 'error');
            });
        });
    }
});