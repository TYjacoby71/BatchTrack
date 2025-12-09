const STORAGE_PREFIX = 'sessionGuard:draft:';
const DRAFT_TTL_MS = 30 * 60 * 1000; // 30 minutes
const LOGIN_PATH = '/auth/login';
const IS_AUTHENTICATED = typeof window !== 'undefined' && Boolean(window.__IS_AUTHENTICATED__);
let redirectInProgress = false;

function getStorage() {
  try {
    return window.localStorage;
  } catch (error) {
    return null;
  }
}

function cssEscape(value) {
  if (window.CSS && typeof window.CSS.escape === 'function') {
    return window.CSS.escape(value);
  }
  return String(value).replace(/[^a-zA-Z0-9_\-]/g, '\\$&');
}

function getDraftKey() {
  return `${STORAGE_PREFIX}${window.location.pathname}`;
}

function readDraft() {
  try {
    const storage = getStorage();
    if (!storage) return null;
    const raw = storage.getItem(getDraftKey());
    if (!raw) return null;
    const draft = JSON.parse(raw);
    if (!draft || typeof draft !== 'object') return null;
    if (Date.now() - (draft.timestamp || 0) > DRAFT_TTL_MS) {
      storage.removeItem(getDraftKey());
      return null;
    }
    return draft;
  } catch (error) {
    console.warn('SessionGuard: unable to read draft', error);
    return null;
  }
}

function writeDraft(draft) {
  try {
    const storage = getStorage();
    if (!storage) return;
    storage.setItem(getDraftKey(), JSON.stringify(draft));
  } catch (error) {
    console.warn('SessionGuard: unable to persist draft', error);
  }
}

function removeDraft() {
  try {
    const storage = getStorage();
    if (!storage) return;
    storage.removeItem(getDraftKey());
  } catch (error) {
    console.warn('SessionGuard: unable to remove draft', error);
  }
}

function serializeForm(form, formIndex) {
  if (!form || form.dataset.sessionGuard === 'off') {
    return null;
  }

  const fields = [];
  const elements = Array.from(form.elements || []);

  elements.forEach((el) => {
    if (!el || el.disabled) {
      return;
    }

    const tag = (el.tagName || '').toLowerCase();
    const type = (el.type || '').toLowerCase();

    if (!['input', 'select', 'textarea'].includes(tag)) {
      return;
    }

    if (type === 'password' || type === 'hidden' || type === 'file') {
      return;
    }

    const name = el.name || el.id;
    if (!name) {
      return;
    }

    let value;
    if (tag === 'select' && el.multiple) {
      value = Array.from(el.selectedOptions || []).map((opt) => opt.value);
      if (!value.length) {
        return;
      }
    } else if (type === 'checkbox') {
      value = el.checked;
      if (value === el.defaultChecked) {
        return;
      }
    } else if (type === 'radio') {
      if (!el.checked) {
        return;
      }
      value = el.value;
    } else {
      value = el.value;
      const defaultValue = el.defaultValue || '';
      if (!value && !defaultValue) {
        return;
      }
      if (value === defaultValue) {
        return;
      }
    }

    fields.push({
      name,
      type,
      tag,
      value,
      selector: el.id ? `#${cssEscape(el.id)}` : `[name="${cssEscape(el.name || el.id)}"]`
    });
  });

  if (!fields.length) {
    return null;
  }

  return {
    id: form.id || null,
    name: form.getAttribute('name') || null,
    index: formIndex,
    fields
  };
}

function snapshotForms() {
  try {
    const forms = Array.from(document.forms || []);
    const snapshots = [];
    forms.forEach((form, index) => {
      const serialized = serializeForm(form, index);
      if (serialized) {
        snapshots.push(serialized);
      }
    });

    if (!snapshots.length) {
      return null;
    }

    const activeElement = document.activeElement;
    const activeDescriptor = activeElement && activeElement.name
      ? {
          name: activeElement.name,
          id: activeElement.id || null,
          formId: activeElement.form ? activeElement.form.id || null : null,
          formName: activeElement.form ? activeElement.form.getAttribute('name') || null : null
        }
      : null;

    return {
      url: window.location.pathname,
      timestamp: Date.now(),
      forms: snapshots,
      active: activeDescriptor
    };
  } catch (error) {
    console.warn('SessionGuard: unable to snapshot forms', error);
    return null;
  }
}

function findMatchingForm(formDraft) {
  if (!formDraft) return null;

  if (formDraft.id) {
    const byId = document.getElementById(formDraft.id);
    if (byId) {
      return byId;
    }
  }

  if (formDraft.name) {
    const byName = document.querySelector(`form[name="${cssEscape(formDraft.name)}"]`);
    if (byName) {
      return byName;
    }
  }

  const forms = Array.from(document.forms || []);
  if (typeof formDraft.index === 'number' && formDraft.index >= 0 && formDraft.index < forms.length) {
    return forms[formDraft.index];
  }

  return null;
}

function restoreDraft() {
  const draft = readDraft();
  if (!draft || !Array.isArray(draft.forms)) {
    return;
  }

  let restored = false;

  draft.forms.forEach((formDraft) => {
    const form = findMatchingForm(formDraft);
    if (!form) {
      return;
    }

    formDraft.fields.forEach((field) => {
      if (!field || !field.selector) {
        return;
      }

      try {
        if (field.type === 'radio') {
          const radios = form.querySelectorAll(`[name="${cssEscape(field.name)}"]`);
          radios.forEach((radio) => {
            if (radio.value === field.value) {
              radio.checked = true;
            }
          });
          restored = true;
          return;
        }

        const element = form.querySelector(field.selector);
        if (!element) {
          return;
        }

        const tag = (element.tagName || '').toLowerCase();
        const type = (element.type || '').toLowerCase();

        if (tag === 'select' && element.multiple && Array.isArray(field.value)) {
          const values = new Set(field.value.map(String));
          Array.from(element.options).forEach((opt) => {
            opt.selected = values.has(opt.value);
          });
          restored = true;
          return;
        }

        if (type === 'checkbox') {
          element.checked = Boolean(field.value);
          restored = true;
          return;
        }

        if (typeof field.value === 'string') {
          element.value = field.value;
          restored = true;
        }
      } catch (error) {
        console.warn('SessionGuard: unable to restore field', field, error);
      }
    });
  });

  if (restored) {
    removeDraft();

    if (draft.active) {
      let target = null;
      if (draft.active.id) {
        target = document.getElementById(draft.active.id);
      }
      if (!target && draft.active.name) {
        target = document.querySelector(`[name="${cssEscape(draft.active.name)}"]`);
      }
      if (target && typeof target.focus === 'function') {
        target.focus({ preventScroll: false });
      }
    }
  }
}

function buildLoginRedirectUrl() {
  const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const url = new URL(LOGIN_PATH, window.location.origin);
  if (!url.searchParams.has('next')) {
    url.searchParams.set('next', next);
  }
  return url.toString();
}

function triggerSessionExpired(source) {
  if (redirectInProgress) {
    return;
  }
  redirectInProgress = true;

  const draft = snapshotForms();
  if (draft) {
    writeDraft(draft);
  }

  try {
    window.dispatchEvent(new CustomEvent('session-expired', {
      detail: {
        source,
        timestamp: Date.now()
      }
    }));
  } catch (error) {
    console.warn('SessionGuard: unable to dispatch event', error);
  }

  if (window.location.pathname.startsWith(LOGIN_PATH)) {
    window.location.reload();
    return;
  }

  window.location.assign(buildLoginRedirectUrl());
}

function shouldHandleResponseLikeLogin(url) {
  if (!url) {
    return false;
  }

  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.pathname.startsWith(LOGIN_PATH);
  } catch (error) {
    return false;
  }
}

function monitorFetch() {
  if (typeof window.fetch !== 'function') {
    return;
  }

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (...args) => {
    try {
      const response = await originalFetch(...args);

      if (!redirectInProgress) {
        const shouldTrigger = response.status === 401 ||
          response.status === 419 ||
          (response.redirected && shouldHandleResponseLikeLogin(response.url)) ||
          shouldHandleResponseLikeLogin(response.url);

        if (shouldTrigger) {
          triggerSessionExpired('fetch');
        }
      }

      return response;
    } catch (error) {
      throw error;
    }
  };
}

function monitorXHR() {
  const { XMLHttpRequest } = window;
  if (!XMLHttpRequest || !XMLHttpRequest.prototype) {
    return;
  }

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function open(method, url, ...rest) {
    this.__sessionGuardRequestUrl = url;
    return originalOpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function send(body) {
    this.addEventListener('load', function onLoad() {
      if (redirectInProgress) {
        return;
      }

      const status = this.status;
      const responseUrl = this.responseURL || this.__sessionGuardRequestUrl;

      const shouldTrigger = status === 401 ||
        status === 419 ||
        shouldHandleResponseLikeLogin(responseUrl);

      if (shouldTrigger) {
        triggerSessionExpired('xhr');
      }
    });

    this.addEventListener('error', function onError() {
      // Ignore network errors; they are handled elsewhere.
    });

    return originalSend.call(this, body);
  };
}

function cleanupStaleDrafts() {
  try {
    const storage = getStorage();
    if (!storage) {
      return;
    }

    const toRemove = [];
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key && key.startsWith(STORAGE_PREFIX)) {
        const raw = storage.getItem(key);
        if (!raw) {
          toRemove.push(key);
          continue;
        }
        try {
          const draft = JSON.parse(raw);
          if (!draft || Date.now() - (draft.timestamp || 0) > DRAFT_TTL_MS) {
            toRemove.push(key);
          }
        } catch (error) {
          toRemove.push(key);
        }
      }
    }

    toRemove.forEach((key) => storage.removeItem(key));
  } catch (error) {
    console.warn('SessionGuard: unable to cleanup drafts', error);
  }
}

function init() {
  cleanupStaleDrafts();
  restoreDraft();
  monitorFetch();
  monitorXHR();
}

if (IS_AUTHENTICATED) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
} else {
  console.debug('SessionGuard: disabled for anonymous visitor');
}

export default {
  snapshotForms,
  restoreDraft,
  triggerSessionExpired
};
