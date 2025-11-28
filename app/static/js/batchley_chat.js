(() => {
  const root = document.getElementById('batchley-chat');
  if (!root) {
    return;
  }

  const elements = {
    messages: root.querySelector('[data-role="messages"]'),
    emptyState: root.querySelector('[data-role="empty-state"]'),
    form: root.querySelector('[data-role="composer"]'),
    input: root.querySelector('[data-role="input"]'),
    submit: root.querySelector('[data-role="submit"]'),
    spinner: root.querySelector('[data-role="spinner"]'),
    statusText: root.querySelector('[data-role="status-text"]'),
    errorBanner: root.querySelector('[data-role="error-banner"]'),
    windowEnd: root.querySelector('[data-role="window-end"]'),
    insertTemplate: root.querySelector('[data-role="insert-template"]'),
    resetHistory: root.querySelector('[data-role="reset-history"]'),
    actionUsed: root.querySelector('[data-role="actions-used"]'),
    actionLimit: root.querySelector('[data-role="actions-limit"]'),
    actionProgress: root.querySelector('[data-role="actions-progress"]'),
    chatUsed: root.querySelector('[data-role="chat-used"]'),
    chatLimit: root.querySelector('[data-role="chat-limit"]'),
    chatProgress: root.querySelector('[data-role="chat-progress"]'),
    creditsRemaining: root.querySelector('[data-role="credits-remaining"]'),
    creditsExpiration: root.querySelector('[data-role="credits-expiration"]'),
  };

  const endpoints = {
    chat: root.dataset.chatEndpoint,
    usage: root.dataset.usageEndpoint,
  };
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

  const state = {
    history: [],
    quota: parseJson(root.dataset.initialQuota),
  };

  function parseJson(value) {
    try {
      return value ? JSON.parse(value) : {};
    } catch (err) {
      console.warn('Batchley chat: unable to parse JSON payload', err);
      return {};
    }
  }

  function nowLabel(prefix) {
    const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `${prefix} • ${ts}`;
  }

  function appendMessage(role, text, options = {}) {
    if (!elements.messages) {
      return;
    }
    if (elements.emptyState) {
      elements.emptyState.classList.add('d-none');
    }

    const wrapper = document.createElement('div');
    wrapper.className = `batchley-message batchley-message--${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'batchley-message__bubble';
    bubble.textContent = text;
    wrapper.appendChild(bubble);

    const meta = document.createElement('div');
    meta.className = 'batchley-message__meta';
    meta.textContent = options.meta || nowLabel(role === 'user' ? 'You' : 'Batchley');
    wrapper.appendChild(meta);

    if (Array.isArray(options.toolResults) && options.toolResults.length) {
      options.toolResults.forEach((tool) => {
        const toolWrap = document.createElement('div');
        toolWrap.className = 'batchley-tool-result';
        const name = document.createElement('div');
        name.className = 'fw-semibold small';
        name.textContent = tool.name || 'Automation';
        const pre = document.createElement('pre');
        pre.className = 'mb-0 small';
        pre.textContent = JSON.stringify(tool.result ?? {}, null, 2);
        toolWrap.appendChild(name);
        toolWrap.appendChild(pre);
        wrapper.appendChild(toolWrap);
      });
    }

    elements.messages.appendChild(wrapper);
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }

  function setLoading(isLoading) {
    if (elements.submit) {
      elements.submit.disabled = isLoading;
    }
    if (elements.spinner) {
      elements.spinner.classList.toggle('d-none', !isLoading);
    }
    if (elements.statusText) {
      elements.statusText.textContent = isLoading ? 'Batchley is thinking...' : 'Shift+Enter for a new line.';
    }
  }

  function showError(message, options = {}) {
    if (!elements.errorBanner) {
      return;
    }
    elements.errorBanner.classList.remove('d-none');
    elements.errorBanner.innerHTML = message;
    if (options.refillUrl) {
      const link = document.createElement('a');
      link.href = options.refillUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.className = 'ms-2';
      link.textContent = 'Buy more credits';
      elements.errorBanner.appendChild(link);
    }
  }

  function clearError() {
    if (elements.errorBanner) {
      elements.errorBanner.classList.add('d-none');
      elements.errorBanner.textContent = '';
    }
  }

  function formatLimit(value) {
    if (value === undefined || value === null || value === 0 || value === -1) {
      return 'Unlimited';
    }
    return value;
  }

  function applyProgress(bar, used, limit) {
    if (!bar) return;
    if (typeof limit !== 'number' || limit <= 0) {
      bar.style.width = used > 0 ? '20%' : '0%';
      return;
    }
    const pct = Math.min(100, Math.round((used / limit) * 100));
    bar.style.width = `${pct}%`;
  }

  function updateQuota(quota) {
    if (!quota) {
      return;
    }
    state.quota = quota;

    if (elements.windowEnd && quota.window_end) {
      elements.windowEnd.textContent = new Date(quota.window_end).toLocaleString();
    }

    if (elements.actionUsed) {
      elements.actionUsed.textContent = quota.used ?? 0;
    }
    if (elements.actionLimit) {
      elements.actionLimit.textContent = formatLimit(quota.allowed);
    }
    applyProgress(elements.actionProgress, quota.used ?? 0, quota.allowed);

    if (elements.chatUsed) {
      elements.chatUsed.textContent = quota.chat_used ?? 0;
    }
    if (elements.chatLimit) {
      elements.chatLimit.textContent = formatLimit(quota.chat_limit);
    }
    applyProgress(elements.chatProgress, quota.chat_used ?? 0, quota.chat_limit);

    const credits = quota.credits || {};
    if (elements.creditsRemaining) {
      elements.creditsRemaining.textContent =
        credits.remaining !== undefined && credits.remaining !== null ? credits.remaining : '—';
    }
    if (elements.creditsExpiration) {
      elements.creditsExpiration.textContent = credits.next_expiration
        ? new Date(credits.next_expiration).toLocaleDateString()
        : 'None scheduled';
    }
  }

  async function refreshUsage() {
    if (!endpoints.usage) return;
    try {
      const resp = await fetch(endpoints.usage, { headers: { Accept: 'application/json' } });
      if (!resp.ok) return;
      const payload = await resp.json();
      if (payload.success && payload.quota) {
        updateQuota(payload.quota);
      }
    } catch (err) {
      console.warn('Batchley chat: unable to refresh usage', err);
    }
  }

  async function sendPrompt(prompt) {
    if (!endpoints.chat) {
      showError('Missing Batchley endpoint.');
      return;
    }
    setLoading(true);
    clearError();
    try {
      const response = await fetch(endpoints.chat, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
        body: JSON.stringify({
          prompt,
          history: state.history,
          metadata: {},
        }),
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        const errorMessage = payload.error || 'Batchley was unable to process that request.';
        showError(errorMessage, { refillUrl: payload.refill_checkout_url });
        if (payload.quota) {
          updateQuota(payload.quota);
        }
        return;
      }

      appendMessage('assistant', payload.message || 'Done.', { toolResults: payload.tool_results || [] });
      state.history.push({ role: 'user', content: prompt });
      state.history.push({ role: 'assistant', content: payload.message });
      if (payload.quota) {
        updateQuota(payload.quota);
      } else {
        refreshUsage();
      }
    } catch (err) {
      console.error('Batchley chat error', err);
      showError('Unable to reach Batchley. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }

  if (elements.form && elements.input) {
    elements.form.addEventListener('submit', (event) => {
      event.preventDefault();
      const prompt = elements.input.value.trim();
      if (!prompt) {
        elements.input.focus();
        return;
      }
      appendMessage('user', prompt, { meta: nowLabel('You') });
      elements.input.value = '';
      sendPrompt(prompt);
    });

    elements.input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        elements.form.dispatchEvent(new Event('submit'));
      }
    });
  }

  if (elements.insertTemplate && elements.input) {
    elements.insertTemplate.addEventListener('click', () => {
      const template = [
        'Create a bulk inventory adjustment with these lines:',
        '- Restock: 10 kg Cocoa Butter at $8',
        '- Spoil: 3 trays Strawberry Puree',
        'Then summarize low-stock risks this week.',
      ].join('\n');
      elements.input.value = template;
      elements.input.focus();
    });
  }

  if (elements.resetHistory) {
    elements.resetHistory.addEventListener('click', () => {
      state.history = [];
      if (elements.messages) {
        elements.messages.innerHTML = '';
      }
      if (elements.emptyState) {
        elements.emptyState.classList.remove('d-none');
      }
      if (elements.statusText) {
        elements.statusText.textContent = 'Chat history cleared for this session.';
      }
    });
  }

  // Initialize quota display and fetch fresh usage.
  if (state.quota) {
    updateQuota(state.quota);
  }
  refreshUsage();
})();
