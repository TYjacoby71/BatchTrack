
// Utility functions for BatchTrack

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

// Make functions globally available
window.getCSRFToken = getCSRFToken;
window.handleModalTransition = handleModalTransition;
