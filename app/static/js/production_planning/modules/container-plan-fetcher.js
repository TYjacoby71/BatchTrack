// Container Plan Fetcher - Handles API calls for container planning
import { logger } from '../../utils/logger.js';
import { appCache } from '../../core/CacheManager.js';

// Use the imported logger instance with context
const containerLogger = {
    debug: (msg, ...args) => logger.debug(`CONTAINER_PLAN: ${msg}`, ...args),
    info: (msg, ...args) => logger.info(`CONTAINER_PLAN: ${msg}`, ...args),
    warn: (msg, ...args) => logger.warn(`CONTAINER_PLAN: ${msg}`, ...args),
    error: (msg, ...args) => logger.error(`CONTAINER_PLAN: ${msg}`, ...args)
};

export class ContainerPlanFetcher {
    constructor(containerManager) {
        this.container = containerManager;
        this.fetchingPlan = false;
        this.inflightKey = null;
    }

    async fetchContainerPlan(extra = {}) {
        containerLogger.debug('fetchContainerPlan called');

        const recipeId = this.container.main?.recipe?.id;
        const scale = this.container.main?.scale || parseFloat(document.getElementById('scaleInput')?.value) || 1;
        const yieldAmount = (this.container.main?.recipe?.yield_amount || 1) * scale;
        const baseKey = `containerPlan:${recipeId}:${yieldAmount}:${this.container.main?.unit}`;

        // Serve from cache if available
        const cached = appCache.get(baseKey);
        if (cached) {
            containerLogger.debug('Returning cached container plan');
            this.container.containerPlan = cached;
            this.container.displayContainerPlan();
            return cached;
        }

        if (this.fetchingPlan && this.inflightKey === baseKey) {
            containerLogger.debug('Fetch already in progress for same key, returning early');
            return null;
        }

        this.fetchingPlan = true;

        if (!this.container.main.recipe || !this.container.main.recipe.id) {
            containerLogger.error('Recipe data not available');
            this.fetchingPlan = false;
            return null;
        }

        if (!this.container.main.requiresContainers) {
            containerLogger.debug('Recipe does not require containers');
            this.fetchingPlan = false;
            return null;
        }

        containerLogger.debug('Fetching for recipe', this.container.main.recipe.id, 'scale:', scale, 'yield:', yieldAmount);
        this.inflightKey = baseKey;

        try {
            const payload = {
                scale: scale,
                yield_amount: yieldAmount,
                yield_unit: this.container.main.unit,
                ...(extra || {})
            };
            const apiEndpoint = `/production-planning/recipe/${this.container.main.recipe.id}/auto-fill-containers`;
            const data = await this.container.main.apiCall(apiEndpoint, payload);
            containerLogger.debug('Raw container plan response:', data);

            if (data && typeof data === 'object') {
                // Check if this is a drawer response
                if (data.drawer_payload || (data.data && data.data.drawer_payload)) {
                    containerLogger.debug('🔍 FETCHER DEBUG: Received drawer payload in container response:', data);
                    // Let the DrawerInterceptor handle this
                }

                this.container.containerPlan = data;
                this.container.displayContainerPlan();
                this.fetchingPlan = false;
                return data;
            } else {
                containerLogger.error('Invalid container plan format:', data);
                this.container.displayContainerError('Invalid container plan response');
                this.fetchingPlan = false;
                return null;
            }
        } catch (error) {
            containerLogger.error('Container plan failed:', error.message || error);
            this.container.displayContainerError(error.message || 'Container plan failed');
            this.fetchingPlan = false;
            return null;
        }
    }

    clearCache() {
        this.fetchingPlan = false;
        this.inflightKey = null;
        appCache.clearPrefix('containerPlan:');
    }
}