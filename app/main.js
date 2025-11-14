// Global request cache to prevent duplicate API calls
const requestCache = new Map();
const CACHE_DURATION = 30000; // 30 seconds

// Global API call wrapper with caching and deduplication
async function cachedFetch(url, options = {}) {
  const cacheKey = `${url}_${JSON.stringify(options)}`;
  const now = Date.now();

  // Check cache
  if (requestCache.has(cacheKey)) {
    const cached = requestCache.get(cacheKey);
    if (now - cached.timestamp < CACHE_DURATION) {
      return cached.response.clone();
    }
  }

  // Make request
  const response = await fetch(url, options);

  // Cache response
  requestCache.set(cacheKey, {
    response: response.clone(),
    timestamp: now
  });

  // Clean old cache entries
  for (const [key, value] of requestCache.entries()) {
    if (now - value.timestamp > CACHE_DURATION) {
      requestCache.delete(key);
    }
  }

  return response;
}

// Global flag to prevent multiple simultaneous server-time requests
let serverTimeRequestInProgress = false;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Main.js loaded successfully');
});