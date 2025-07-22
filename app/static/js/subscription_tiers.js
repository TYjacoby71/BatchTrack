
$(document).ready(function() {
    // Sync tier with Stripe
    $('.sync-tier').on('click', function() {
        const tierKey = $(this).data('tier-key');
        const lookupKey = $(this).data('lookup-key');
        const button = $(this);
        
        button.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Syncing...');
        
        $.ajax({
            url: `/developer/subscription-tiers/sync/${tierKey}`,
            method: 'POST',
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    // Update pricing display
                    updateTierDisplay(tierKey, response.tier);
                    showAlert('success', response.message);
                } else {
                    showAlert('error', response.error || 'Sync failed');
                }
            },
            error: function(xhr) {
                const response = xhr.responseJSON || {};
                showAlert('error', response.error || 'Failed to sync with Stripe');
            },
            complete: function() {
                button.prop('disabled', false).html('<i class="fas fa-sync"></i> Sync with Stripe');
            }
        });
    });
    
    // Filter tiers by visibility
    $('#tier-filter').on('change', function() {
        const filterValue = $(this).val();
        $('.tier-card').each(function() {
            const isCustomerFacing = $(this).data('is-customer-facing');
            const isAvailable = $(this).data('is-available');
            
            let show = true;
            if (filterValue === 'customer-facing' && !isCustomerFacing) {
                show = false;
            } else if (filterValue === 'internal' && isCustomerFacing) {
                show = false;
            } else if (filterValue === 'available' && !isAvailable) {
                show = false;
            } else if (filterValue === 'disabled' && isAvailable) {
                show = false;
            }
            
            $(this).toggle(show);
        });
    });
    
    function updateTierDisplay(tierKey, tierData) {
        const tierCard = $(`.tier-card[data-tier-key="${tierKey}"]`);
        
        // Update pricing
        if (tierData.stripe_price_monthly) {
            tierCard.find('.monthly-price').text(tierData.stripe_price_monthly);
        }
        if (tierData.stripe_price_yearly) {
            tierCard.find('.yearly-price').text(tierData.stripe_price_yearly);
        }
        
        // Update features
        if (tierData.stripe_features && tierData.stripe_features.length > 0) {
            const featuresList = tierCard.find('.stripe-features');
            featuresList.empty();
            tierData.stripe_features.forEach(function(feature) {
                featuresList.append(`<li>${feature}</li>`);
            });
        }
        
        // Update last synced
        if (tierData.last_synced) {
            const syncDate = new Date(tierData.last_synced).toLocaleString();
            tierCard.find('.last-synced').text(`Last synced: ${syncDate}`);
        }
    }
    
    function showAlert(type, message) {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const alert = $(`
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);
        
        $('.container-fluid').prepend(alert);
        
        // Auto-dismiss after 5 seconds
        setTimeout(function() {
            alert.alert('close');
        }, 5000);
    }
});
