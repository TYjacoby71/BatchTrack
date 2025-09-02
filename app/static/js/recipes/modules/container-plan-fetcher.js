
/**
 * Container Plan Fetcher - Handles API calls for container planning
 */
export class ContainerPlanFetcher {
    constructor(containerManager) {
        this.containerManager = containerManager;
        this.fetchingPlan = false;
        this.lastPlanResult = null;
    }

    async fetchContainerPlan() {
        console.log('🔍 CONTAINER PLAN: fetchContainerPlan called');

        if (this.fetchingPlan) {
            console.log('🔍 CONTAINER PLAN: Fetch already in progress, returning cached result');
            return this.lastPlanResult;
        }

        this.fetchingPlan = true;

        if (!window.recipeData?.id) {
            console.error('🚨 CONTAINER PLAN: Recipe data not available');
            this.fetchingPlan = false;
            return null;
        }

        const scale = this.containerManager.getCurrentScale();
        const recipeId = window.recipeData.id;

        try {
            const response = await fetch(`/production-planning/${recipeId}/auto-fill-containers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value || 
                                   document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
                },
                body: JSON.stringify({
                    recipe_id: recipeId,
                    scale: scale
                })
            });

            console.log('🔧 CONTAINER_MANAGEMENT: Response status:', response.status);

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error(`Expected JSON response, got ${contentType}`);
            }

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Failed to fetch container options');
            }

            this.lastPlanResult = result;
            return result;

        } catch (error) {
            console.error('🔧 CONTAINER_MANAGEMENT: Network/parsing error:', error);
            throw error;
        } finally {
            this.fetchingPlan = false;
        }
    }
}
/**
 * Container Plan Fetcher - Data Fetching Only
 * 
 * Handles API calls to fetch container planning data from the backend.
 * Pure data fetching - no business logic or display logic.
 */
export class ContainerPlanFetcher {
    constructor(containerManager) {
        this.containerManager = containerManager;
    }

    async fetchContainerPlan() {
        try {
            const recipeData = window.recipeData;
            if (!recipeData?.id) {
                console.error('🔧 CONTAINER_FETCHER: No recipe data available');
                return null;
            }

            const scale = this.getCurrentScale();
            const payload = {
                recipe_id: recipeData.id,
                scale: scale
            };

            console.log('🔧 CONTAINER_MANAGEMENT: Sending request:', payload);

            const response = await fetch(`/production-planning/${recipeData.id}/auto-fill-containers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value || ''
                },
                body: JSON.stringify(payload)
            });

            console.log('🔧 CONTAINER_MANAGEMENT: Response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const result = await response.json();
            console.log('🔧 CONTAINER_FETCHER: Received data:', result);

            return result;

        } catch (error) {
            console.error('🔧 CONTAINER_FETCHER: Error fetching container plan:', error);
            throw error;
        }
    }

    getCurrentScale() {
        const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }
}
