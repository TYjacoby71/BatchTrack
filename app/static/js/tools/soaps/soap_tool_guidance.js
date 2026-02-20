(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const guidanceSections = new Map();
  let isExpanded = false;

  function normalizeItems(items){
    if (!Array.isArray(items)) return [];
    const seen = new Set();
    const normalized = [];
    items.forEach(item => {
      const text = String(item || '').trim();
      if (!text || seen.has(text)) return;
      seen.add(text);
      normalized.push(text);
    });
    return normalized;
  }

  function getDynamicEntries(){
    return Array.from(guidanceSections.values()).filter(entry => !entry.persistent && entry.items.length);
  }

  function buildSummary(){
    const entries = getDynamicEntries();
    const totalItems = entries.reduce((sum, entry) => sum + entry.items.length, 0);
    if (!totalItems) {
      return { totalItems: 0, text: 'No active formula hints from your current configuration.' };
    }
    if (totalItems === 1) {
      return { totalItems, text: '1 active formula hint from your current configuration.' };
    }
    return { totalItems, text: `${totalItems} active formula hints from your current configuration.` };
  }

  function render(){
    const sectionsEl = document.getElementById('soapGuidanceSections');
    const summaryEl = document.getElementById('soapGuidanceSummary');
    const countEl = document.getElementById('soapGuidanceCount');
    const emptyEl = document.getElementById('soapGuidanceEmpty');
    if (!sectionsEl || !summaryEl || !countEl || !emptyEl) return;

    const summary = buildSummary();
    summaryEl.textContent = summary.text;
    countEl.textContent = String(summary.totalItems);

    const entries = Array.from(guidanceSections.values()).filter(entry => entry.items.length);
    sectionsEl.innerHTML = '';
    entries.forEach(entry => {
      const section = document.createElement('section');
      section.className = `soap-guidance-section ${entry.tone ? `is-${entry.tone}` : ''}`.trim();
      const heading = document.createElement('h6');
      heading.className = 'soap-guidance-section-title';
      heading.textContent = entry.title || 'Guidance';
      const list = document.createElement('ul');
      list.className = 'soap-guidance-list';
      entry.items.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        list.appendChild(li);
      });
      section.appendChild(heading);
      section.appendChild(list);
      sectionsEl.appendChild(section);
    });

    emptyEl.classList.toggle('d-none', entries.length > 0);
  }

  function setSection(key, options = {}){
    if (!key) return;
    const items = normalizeItems(options.items);
    if (!items.length) {
      guidanceSections.delete(key);
      render();
      return;
    }
    guidanceSections.set(key, {
      key,
      title: options.title || 'Guidance',
      tone: options.tone || '',
      persistent: !!options.persistent,
      items,
    });
    render();
  }

  function clearSection(key){
    if (!key) return;
    if (!guidanceSections.has(key)) return;
    guidanceSections.delete(key);
    render();
  }

  function setExpanded(nextExpanded){
    const dock = document.getElementById('soapGuidanceDock');
    const toggle = document.getElementById('soapGuidanceToggle');
    const overlay = document.getElementById('soapGuidanceOverlay');
    if (!dock || !toggle) return;
    isExpanded = !!nextExpanded;
    dock.classList.toggle('is-expanded', isExpanded);
    if (overlay) {
      const isHidden = !isExpanded;
      overlay.setAttribute('aria-hidden', isHidden ? 'true' : 'false');
      if (isHidden) {
        overlay.setAttribute('inert', '');
        if ('inert' in overlay) overlay.inert = true;
        if (overlay.contains(document.activeElement)) {
          toggle.focus();
        }
      } else {
        overlay.removeAttribute('inert');
        if ('inert' in overlay) overlay.inert = false;
      }
    }
    toggle.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
    const label = isExpanded ? 'Collapse guidance panel' : 'Expand guidance panel';
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('title', label);
    const icon = toggle.querySelector('i');
    if (icon) {
      icon.classList.toggle('fa-caret-up', !isExpanded);
      icon.classList.toggle('fa-caret-down', isExpanded);
    }
  }

  function toggleExpanded(force){
    if (typeof force === 'boolean') {
      setExpanded(force);
      return;
    }
    setExpanded(!isExpanded);
  }

  function bindToggle(){
    const toggle = document.getElementById('soapGuidanceToggle');
    if (!toggle || toggle.dataset.bound === 'true') return;
    toggle.dataset.bound = 'true';
    toggle.addEventListener('click', () => toggleExpanded());
  }

  function init(){
    bindToggle();
    setExpanded(false);
    setSection('core-safety', {
      title: 'Safety',
      tone: 'warning',
      persistent: true,
      items: ['Always add lye to water (never water to lye) and wear protective gear.'],
    });
  }

  SoapTool.guidance = {
    init,
    render,
    setSection,
    clearSection,
    setExpanded,
    toggleExpanded,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})(window);
