(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  SoapTool.config = {
    unitOptionsHtml: (window.soapToolConfig && window.soapToolConfig.unitOptionsHtml) || '',
    calcLimit: Number.isFinite(window.SOAP_CALC_LIMIT) ? window.SOAP_CALC_LIMIT : null,
    calcTier: window.SOAP_CALC_TIER || 'guest',
    isAuthenticated: window.__IS_AUTHENTICATED__ === true,
  };

  SoapTool.state = {
    lastCalc: null,
    lastOilEdit: null,
    selectedOilProfile: null,
    wasCapped: false,
    lastPreviewRow: null,
    lastRemovedOil: null,
    lastRemovedOilIndex: null,
    lastSaveToastAt: 0,
    lastRecipePayload: null,
    totalOilsGrams: 0,
    currentUnit: 'g',
  };

  SoapTool.helpers = {
    round,
    toNumber,
    clamp,
    formatTime,
    getStorage,
  };

  function round(value, decimals = 3){
    if (!isFinite(value)) return 0;
    const factor = Math.pow(10, decimals);
    return Math.round(value * factor) / factor;
  }

  function toNumber(value){
    let cleaned = value;
    if (typeof cleaned === 'string') {
      cleaned = cleaned.replace(/,/g, '').trim();
    }
    const num = parseFloat(cleaned);
    return isFinite(num) ? num : 0;
  }

  function clamp(value, min, max){
    if (!isFinite(value)) return min;
    if (value < min) return min;
    if (max !== undefined && max !== null && value > max) return max;
    return value;
  }

  function formatTime(ts){
    if (!ts) return 'Not saved yet';
    const date = new Date(ts);
    return `Saved ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  }

  function getStorage(){
    try {
      return window.localStorage;
    } catch (_) {
      return null;
    }
  }
})(window);
