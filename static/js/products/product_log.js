
// Product log functionality
function viewProductLog(productId) {
  window.location.href = `/products/${productId}/log`;
}

// Make functions globally available
window.viewProductLog = viewProductLog;
