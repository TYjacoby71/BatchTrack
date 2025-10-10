(function(window){
  'use strict';

  const REGISTRY = new Map();
  let mounted = null;

  function normalizeCategoryName(name){
    return (name||'').trim().toLowerCase();
  }

  function hasSkinFor(categoryName){
    const key = normalizeCategoryName(categoryName);
    for (const [pattern] of REGISTRY){
      if (key.includes(pattern)) return true;
    }
    return false;
  }

  function register(pattern, skinFactory){
    REGISTRY.set(normalizeCategoryName(pattern), skinFactory);
  }

  function unmount(){
    if (mounted && mounted.unmount){ try { mounted.unmount(); } catch(_) {} }
    mounted = null;
  }

  function mount(categoryName, hostEl, infoEl){
    unmount();
    const key = normalizeCategoryName(categoryName);
    let factory = null;
    for (const [pattern, f] of REGISTRY){
      if (key.includes(pattern)) { factory = f; break; }
    }
    if (!factory || !hostEl) return;
    mounted = factory();
    if (mounted && mounted.mount){ mounted.mount({ hostEl, infoEl }); }
  }

  window.CategorySkins = { register, hasSkinFor, mount, unmount };
})(window);
