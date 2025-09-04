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
            const data = await this.container.main.apiCall(`/production-planning/recipe/${this.container.main.recipe.id}/auto-fill-containers`, payload);

            this.fetchingPlan = false;

            if (data.success) {
                containerLogger.debug('Plan successful');
                containerLogger.debug('Container data received:', data);
                this.container.containerPlan = data;
                // Cache result for 60 seconds to reduce server load
                appCache.set(baseKey, data, 60000);
                this.container.displayContainerPlan();
                return data;
            } else {
                // Check for universal drawer payload
                if (data.drawer_payload) {
                    containerLogger.debug('Drawer payload detected from container plan, opening drawer');
                    const retryCallback = (evtDetail) => {
                        const density = evtDetail?.density;
                        containerLogger.debug('Retrying auto-fill with product density', density);
                        return this.fetchContainerPlan({ product_density: density });
                    };
                    window.dispatchEvent(new CustomEvent('openDrawer', {
                        detail: {
                            ...data.drawer_payload,
                            retry_callback: retryCallback
                        }
                    }));
                }
                containerLogger.error('Container plan failed:', data.error);
                this.container.displayContainerError(data.error);
                return null;
            }
        } catch (error) {
            containerLogger.error('Network error while loading containers:', error);
            this.container.displayContainerError('Network error while loading containers');
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