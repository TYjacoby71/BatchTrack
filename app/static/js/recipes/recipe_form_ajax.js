/**
 * AJAX handlers for recipe form to prevent page reload and preserve form state
 */

(function(window) {
    'use strict';

    /**
     * Get CSRF token from meta tag
     */
    function getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        return token ? token.getAttribute('content') : '';
    }

    /**
     * Handle adding ingredient to existing recipe via AJAX
     * This prevents page reload and preserves form state
     */
    window.addIngredientViaAjax = function(recipeId, ingredientData) {
        if (!recipeId) {
            showNotification('Cannot add ingredient to unsaved recipe. Please save the recipe first.', 'warning');
            return Promise.reject('Recipe not saved');
        }

        return fetch(`/api/drawer-actions/recipe/add-ingredient/${recipeId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                ingredient_id: ingredientData.ingredient_id,
                quantity: ingredientData.quantity,
                unit: ingredientData.unit
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Ingredient added successfully', 'success');
                return data;
            } else {
                showNotification(data.error || 'Failed to add ingredient', 'error');
                throw new Error(data.error);
            }
        })
        .catch(error => {
            console.error('Error adding ingredient:', error);
            showNotification('Failed to add ingredient', 'error');
            throw error;
        });
    };

    /**
     * Update ingredient list UI after adding via AJAX
     */
    window.updateIngredientList = function(ingredient) {
        const container = document.getElementById('ingredients-container');
        if (!container) return;

        // Remove empty state if present
        const emptyState = container.querySelector('.text-center.text-muted');
        if (emptyState) {
            emptyState.remove();
        }

        // Find if ingredient already exists in the list
        const existingEntry = Array.from(container.querySelectorAll('.ingredient-entry')).find(entry => {
            const hiddenInput = entry.querySelector('input[name="ingredient_ids[]"]');
            return hiddenInput && parseInt(hiddenInput.value) === ingredient.id;
        });

        if (existingEntry) {
            // Update existing entry
            const amountInput = existingEntry.querySelector('input[name="amounts[]"]');
            const unitSelect = existingEntry.querySelector('select[name="units[]"]');
            const nameInput = existingEntry.querySelector('input.recipe-ingredient-typeahead');
            
            if (amountInput) amountInput.value = ingredient.quantity;
            if (unitSelect) unitSelect.value = ingredient.unit;
            if (nameInput) nameInput.value = ingredient.name;
            
            // Highlight the updated entry
            existingEntry.classList.add('border-success');
            setTimeout(() => existingEntry.classList.remove('border-success'), 2000);
        } else {
            // Entry should already be in DOM from addIngredient() call
            // Just highlight it to confirm save
            const lastEntry = container.querySelector('.ingredient-entry:last-child');
            if (lastEntry) {
                lastEntry.classList.add('border-success');
                setTimeout(() => lastEntry.classList.remove('border-success'), 2000);
            }
        }
    };

    /**
     * Enhanced addIngredient function that preserves the last selected unit
     */
    window.enhanceAddIngredientFunction = function() {
        const originalAddIngredient = window.addIngredient;
        if (!originalAddIngredient) return;

        let lastSelectedUnit = null;

        window.addIngredient = function(preselectId = null, presetUnit = null) {
            const entry = originalAddIngredient(preselectId, presetUnit);
            
            // Preserve last selected unit
            if (lastSelectedUnit && !presetUnit) {
                const unitSelect = entry.querySelector('select[name="units[]"]');
                if (unitSelect) {
                    unitSelect.value = lastSelectedUnit;
                }
            }

            // Track unit changes
            const unitSelect = entry.querySelector('select[name="units[]"]');
            if (unitSelect) {
                unitSelect.addEventListener('change', function() {
                    lastSelectedUnit = this.value;
                });
            }

            return entry;
        };
    };

    /**
     * Add auto-save functionality for recipe form
     * Saves form data to localStorage every 30 seconds
     */
    window.enableRecipeAutoSave = function(formId) {
        const form = document.getElementById(formId);
        if (!form) return;

        const AUTOSAVE_KEY = 'recipe_form_autosave';
        const AUTOSAVE_INTERVAL = 30000; // 30 seconds

        function saveFormData() {
            const formData = new FormData(form);
            const data = {};
            
            // Save basic form fields
            for (let [key, value] of formData.entries()) {
                if (!data[key]) {
                    data[key] = value;
                } else if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            }

            data._timestamp = new Date().toISOString();
            data._url = window.location.pathname;

            try {
                localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(data));
                console.log('Form auto-saved');
                
                // Show save indicator briefly
                const indicator = document.getElementById('autosave-indicator');
                if (indicator) {
                    indicator.innerHTML = '<i class="fas fa-check"></i> Saved';
                    indicator.className = 'badge bg-success';
                    setTimeout(() => {
                        indicator.innerHTML = '<i class="fas fa-clock"></i> Auto-save enabled';
                        indicator.className = 'badge bg-secondary';
                    }, 2000);
                }
            } catch (e) {
                console.error('Failed to auto-save form:', e);
            }
        }

        function restoreFormData() {
            try {
                const saved = localStorage.getItem(AUTOSAVE_KEY);
                if (!saved) return false;

                const data = JSON.parse(saved);
                
                // Only restore if we're on the same URL and it's recent (within 1 hour)
                if (data._url !== window.location.pathname) return false;
                
                const timestamp = new Date(data._timestamp);
                const hourAgo = new Date(Date.now() - 60 * 60 * 1000);
                if (timestamp < hourAgo) {
                    localStorage.removeItem(AUTOSAVE_KEY);
                    return false;
                }

                // Ask user if they want to restore
                if (confirm('Found unsaved changes from ' + timestamp.toLocaleString() + '. Restore?')) {
                    // Restore simple fields
                    for (let [key, value] of Object.entries(data)) {
                        if (key.startsWith('_')) continue;
                        
                        const input = form.querySelector(`[name="${key}"]`);
                        if (input) {
                            if (input.type === 'checkbox') {
                                input.checked = value === 'true' || value === true;
                            } else {
                                input.value = value;
                            }
                        }
                    }
                    
                    showNotification('Form data restored', 'success');
                    return true;
                }
            } catch (e) {
                console.error('Failed to restore form data:', e);
            }
            return false;
        }

        function clearSavedData() {
            localStorage.removeItem(AUTOSAVE_KEY);
        }

        // Restore on page load
        restoreFormData();

        // Auto-save periodically
        const autoSaveTimer = setInterval(saveFormData, AUTOSAVE_INTERVAL);

        // Clear on successful submit
        form.addEventListener('submit', function() {
            clearInterval(autoSaveTimer);
            clearSavedData();
        });

        // Save on page unload
        window.addEventListener('beforeunload', saveFormData);

        // Show auto-save indicator
        const indicator = document.getElementById('autosave-indicator');
        if (indicator) {
            indicator.style.display = 'inline-block';
        }
    };

    /**
     * Initialize AJAX enhancements for recipe form
     */
    window.initRecipeFormAjax = function() {
        // Enhance addIngredient to preserve unit selection
        enhanceAddIngredientFunction();

        // Enable auto-save if recipe form exists
        if (document.getElementById('recipeForm')) {
            enableRecipeAutoSave('recipeForm');
        }

        console.log('Recipe form AJAX enhancements initialized');
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initRecipeFormAjax);
    } else {
        initRecipeFormAjax();
    }

})(window);
