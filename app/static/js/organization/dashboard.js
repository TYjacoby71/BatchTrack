
// Organization Dashboard JavaScript
function organizationDashboard() {
    return {
        orgSettings: {
            name: '{{ organization.name }}',
            contact_email: '{{ organization.contact_email or current_user.email or "" }}',
            timezone: '{{ organization.timezone or "America/New_York" }}'
        },

        async updateOrgSettings() {
            try {
                const response = await fetch('/organization/update-settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: JSON.stringify(this.orgSettings)
                });

                const result = await response.json();
                if (result.success) {
                    this.showToast('Organization settings updated successfully', 'success');
                } else {
                    this.showToast(result.error || 'Failed to update settings', 'error');
                }
            } catch (error) {
                this.showToast('Error updating settings', 'error');
                console.error('Error:', error);
            }
        },

        showToast(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} position-fixed`;
            toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
            toast.textContent = message;

            document.body.appendChild(toast);
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    };
}

// Global utility functions
function getCSRFToken() {
    const tokenMeta = document.querySelector('meta[name=csrf-token]');
    return tokenMeta ? tokenMeta.getAttribute('content') : '';
}

function showMessage(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    const container = document.querySelector('.container-fluid');
    container.insertBefore(alertDiv, container.firstChild);

    setTimeout(() => {
        if (alertDiv && alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// User management functions
async function inviteUser() {
    const email = document.getElementById('inviteEmail').value;
    const roleId = document.getElementById('inviteRole').value;
    const firstName = document.getElementById('inviteFirstName').value;
    const lastName = document.getElementById('inviteLastName').value;
    const phone = document.getElementById('invitePhone').value;

    if (!email || !roleId || !firstName || !lastName) {
        showMessage('Email, role, first name, and last name are required', 'danger');
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showMessage('Please enter a valid email address', 'danger');
        return;
    }

    const inviteData = {
        email: email,
        role_id: roleId,
        first_name: firstName,
        last_name: lastName,
        phone: phone
    };

    try {
        const response = await fetch('/organization/invite-user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(inviteData)
        });

        const result = await response.json();

        if (result.success) {
            showMessage(result.message || 'User invited successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('inviteUserModal'));
            modal.hide();
            document.getElementById('inviteUserForm').reset();

            if (result.user_data && result.user_data.temp_password) {
                setTimeout(() => {
                    alert(`Login Credentials:\nUsername: ${result.user_data.username}\nPassword: ${result.user_data.temp_password}\n\nPlease share these securely with the new user.`);
                }, 500);
            }

            setTimeout(() => window.location.reload(), 2000);
        } else {
            showMessage(result.error || 'Failed to send invite', 'danger');
        }
    } catch (error) {
        console.error('Invite error:', error);
        showMessage('Failed to send invite', 'danger');
    }
}

async function toggleUserStatus(userId) {
    if (!confirm('Are you sure you want to change this user\'s status?')) {
        return;
    }

    try {
        const response = await fetch(`/organization/user/${userId}/toggle-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        });

        const result = await response.json();

        if (result.success) {
            showMessage(result.message || 'User status updated', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showMessage(result.error || 'Failed to update user status', 'danger');
        }
    } catch (error) {
        console.error('Toggle status error:', error);
        showMessage('Failed to update user status', 'danger');
    }
}

async function editUser(userId) {
    try {
        const response = await fetch(`/organization/user/${userId}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken()
            }
        });

        const result = await response.json();

        if (result.success) {
            const user = result.user;

            document.getElementById('editUserId').value = user.id;
            document.getElementById('editFirstName').value = user.first_name || '';
            document.getElementById('editLastName').value = user.last_name || '';
            document.getElementById('editEmail').value = user.email || '';
            document.getElementById('editPhone').value = user.phone || '';
            
            const userRoles = user.role_assignments || [];
            const activeRole = userRoles.find(assignment => assignment.is_active);
            document.getElementById('editRole').value = activeRole ? activeRole.role_id : '';
            document.getElementById('editStatus').value = user.is_active.toString();

            document.getElementById('editUsername').textContent = user.username;
            document.getElementById('editLastLogin').textContent = user.last_login || 'Never';
            document.getElementById('editCreatedAt').textContent = user.created_at || 'Unknown';

            const modal = new bootstrap.Modal(document.getElementById('editUserModal'));
            modal.show();
        } else {
            showMessage(result.error || 'Failed to load user data', 'danger');
        }
    } catch (error) {
        console.error('Edit user error:', error);
        showMessage('Failed to load user data', 'danger');
    }
}

async function updateUser() {
    const userId = document.getElementById('editUserId').value;
    const userData = {
        first_name: document.getElementById('editFirstName').value,
        last_name: document.getElementById('editLastName').value,
        email: document.getElementById('editEmail').value,
        phone: document.getElementById('editPhone').value,
        role_id: document.getElementById('editRole').value,
        is_active: document.getElementById('editStatus').value === 'true'
    };

    try {
        const response = await fetch(`/organization/user/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(userData)
        });

        const result = await response.json();

        if (result.success) {
            showMessage(result.message || 'User updated successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('editUserModal'));
            modal.hide();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showMessage(result.error || 'Failed to update user', 'danger');
        }
    } catch (error) {
        console.error('Update error:', error);
        showMessage('Failed to update user', 'danger');
    }
}

async function confirmDeleteUser() {
    const userId = document.getElementById('editUserId').value;
    const username = document.getElementById('editUsername').textContent;

    if (!confirm(`Are you sure you want to permanently delete user "${username}"? This action cannot be undone and will remove all associated data.`)) {
        return;
    }

    if (!confirm('This is your final warning. This will permanently delete the user and all their data. Are you absolutely sure?')) {
        return;
    }

    try {
        const response = await fetch(`/organization/user/${userId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCSRFToken()
            }
        });

        const result = await response.json();

        if (result.success) {
            showMessage(result.message || 'User deleted successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('editUserModal'));
            modal.hide();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showMessage(result.error || 'Failed to delete user', 'danger');
        }
    } catch (error) {
        console.error('Delete user error:', error);
        showMessage('Failed to delete user', 'danger');
    }
}

// Role management functions
function openCreateRoleModal() {
    const modal = new bootstrap.Modal(document.getElementById('createRoleModal'));
    modal.show();
}

async function createRole() {
    const roleName = document.getElementById('roleName').value;
    const roleDescription = document.getElementById('roleDescription').value;
    const permissionCheckboxes = document.querySelectorAll('.permission-checkbox:checked');
    const permissionIds = Array.from(permissionCheckboxes).map(cb => cb.value);

    const roleData = {
        name: roleName,
        description: roleDescription,
        permissions: permissionIds
    };

    try {
        const response = await fetch('/organization/create-role', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(roleData)
        });

        const result = await response.json();

        if (result.success) {
            showMessage(result.message || 'Role created successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('createRoleModal'));
            modal.hide();
            document.getElementById('createRoleForm').reset();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showMessage(result.error || 'Failed to create role', 'danger');
        }
    } catch (error) {
        console.error('Create role error:', error);
        showMessage('Failed to create role', 'danger');
    }
}

function toggleCategoryPermissions(category) {
    const categoryCheckbox = document.getElementById(`category_${category}`);
    const permissionCheckboxes = document.querySelectorAll(`.category-${category}`);

    permissionCheckboxes.forEach(cb => {
        cb.checked = categoryCheckbox.checked;
    });
}

function updateCategoryCheckbox(category) {
    const categoryCheckbox = document.getElementById(`category_${category}`);
    const permissionCheckboxes = document.querySelectorAll(`.category-${category}`);
    const checkedPermissions = Array.from(permissionCheckboxes).filter(cb => cb.checked);

    categoryCheckbox.checked = checkedPermissions.length === permissionCheckboxes.length;
}

// Utility functions
function exportReport(type) {
    window.open(`/organization/export/${type}`, '_blank');
}

function editRole(roleId) {
    showMessage('Role editing functionality coming soon', 'info');
}

function deleteRole(roleId) {
    if (!confirm('Are you sure you want to delete this role?')) {
        return;
    }
    showMessage('Role deletion functionality coming soon', 'info');
}

function viewAuditLog() {
    showMessage('Audit log functionality coming soon', 'info');
}

function viewUserActivity(userId) {
    showMessage('User activity view functionality coming soon', 'info');
}

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
