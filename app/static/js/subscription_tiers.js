
// Update tier pricing display after sync
function updateTierPricing(tierKey, tierData) {
    const tierCard = $(`.tier-card[data-tier-key="${tierKey}"]`);
    if (tierCard.length) {
        const pricingDiv = tierCard.find('.tier-pricing');
        const priceDisplay = pricingDiv.find('.price-display');
        const priceInfo = pricingDiv.find('small');
        
        if (tierData.stripe_price) {
            priceDisplay.text(tierData.stripe_price).addClass('text-success');
            priceInfo.html(`From Stripe: ${tierData.stripe_lookup_key || ''}<br>Just synced`);
        } else {
            priceDisplay.text(tierData.fallback_price || '$0').removeClass('text-success');
            priceInfo.text('Sync completed - no pricing found');
        }
    }
}



$(document).ready(function() {
    // Get CSRF token from meta tag or form
    function getCSRFToken() {
        return $('meta[name=csrf-token]').attr('content') || 
               $('input[name="csrf_token"]').val() || 
               document.querySelector('input[name="csrf_token"]')?.value;
    }

    // Add CSRF token to AJAX requests
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", getCSRFToken());
            }
        }
    });

    // Sync tier with Stripe
    $('.sync-tier').on('click', function() {
        const tierKey = $(this).data('tier-key');
        const lookupKey = $(this).data('lookup-key');
        const button = $(this);
        
        button.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Syncing...');
        
        $.ajax({
            url: `/developer/subscription-tiers/sync/${tierKey}`,
            method: 'POST',
            headers: {
                'X-CSRFToken': $('meta[name=csrf-token]').attr('content')
            },
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    // Update pricing display immediately
                    updateTierPricing(tierKey, response.tier);
                    showAlert('success', response.message || 'Sync completed successfully');
                    // Reload page to show updated data
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showAlert('error', response.error || response.message || 'Sync failed');
                }
            },
            error: function(xhr) {
                const response = xhr.responseJSON || {};
                const errorMsg = response.error || response.message || 'Failed to sync with Stripe';
                showAlert('error', errorMsg);
                console.error('Sync error:', xhr);
            },
            complete: function() {
                button.prop('disabled', false).html('<i class="fas fa-sync"></i> Sync with Stripe');
            }
        });
    });
    
    // Sync tier with Whop
    $('.sync-whop-tier').on('click', function() {
        const tierKey = $(this).data('tier-key');
        const productKey = $(this).data('product-key');
        const button = $(this);
        
        button.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Syncing...');
        
        $.ajax({
            url: `/developer/subscription-tiers/sync-whop/${tierKey}`,
            method: 'POST',
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    showAlert('success', response.message);
                } else {
                    showAlert('error', response.error || 'Whop sync failed');
                }
            },
            error: function(xhr) {
                const response = xhr.responseJSON || {};
                showAlert('error', response.error || 'Failed to sync with Whop');
            },
            complete: function() {
                button.prop('disabled', false).html('<i class="fas fa-sync"></i> Sync with Whop');
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
