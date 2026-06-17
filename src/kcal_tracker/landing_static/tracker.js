(() => {
  const endpoint = "/landing/events";
  const visitorKey = "kcal:landing:visitor";
  const sessionKey = "kcal:landing:session";
  const botLinkSelector = 'a[href*="t.me/trackerkcal_bot"]';
  const metrikaCounterId = 109917758;
  const metrikaGoals = {
    view: "landing_view",
    bot_click: "bot_click",
  };

  const randomId = () => {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  };

  const getStoredId = (storage, key) => {
    try {
      let value = storage.getItem(key);
      if (!value) {
        value = randomId();
        storage.setItem(key, value);
      }
      return value;
    } catch {
      return randomId();
    }
  };

  const params = new URLSearchParams(window.location.search);
  const basePayload = () => ({
    path: window.location.pathname || "/",
    hostname: window.location.hostname || null,
    referrer: document.referrer || null,
    utm_source: params.get("utm_source"),
    utm_medium: params.get("utm_medium"),
    utm_campaign: params.get("utm_campaign"),
    utm_content: params.get("utm_content"),
    utm_term: params.get("utm_term"),
    visitor_id: getStoredId(window.localStorage, visitorKey),
    session_id: getStoredId(window.sessionStorage, sessionKey),
  });

  const reachMetrikaGoal = (eventType) => {
    const goal = metrikaGoals[eventType];
    if (!goal || typeof window.ym !== "function") return;
    try {
      window.ym(metrikaCounterId, "reachGoal", goal);
    } catch {
      // Ignore analytics failures; internal tracking must keep working.
    }
  };

  const send = (eventType) => {
    reachMetrikaGoal(eventType);
    const body = JSON.stringify({ ...basePayload(), event_type: eventType });
    const blob = new Blob([body], { type: "application/json" });
    if (navigator.sendBeacon?.(endpoint, blob)) return;
    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  };

  window.addEventListener("load", () => send("view"), { once: true });
  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest?.(botLinkSelector);
      if (link) send("bot_click");
    },
    { capture: true },
  );
})();
