/*
 * iOS 26 chrome behaviour.
 *
 * Adds the parts of the native feel that CSS alone cannot express:
 *   - the navigation bar gains its material and hairline only once content
 *     scrolls under it, and the large title collapses into a compact one;
 *   - the floating tab bar minimizes while scrolling down and returns on the
 *     way up, the way iOS 26 tab bars behave;
 *   - tab selection fires a selection haptic;
 *   - sheets can be dragged between detents or flicked away, with the
 *     rubber-band resistance UIKit applies past the top stop;
 *   - pulling down at the top of a screen refreshes it, replacing the toolbar
 *     refresh button that no native app carries.
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

  /* -------------------------------------------------------------------------
   * Sheet gestures: drag from the grabber area to move between detents or to
   * dismiss, with the rubber-band resistance UIKit applies past the top stop.
   * ---------------------------------------------------------------------- */

  const GRAB_ZONE = 64; // only the header area starts a drag, so inner scrolling still works
  const DISMISS_DISTANCE = 132;
  const DISMISS_VELOCITY = 0.7; // px per ms
  const RUBBER_BAND = 0.3;

  let drag = null;

  function detentsFor(panel) {
    // A tall sheet gets a medium stop; short ones only open and dismiss.
    const height = panel.getBoundingClientRect().height;
    return height > window.innerHeight * 0.7 ? [0, Math.round(height * 0.45)] : [0];
  }

  function closestDetent(panel, offset) {
    return detentsFor(panel).reduce((best, detent) =>
      Math.abs(detent - offset) < Math.abs(best - offset) ? detent : best,
    );
  }

  function settle(panel, offset) {
    panel.style.transition = `transform var(--motion-spring)`;
    panel.style.transform = offset ? `translateY(${offset}px)` : "";
  }

  function dismiss(panel, sheet) {
    panel.style.transition = `transform var(--motion-soft)`;
    panel.style.transform = `translateY(${panel.getBoundingClientRect().height}px)`;
    try {
      tg?.HapticFeedback?.impactOccurred?.("light");
    } catch {
      // Optional outside Telegram.
    }
    window.setTimeout(() => {
      panel.style.transition = "";
      panel.style.transform = "";
      // The app closes a sheet when its backdrop is clicked; reuse that path
      // instead of duplicating any per-sheet teardown.
      sheet.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }, 200);
  }

  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const panel = event.target.closest?.(".sheet-panel");
      if (!panel) return;
      const sheet = panel.closest(".sheet");
      if (!sheet || sheet.classList.contains("hidden")) return;
      if (event.target.closest("button, input, select, textarea, a")) return;

      const bounds = panel.getBoundingClientRect();
      const base = Number.parseFloat(panel.dataset.sheetOffset || "0") || 0;
      if (event.clientY - bounds.top > GRAB_ZONE) return;

      drag = {
        panel,
        sheet,
        base,
        startY: event.clientY,
        lastY: event.clientY,
        lastAt: event.timeStamp,
        velocity: 0,
      };
      panel.style.transition = "none";
      // The entrance animation is filled forwards, and an animated transform
      // outranks an inline one — drop it so dragging can take over.
      panel.style.animation = "none";
      panel.setPointerCapture?.(event.pointerId);
    },
    { passive: true },
  );

  document.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const raw = drag.base + (event.clientY - drag.startY);
    const offset = raw < 0 ? raw * RUBBER_BAND : raw;
    const elapsed = event.timeStamp - drag.lastAt;
    if (elapsed > 0) {
      drag.velocity = (event.clientY - drag.lastY) / elapsed;
      drag.lastY = event.clientY;
      drag.lastAt = event.timeStamp;
    }
    drag.panel.style.transform = `translateY(${offset}px)`;
  });

  function endDrag(event) {
    if (!drag) return;
    const { panel, sheet } = drag;
    const travelled = drag.base + (event.clientY - drag.startY);
    const flicked = drag.velocity > DISMISS_VELOCITY;
    const current = drag;
    drag = null;

    const detents = detentsFor(panel);
    const deepest = detents[detents.length - 1];

    // A flick only dismisses once the sheet is already at its lowest detent;
    // otherwise it just falls to that detent.
    if (travelled - deepest > DISMISS_DISTANCE || (flicked && travelled >= deepest)) {
      dismiss(panel, sheet);
      return;
    }

    const target = flicked && current.velocity > 0 ? deepest : closestDetent(panel, travelled);
    panel.dataset.sheetOffset = String(target);
    settle(panel, target);
  }

  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);

  // A freshly opened sheet always starts at its largest detent.
  new MutationObserver((records) => {
    for (const record of records) {
      const sheet = record.target;
      if (!sheet.classList?.contains("sheet") || sheet.classList.contains("hidden")) continue;
      const panel = sheet.querySelector(".sheet-panel");
      if (!panel) continue;
      panel.dataset.sheetOffset = "0";
      panel.style.transition = "";
      panel.style.transform = "";
      panel.style.animation = "";
    }
  }).observe(document.body, {
    subtree: true,
    attributes: true,
    attributeFilter: ["class"],
  });

  /* -------------------------------------------------------------------------
   * Pull to refresh. Telegram claims vertical swipes to dismiss the Mini App,
   * so that gesture is released first; the close button in Telegram's own
   * header still dismisses.
   * ---------------------------------------------------------------------- */

  try {
    tg?.disableVerticalSwipes?.();
  } catch {
    // Older Telegram clients simply keep their swipe gesture.
  }

  const PULL_THRESHOLD = 72;
  const PULL_MAX = 140;

  const pullIndicator = document.createElement("div");
  pullIndicator.className = "ptr-indicator";
  pullIndicator.setAttribute("aria-hidden", "true");
  document.body.appendChild(pullIndicator);

  let pull = null;

  function refreshControl() {
    return document.querySelector("#refresh-hero") || document.querySelector("#refresh");
  }

  function resetPull() {
    pull = null;
    pullIndicator.style.transform = "";
    pullIndicator.style.opacity = "";
    pullIndicator.classList.remove("is-active");
  }

  window.addEventListener(
    "touchstart",
    (event) => {
      if (event.touches.length !== 1) return;
      if (body.classList.contains("sheet-open")) return;
      if (currentScroll() > 0) return;
      pull = { startY: event.touches[0].clientY, distance: 0 };
    },
    { passive: true },
  );

  window.addEventListener(
    "touchmove",
    (event) => {
      if (!pull) return;
      const distance = event.touches[0].clientY - pull.startY;
      if (distance <= 0) {
        resetPull();
        return;
      }
      pull.distance = Math.min(distance, PULL_MAX);
      const progress = Math.min(pull.distance / PULL_THRESHOLD, 1);
      pullIndicator.classList.add("is-active");
      pullIndicator.style.opacity = String(progress);
      pullIndicator.style.transform = `translate(-50%, ${pull.distance * 0.45}px) rotate(${progress * 320}deg)`;
    },
    { passive: true },
  );

  window.addEventListener("touchend", () => {
    if (!pull) return;
    const shouldRefresh = pull.distance >= PULL_THRESHOLD;
    resetPull();
    if (!shouldRefresh) return;
    try {
      tg?.HapticFeedback?.impactOccurred?.("medium");
    } catch {
      // Optional outside Telegram.
    }
    pullIndicator.classList.add("is-active", "is-loading");
    refreshControl()?.click();
    window.setTimeout(() => pullIndicator.classList.remove("is-active", "is-loading"), 900);
  });

  applyScrollState();
})();
