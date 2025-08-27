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
let clockUpdateInProgress = false;

async function updateClock() {
  const clock = document.getElementById('clock');
  if (clock && !clockUpdateInProgress) {
    clockUpdateInProgress = true;
    try {
      // Use cached fetch to prevent duplicate requests
      const response = await cachedFetch('/api/server-time');
      if (response.ok) {
        const data = await response.json();
        const serverTime = new Date(data.user_time || data.server_utc);
        clock.textContent = '🕐 ' + serverTime.toLocaleTimeString();
      } else {
        // Fallback to local time if server endpoint unavailable
        const now = new Date();
        clock.textContent = '🕐 ' + now.toLocaleTimeString();
      }
    } catch (error) {
      // Fallback to local time on error
      const now = new Date();
      clock.textContent = '🕐 ' + now.toLocaleTimeString();
    } finally {
      clockUpdateInProgress = false;
    }
  }
}

document.addEventListener('DOMContentLoaded', function() {
  // Initialize clock - reduce frequency to 5 minutes
  updateClock();
  setInterval(updateClock, 300000);
});