// Organization Dashboard JavaScript
function organizationDashboard() {
    // Get organization data from the page data
    const orgData = window.organizationData || {};
    const userData = window.currentUserData || {};
    
    return {
        orgSettings: {
            name: orgData.name || (userData.first_name && userData.last_name ? `${userData.first_name} ${userData.last_name}` : userData.username || ''),
            contact_email: orgData.contact_email || userData.email || ''
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

function showLoginCredentials(username, password, statusText) {
    const modalHtml = `
        <div class="modal fade" id="loginCredentialsModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-info text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-key me-2"></i>Login Credentials Created
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            Please share these credentials securely with the new user.
                        </div>
                        <div class="row">
                            <div class="col-sm-3"><strong>Username:</strong></div>
                            <div class="col-sm-9">
                                <code class="bg-light p-1 rounded">${username}</code>
                                <button type="button" class="btn btn-sm btn-outline-secondary ms-2" onclick="navigator.clipboard.writeText('${username}')">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                        </div>
                        <div class="row mt-2">
                            <div class="col-sm-3"><strong>Password:</strong></div>
                            <div class="col-sm-9">
                                <code class="bg-light p-1 rounded">${password}</code>
                                <button type="button" class="btn btn-sm btn-outline-secondary ms-2" onclick="navigator.clipboard.writeText('${password}')">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                        </div>
                        ${statusText ? `<div class="alert alert-info mt-3"><i class="fas fa-info-circle me-2"></i>${statusText}</div>` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Got it</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if present
    const existingModal = document.getElementById('loginCredentialsModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Add new modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('loginCredentialsModal'));
    modal.show();

    // Clean up when modal is closed
    document.getElementById('loginCredentialsModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
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
function openInviteModal() {
    // Check if organization can add more users
    const currentUsers = parseInt(document.querySelector('[data-current-users]')?.dataset.currentUsers || '0');
    const maxUsers = parseInt(document.querySelector('[data-max-users]')?.dataset.maxUsers || '1');
    const subscriptionTier = document.querySelector('[data-subscription-tier]')?.dataset.subscriptionTier || 'solo';

    if (currentUsers >= maxUsers && maxUsers !== Infinity) {
        // Show warning modal about subscription limits
        const warningHtml = `
            <div class="modal fade" id="subscriptionLimitModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-warning text-dark">
                            <h5 class="modal-title">
                                <i class="fas fa-exclamation-triangle me-2"></i>Subscription Limit Reached
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>Your organization has reached the user limit for the <strong>${subscriptionTier}</strong> subscription tier (${currentUsers}/${maxUsers} users).</p>
                            <p>You can still invite new users, but they will be added as <strong>inactive</strong> until you:</p>
                            <ul>
                                <li>Deactivate another user to free up a seat, or</li>
                                <li>Upgrade your subscription tier</li>
                            </ul>
                            <p><strong>Would you like to continue with adding an inactive user?</strong></p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-warning" onclick="proceedWithInactiveUser()">
                                Add Inactive User
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existingModal = document.getElementById('subscriptionLimitModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Add new modal to body
        document.body.insertAdjacentHTML('beforeend', warningHtml);
        const warningModal = new bootstrap.Modal(document.getElementById('subscriptionLimitModal'));
        warningModal.show();
    } else {
        const modal = new bootstrap.Modal(document.getElementById('inviteUserModal'));
        modal.show();
    }
}

function proceedWithInactiveUser() {
    // Close warning modal and open invite modal
    const warningModal = bootstrap.Modal.getInstance(document.getElementById('subscriptionLimitModal'));
    warningModal.hide();

    // Set flag to indicate this will be an inactive user
    document.getElementById('inviteUserModal').dataset.addAsInactive = 'true';

    // Show notice in invite modal
    const noticeHtml = `
        <div class="alert alert-warning border-0 mb-3" id="inactiveUserNotice">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Note:</strong> This user will be added as <strong>inactive</strong> due to subscription limits.
        </div>
    `;

    const modalBody = document.querySelector('#inviteUserModal .modal-body');
    const existingNotice = document.getElementById('inactiveUserNotice');
    if (existingNotice) {
        existingNotice.remove();
    }
    modalBody.insertAdjacentHTML('afterbegin', noticeHtml);

    const modal = new bootstrap.Modal(document.getElementById('inviteUserModal'));
    modal.show();
}

async function inviteUser() {
    const form = document.getElementById('inviteUserForm');
    const formData = new FormData(form);

    const inviteData = {
        email: document.getElementById('inviteEmail').value.trim(),
        first_name: document.getElementById('inviteFirstName').value.trim(),
        last_name: document.getElementById('inviteLastName').value.trim(),
        role_id: document.getElementById('inviteRole').value,
        phone: document.getElementById('invitePhone').value.trim(),
        // Check if this should be added as inactive due to subscription limits
        force_inactive: document.getElementById('inviteUserModal').dataset.addAsInactive === 'true'
    };

    if (!inviteData.email || !inviteData.first_name || !inviteData.last_name || !inviteData.role_id) {
        showMessage('Please fill in all required fields', 'danger');
        return;
    }

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
            let message = result.message || 'User invited successfully';
            if (inviteData.force_inactive) {
                message += ' (User added as inactive due to subscription limits)';
            }
            showMessage(message, 'success');

            const modal = bootstrap.Modal.getInstance(document.getElementById('inviteUserModal'));
            modal.hide();
            document.getElementById('inviteUserForm').reset();

            // Clean up the modal state
            delete document.getElementById('inviteUserModal').dataset.addAsInactive;
            const inactiveNotice = document.getElementById('inactiveUserNotice');
            if (inactiveNotice) {
                inactiveNotice.remove();
            }

            if (result.user_data && result.user_data.temp_password) {
                const statusText = inviteData.force_inactive ? ' (Account is inactive - activate when a seat becomes available)' : '';
                setTimeout(() => {
                    showLoginCredentials(result.user_data.username, result.user_data.temp_password, statusText);
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
    // Show custom confirmation modal instead of native confirm
    showConfirmModal(
        'Confirm Status Change',
        'Are you sure you want to change this user\'s status?',
        async () => {
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
    );
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

    // Show first confirmation modal
    showConfirmModal(
        'Delete User',
        `Are you sure you want to permanently delete user "${username}"? This action cannot be undone and will remove all associated data.`,
        () => {
            // Show second confirmation modal
            showConfirmModal(
                'Final Warning',
                'This is your final warning. This will permanently delete the user and all their data. Are you absolutely sure?',
                async () => {
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
                },
                'danger'
            );
        },
        'warning'
    );
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
    showConfirmModal(
        'Delete Role',
        'Are you sure you want to delete this role?',
        () => {
            showMessage('Role deletion functionality coming soon', 'info');
        }
    );
}

function viewAuditLog() {
    showMessage('Audit log functionality coming soon', 'info');
}

function viewUserActivity(userId) {
    showMessage('User activity view functionality coming soon', 'info');
}

// Custom confirm modal function to replace native confirm dialogs
function showConfirmModal(title, message, onConfirm, variant = 'primary') {
    const modalId = 'customConfirmModal';
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-${variant === 'danger' ? 'danger' : variant === 'warning' ? 'warning' : 'primary'} text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-${variant === 'danger' ? 'exclamation-triangle' : variant === 'warning' ? 'exclamation-triangle' : 'question-circle'} me-2"></i>${title}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-${variant === 'danger' ? 'danger' : variant === 'warning' ? 'warning' : 'primary'}" id="confirmButton">
                            ${variant === 'danger' ? 'Delete' : 'Confirm'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if present
    const existingModal = document.getElementById(modalId);
    if (existingModal) {
        existingModal.remove();
    }

    // Add new modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    
    // Add event listener for confirm button
    document.getElementById('confirmButton').addEventListener('click', () => {
        modal.hide();
        if (onConfirm) {
            onConfirm();
        }
    });

    // Clean up when modal is closed
    document.getElementById(modalId).addEventListener('hidden.bs.modal', function() {
        this.remove();
    });

    modal.show();
}

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});