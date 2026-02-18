(function() {
  const initialPayload = (
    window.BT_LIST_PREFERENCES && typeof window.BT_LIST_PREFERENCES === 'object'
  ) ? window.BT_LIST_PREFERENCES : {};
  const state = JSON.parse(JSON.stringify(initialPayload));
  const saveTimers = Object.create(null);
  const inFlight = Object.create(null);
  const pending = Object.create(null);
  const SAVE_DEBOUNCE_MS = 250;
  const SCOPE_PATTERN = /^[a-zA-Z0-9:_-]{1,80}$/;

  function isAuthenticatedSession() {
    return Boolean(window.BT_STORAGE && window.BT_STORAGE.userId);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute('content') || '') : '';
  }

  function normalizeScope(scope) {
    const normalized = (scope || '').trim();
    return SCOPE_PATTERN.test(normalized) ? normalized : null;
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function getScopeObject(scope, createIfMissing) {
    const normalizedScope = normalizeScope(scope);
    if (!normalizedScope) {
      return null;
    }
    const current = state[normalizedScope];
    if (!current || typeof current !== 'object' || Array.isArray(current)) {
      if (!createIfMissing) {
        return null;
      }
      state[normalizedScope] = {};
    }
    return state[normalizedScope];
  }

  async function persistScope(scope) {
    const normalizedScope = normalizeScope(scope);
    if (!normalizedScope || !isAuthenticatedSession()) {
      return;
    }
    if (inFlight[normalizedScope]) {
      pending[normalizedScope] = true;
      return;
    }
    inFlight[normalizedScope] = true;
    try {
      const scoped = getScopeObject(normalizedScope, true) || {};
      await fetch(`/settings/api/list-preferences/${encodeURIComponent(normalizedScope)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          mode: 'replace',
          values: scoped,
        }),
      });
    } catch (error) {
      // Keep silent in UI; state remains available locally and will retry on next save.
    } finally {
      inFlight[normalizedScope] = false;
      if (pending[normalizedScope]) {
        pending[normalizedScope] = false;
        persistScope(normalizedScope);
      }
    }
  }

  function schedulePersist(scope) {
    const normalizedScope = normalizeScope(scope);
    if (!normalizedScope || !isAuthenticatedSession()) {
      return;
    }
    if (saveTimers[normalizedScope]) {
      clearTimeout(saveTimers[normalizedScope]);
    }
    saveTimers[normalizedScope] = setTimeout(() => {
      persistScope(normalizedScope);
    }, SAVE_DEBOUNCE_MS);
  }

  window.BT_LIST_PREFS = {
    getScope(scope) {
      const scoped = getScopeObject(scope, false);
      return scoped ? clone(scoped) : {};
    },
    get(scope, key, fallbackValue = null) {
      const scoped = getScopeObject(scope, false);
      if (!scoped || !Object.prototype.hasOwnProperty.call(scoped, key)) {
        return fallbackValue;
      }
      return scoped[key];
    },
    set(scope, key, value) {
      const scoped = getScopeObject(scope, true);
      if (!scoped) return;
      scoped[key] = value;
      schedulePersist(scope);
    },
    replaceScope(scope, values) {
      const normalizedScope = normalizeScope(scope);
      if (!normalizedScope) return;
      const nextValue = (
        values && typeof values === 'object' && !Array.isArray(values)
      ) ? clone(values) : {};
      state[normalizedScope] = nextValue;
      schedulePersist(normalizedScope);
    },
    delete(scope, key) {
      const scoped = getScopeObject(scope, false);
      if (!scoped || !Object.prototype.hasOwnProperty.call(scoped, key)) {
        return;
      }
      delete scoped[key];
      schedulePersist(scope);
    },
    flush(scope) {
      const normalizedScope = normalizeScope(scope);
      if (!normalizedScope) return Promise.resolve();
      return persistScope(normalizedScope);
    },
    all() {
      return clone(state);
    },
  };
})();
