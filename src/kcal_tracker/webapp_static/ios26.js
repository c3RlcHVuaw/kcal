/*
 * iOS 26 chrome behaviour.
 *
 * Adds the parts of the native feel that CSS alone cannot express:
 *   - the navigation bar gains its material and hairline only once content
 *     scrolls under it, and the large title collapses into a compact one;
 *   - the floating tab bar minimizes while scrolling down and returns on the
 *     way up, the way iOS 26 tab bars behave;
 *   - tab selection fires a selection haptic.
 *
 * It only toggles classes on <body>, so app.js keeps full ownership of state.
 */

(function () {
  const body = document.body;
  const tg = window.Telegram?.WebApp;

  const SCROLLED_AT = 4;
  const COMPACT_AT = 72;
  const DIRECTION_TOLERANCE = 6;

  let lastY = 0;
  let ticking = false;

  function currentScroll() {
    return Math.max(0, window.scrollY || window.pageYOffset || 0);
  }

  function applyScrollState() {
    const y = currentScroll();
    const delta = y - lastY;

    body.classList.toggle("chrome-scrolled", y > SCROLLED_AT);

    // A sheet owns the screen while it is open; keep the bar expanded under it.
    if (!body.classList.contains("sheet-open")) {
      if (delta > DIRECTION_TOLERANCE && y > COMPACT_AT) {
        body.classList.add("chrome-compact");
      } else if (delta < -DIRECTION_TOLERANCE || y <= COMPACT_AT) {
        body.classList.remove("chrome-compact");
      }
    }

    if (Math.abs(delta) > DIRECTION_TOLERANCE) {
      lastY = y;
    }
    ticking = false;
  }

  function onScroll() {
    if (ticking) return;
    // Frame callbacks are suspended while the webview is hidden, which would
    // otherwise leave the throttle latched and freeze the chrome.
    if (document.hidden) {
      applyScrollState();
      return;
    }
    ticking = true;
    window.requestAnimationFrame(applyScrollState);
  }

  window.addEventListener("scroll", onScroll, { passive: true });

  // Switching a tab restarts the screen at the top with expanded chrome.
  function resetChrome() {
    lastY = 0;
    body.classList.remove("chrome-scrolled", "chrome-compact");
  }

  const viewObserver = new MutationObserver((records) => {
    for (const record of records) {
      if (record.attributeName === "data-view") {
        window.scrollTo({ top: 0, behavior: "auto" });
        resetChrome();
      }
    }
  });
  viewObserver.observe(body, { attributes: true, attributeFilter: ["data-view"] });

  // Selection haptic on tab taps, matching UITabBar.
  document.querySelector(".tab-bar")?.addEventListener("click", (event) => {
    if (!event.target.closest("button")) return;
    try {
      tg?.HapticFeedback?.selectionChanged?.();
    } catch {
      // Haptics are unavailable outside Telegram.
    }
  });

  applyScrollState();
})();
