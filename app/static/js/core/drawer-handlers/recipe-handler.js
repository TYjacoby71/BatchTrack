
/**
 * Recipe Error Drawer Handler
 * Handles all recipe-related drawer errors
 */
export class RecipeDrawerHandler {
    constructor(drawerProtocol) {
        this.drawerProtocol = drawerProtocol;
    }

    async handleError(errorCode, errorData) {
        switch (errorCode) {
            case 'MISSING_INGREDIENT':
                return this.handleMissingIngredient(errorData);
            
            case 'SCALING_VALIDATION':
                return this.handleScalingValidation(errorData);
            
            case 'INVALID_YIELD':
                return this.handleInvalidYield(errorData);
            
            default:
                console.warn(`🔧 RECIPE DRAWER: Unhandled error code: ${errorCode}`);
                return false;
        }
    }

    async handleMissingIngredient(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/recipe/missing-ingredient-modal/' + errorData.recipe_id,
            'ingredientAdded'
        );
    }

    async handleScalingValidation(errorData) {
        const params = new URLSearchParams({
            scale: errorData.scale,
            error_details: errorData.error_details
        });
        
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/recipe/scaling-validation-modal/' + errorData.recipe_id + '?' + params,
            'recipeScalingFixed'
        );
    }

    async handleInvalidYield(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/recipe/yield-validation-modal/' + errorData.recipe_id,
            'recipeYieldFixed'
        );
    }
}
