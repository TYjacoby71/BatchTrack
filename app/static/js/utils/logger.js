/**
 * Centralized logging utility for frontend
 * Controls debug output based on environment
 */

// Enhanced logging utility with structured formatting
class Logger {
    constructor(context = 'APP') {
        this.context = context;
        // Only enable debug logging if explicitly enabled via URL parameter or localStorage
        this.debugEnabled = this._shouldEnableDebug();
    }

    _shouldEnableDebug() {
        // Check URL parameter first
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('debug') === 'true') {
            return true;
        }

        // Check localStorage for persistent debugging
        if (localStorage.getItem('batchtrack_debug') === 'true') {
            return true;
        }

        // Default: disable debug logging
        return false;
    }

    debug(message, ...args) {
        if (this.debugEnabled) {
            console.log(`🔍 ${this.context}: ${message}`, ...args);
        }
    }

    info(...args) {
        console.info('ℹ️', ...args);
    },

    warn(...args) {
        console.warn('⚠️', ...args);
    },

    error(...args) {
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