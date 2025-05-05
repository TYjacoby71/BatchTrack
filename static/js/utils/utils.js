
export function getCSRFToken() {
  const token = document.querySelector('input[name="csrf_token"]')?.value;
  if (!token) console.error('CSRF token not found');
  return token;
}

export function handleModalTransition(closeModalId, openModalId, focusElementId = null) {
  const closeModal = bootstrap.Modal.getInstance(document.getElementById(closeModalId));
  if (closeModal) {
    closeModal.hide();
    if (openModalId) {
      setTimeout(() => {
        const openModal = new bootstrap.Modal(document.getElementById(openModalId));
        openModal.show();
        if (focusElementId) document.getElementById(focusElementId)?.focus();
      }, 300);
    }
  }
}
