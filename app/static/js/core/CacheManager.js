class SimpleCache {
    constructor(defaultTtl = 30000) {
        this.cache = new Map();
        this.defaultTtl = defaultTtl;
    }

    get(key) {
        if (this.cache.has(key)) {
            const entry = this.cache.get(key);
            if (Date.now() < entry.expiresAt) {
                return entry.value;
            }
            this.cache.delete(key);
        }
        return null;
    }

    set(key, value, ttl) {
        const expiresAt = Date.now() + (ttl || this.defaultTtl);
        this.cache.set(key, { value, expiresAt });
    }

    delete(key) {
        this.cache.delete(key);
    }

    clear() {
        this.cache.clear();
    }

    clearPrefix(prefix) {
        for (const key of Array.from(this.cache.keys())) {
            if (String(key).startsWith(prefix)) {
                this.cache.delete(key);
            }
        }
    }
}

export const appCache = new SimpleCache();

