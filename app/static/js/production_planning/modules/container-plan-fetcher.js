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
        const yieldAmount = (this.container.main.recipe.yield_amount || 1) * scale;

        console.log('🔍 CONTAINER PLAN: Fetching for recipe', this.container.main.recipe.id, 'scale:', scale, 'yield:', yieldAmount);

        try {
            const data = await this.container.main.apiCall(`/production-planning/recipe/${this.container.main.recipe.id}/auto-fill-containers`, {
                scale: scale,
                yield_amount: yieldAmount,
                yield_unit: this.container.main.unit
            });

            this.fetchingPlan = false;

            if (data.success) {
                console.log('🔍 CONTAINER PLAN: Plan successful');
                this.container.containerPlan = data;
                this.lastPlanResult = data;
                this.container.displayContainerPlan();
                return data;
            } else {
                console.log('🔍 CONTAINER PLAN: Plan failed:', data.error);
                this.container.displayContainerError(data.error);
                return null;
            }
        } catch (error) {
            console.error('🚨 CONTAINER PLAN: Network error:', error);
            this.container.displayContainerError('Network error while loading containers');
            this.fetchingPlan = false;
            return null;
        }
    }

    clearCache() {
        this.lastPlanResult = null;
        this.fetchingPlan = false;
    }
}