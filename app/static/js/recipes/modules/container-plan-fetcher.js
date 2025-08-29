// Container Plan Fetcher - Handles API calls for container planning
export class ContainerPlanFetcher {
    constructor(containerManager) {
        this.container = containerManager;
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

        if (!this.container.main.recipe || !this.container.main.recipe.id) {
            console.error('🚨 CONTAINER PLAN: Recipe data not available');
            this.fetchingPlan = false;
            return null;
        }

        if (!this.container.main.requiresContainers) {
            console.log('🔍 CONTAINER PLAN: Recipe does not require containers');
            this.fetchingPlan = false;
            return null;
        }

        const scale = this.container.main.scale || parseFloat(document.getElementById('scaleInput')?.value) || 1;
        const yieldAmount = (this.container.main.recipe.predicted_yield || 1) * scale; // Changed from yield_amount to predicted_yield

        console.log('🔍 CONTAINER PLAN: Fetching for recipe', this.container.main.recipe.id, 'scale:', scale, 'yield:', yieldAmount);

        try {
            const data = await this.container.main.apiCall(`/recipes/${this.container.main.recipe.id}/auto-fill-containers`, {
                scale: scale,
                predicted_yield: this.container.main.recipe.predicted_yield,
                predicted_yield_unit: this.container.main.recipe.predicted_yield_unit
            });

            this.fetchingPlan = false;

            if (data && data.success) {
                console.log('🔍 CONTAINER PLAN: Plan successful');
                this.container.containerPlan = data;
                this.lastPlanResult = data;
                this.container.displayContainerPlan();
                return data;
            } else {
                const errorMsg = data?.error || 'Container planning failed';
                console.log('🔍 CONTAINER PLAN: Plan failed:', errorMsg);
                this.container.displayContainerError(errorMsg);
                return null;
            }
        } catch (error) {
            console.error('🚨 CONTAINER PLAN: Network error:', error);
            let errorMessage = 'Network error while loading containers';

            // Check if it's a specific API error
            if (error.message && error.message.includes('api_format')) {
                errorMessage = 'Container system configuration error - please contact support';
            }

            this.container.displayContainerError(errorMessage);
            this.fetchingPlan = false;
            return null;
        }
    }

    clearCache() {
        this.lastPlanResult = null;
        this.fetchingPlan = false;
    }
}