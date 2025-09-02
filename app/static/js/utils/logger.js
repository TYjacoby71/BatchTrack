
/**
 * Centralized logging utility for frontend
 * Controls debug output based on environment
 */

// Check if we're in debug mode (can be controlled via environment or URL param)
const DEBUG_MODE = window.location.hostname.includes('replit.dev') || 
                   new URLSearchParams(window.location.search).has('debug') ||
                   localStorage.getItem('batchtrack_debug') === 'true';

export const logger = {
    debug: (...args) => {
        if (DEBUG_MODE) {
            console.log('🔍', ...args);
        }
    },
    
    info: (...args) => {
        console.info('ℹ️', ...args);
    },
    
    warn: (...args) => {
        console.warn('⚠️', ...args);
    },
    
    error: (...args) => {
        console.error('❌', ...args);
    },
    
    // Special method for performance monitoring (always show)
    perf: (message, startTime) => {
        const duration = performance.now() - startTime;
        console.log(`⏱️ ${message}: ${duration.toFixed(2)}ms`);
    }
};

// Add debug mode indicator
if (DEBUG_MODE) {
    console.log('🔧 DEBUG MODE: Frontend debugging enabled');
}
