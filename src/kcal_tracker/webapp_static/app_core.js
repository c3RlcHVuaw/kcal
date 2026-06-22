(function () {
  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || "";
  const APP_CACHE_PREFIX = "kcal:cache:v1:";

  function appCacheKey(key) {
    const telegramId = tg?.initDataUnsafe?.user?.id || "anon";
    return `${APP_CACHE_PREFIX}${telegramId}:${key}`;
  }

  function readAppCache(key, ttlMs) {
    try {
      const raw = window.localStorage?.getItem(appCacheKey(key));
      if (!raw) return null;
      const cached = JSON.parse(raw);
      if (!cached || Date.now() - Number(cached.saved_at || 0) > ttlMs) return null;
      return cached.value ?? null;
    } catch {
      return null;
    }
  }

  function writeAppCache(key, value) {
    try {
      window.localStorage?.setItem(appCacheKey(key), JSON.stringify({
        saved_at: Date.now(),
        value,
      }));
    } catch {
      // Cache is optional in Telegram webviews.
    }
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData,
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const message = await response.text();
      const error = new Error(message || `Ошибка ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  async function apiForm(path, form) {
    const response = await fetch(path, {
      method: "POST",
      headers: {
        "X-Telegram-Init-Data": initData,
      },
      body: form,
    });
    if (!response.ok) {
      const message = await response.text();
      const error = new Error(message || `Ошибка ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  async function recordWebappEvent(eventType, payload = {}) {
    if (!initData || !eventType) return;
    try {
      await api("/webapp/me/quality-events", {
        method: "POST",
        body: JSON.stringify({
          event_type: eventType,
          source: payload.source || null,
          query: payload.query || null,
          details: payload.details || {},
        }),
      });
    } catch {
      // Quality events should never block food logging.
    }
  }

  window.KcalAppCore = {
    tg,
    initData,
    readAppCache,
    writeAppCache,
    api,
    apiForm,
    recordWebappEvent,
  };
})();
