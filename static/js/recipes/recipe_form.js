
// Recipe form handling
document.addEventListener('DOMContentLoaded', function() {
  const recipeForm = document.getElementById('recipeForm');
  
  if (recipeForm) {
    // Container handling
    const requiresContainersCheckbox = document.getElementById('requiresContainers');
    const allowedContainersSection = document.getElementById('allowedContainersSection');

    if (requiresContainersCheckbox && allowedContainersSection) {
      requiresContainersCheckbox.addEventListener('change', function() {
        if (this.checked) {
          allowedContainersSection.style.display = 'block';
        } else {
          allowedContainersSection.style.display = 'none';
        }
      });
    }

    // Form submission handling
    recipeForm.addEventListener('submit', function(e) {
      // Your existing recipe form submission logic
    });
  }
});
