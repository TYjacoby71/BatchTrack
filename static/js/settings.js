
$(document).ready(function() {
    // Handle all settings toggles and inputs
    $('.form-check-input, .form-select, .form-control').on('change', function() {
        const settingId = this.id;
        let settingValue;
        
        if (this.type === 'checkbox') {
            settingValue = this.checked;
        } else if (this.type === 'number') {
            settingValue = parseInt(this.value);
        } else {
            settingValue = this.value;
        }
        
        // Send AJAX request to save setting
        $.ajax({
            url: '/settings/save',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                [settingId.replace(/-/g, '_')]: settingValue
            }),
            success: function(response) {
                if (response.status === 'success') {
                    // Show success feedback
                    showSettingsSaved();
                }
            },
            error: function(xhr, status, error) {
                console.error('Settings save error:', error);
                // Revert the toggle if save failed
                if (this.type === 'checkbox') {
                    this.checked = !this.checked;
                }
            }
        });
    });
    
    function showSettingsSaved() {
        // Create or update success message
        let successMsg = $('#settings-success');
        if (successMsg.length === 0) {
            successMsg = $('<div id="settings-success" class="alert alert-success alert-dismissible fade show position-fixed" style="top: 20px; right: 20px; z-index: 1050;">Settings saved successfully! <button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>');
            $('body').append(successMsg);
        }
        
        // Auto-hide after 3 seconds
        setTimeout(function() {
            successMsg.fadeOut();
        }, 3000);
    }
});
