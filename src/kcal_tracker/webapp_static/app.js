const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const state = {
  today: null,
  week: null,
  body: null,
  activeView: "today",
};

const nodes = {
  authWarning: document.querySelector("#auth-warning"),
  refresh: document.querySelector("#refresh"),
  hello: document.querySelector("#hello"),
  screenTitle: document.querySelector("#screen-title"),
  kcalEaten: document.querySelector("#kcal-eaten"),
  kcalBurned: document.querySelector("#kcal-burned"),
  kcalRing: document.querySelector("#kcal-ring"),
  kcalLeft: document.querySelector("#kcal-left"),
  kcalTarget: document.querySelector("#kcal-target"),
  kcalPercent: document.querySelector("#kcal-percent"),
  kcalProgress: document.querySelector("#kcal-progress"),
  protein: document.querySelector("#protein"),
  fat: document.querySelector("#fat"),
  carbs: document.querySelector("#carbs"),
  water: document.querySelector("#water"),
  activityTotal: document.querySelector("#activity-total"),
  entries: document.querySelector("#entries"),
  foodForm: document.querySelector("#food-form"),
  toast: document.querySelector("#toast"),
  weightButton: document.querySelector("#weight-button"),
  weightValue: document.querySelector("#weight-value"),
  weightGoal: document.querySelector("#weight-goal"),
  deleteLatest: document.querySelector("#delete-latest"),
  repeatYesterday: document.querySelector("#repeat-yesterday"),
  frequentList: document.querySelector("#frequent-list"),
  favoritesList: document.querySelector("#favorites-list"),
  weekAverage: document.querySelector("#week-average"),
  weekTarget: document.querySelector("#week-target"),
  weekInTarget: document.querySelector("#week-in-target"),
  weekChart: document.querySelector("#week-chart"),
  goalForm: document.querySelector("#goal-form"),
  goalKind: document.querySelector("#goal-kind"),
  goalWeight: document.querySelector("#goal-weight"),
  goalPace: document.querySelector("#goal-pace"),
  activityForm: document.querySelector("#activity-form"),
  weightTrend: document.querySelector("#weight-trend"),
  weightChart: document.querySelector("#weight-chart"),
  habitList: document.querySelector("#habit-list"),
  aiUsage: document.querySelector("#ai-usage"),
  openBot: document.querySelector("#open-bot"),
  exportFood: document.querySelector("#export-food"),
};

tg?.ready();
tg?.expand();
tg?.setHeaderColor?.("secondary_bg_color");
tg?.setBackgroundColor?.("#f2f2f7");

if (tg?.initDataUnsafe?.user?.first_name) {
  nodes.hello.textContent = `Привет, ${tg.initDataUnsafe.user.first_name}`;
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.querySelectorAll("[data-food-tab]").forEach((button) => {
  button.addEventListener("click", () => switchFoodTab(button.dataset.foodTab));
});

nodes.refresh.addEventListener("click", loadAll);
document.querySelector("#refresh-hero")?.addEventListener("click", loadAll);
document.querySelectorAll("[data-view-shortcut]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.viewShortcut));
});
nodes.deleteLatest.addEventListener("click", deleteLatestEntry);
nodes.repeatYesterday.addEventListener("click", repeatYesterday);
nodes.openBot.addEventListener("click", () => tg?.close());
nodes.exportFood.addEventListener("click", exportFood);

document.querySelectorAll("[data-water]").forEach((button) => {
  button.addEventListener("click", async () => {
    await api("/webapp/me/water", {
      method: "POST",
      body: JSON.stringify({ amount_ml: Number(button.dataset.water) }),
    });
    await loadToday();
    toast("Вода добавлена");
  });
});

nodes.weightButton.addEventListener("click", async () => {
  const value = prompt("Вес в кг");
  const weight = parseNumber(value);
  if (!weight) return;
  await api("/webapp/me/weight", {
    method: "POST",
    body: JSON.stringify({ weight_kg: weight }),
  });
  await Promise.all([loadToday(), loadBody()]);
  toast("Вес сохранён");
});

nodes.foodForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(nodes.foodForm);
  const payload = {
    name: String(form.get("name") || "").trim(),
    kcal: parseNumber(form.get("kcal")),
    weight_g: parseNumber(form.get("weight")),
    protein: parseNumber(form.get("protein")) || 0,
    fat: parseNumber(form.get("fat")) || 0,
    carbs: parseNumber(form.get("carbs")) || 0,
    source: "manual",
  };
  if (!payload.name || payload.kcal === null) {
    toast("Заполни название и калории");
    return;
  }
  await api("/webapp/me/entries", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  nodes.foodForm.reset();
  await Promise.all([loadToday(), loadWeek(), loadFrequent()]);
  switchView("today");
  toast("Еда добавлена");
});

nodes.goalForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    goal: nodes.goalKind.value,
    target_weight_kg: parseNumber(nodes.goalWeight.value),
    weekly_weight_change_kg: parseNumber(nodes.goalPace.value),
  };
  if (payload.goal === "maintain") {
    payload.target_weight_kg = null;
    payload.weekly_weight_change_kg = null;
  }
  await api("/webapp/me/goals/weight", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await Promise.all([loadToday(), loadWeek()]);
  toast("Цель обновлена");
});

nodes.activityForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(nodes.activityForm);
  const payload = {
    name: String(form.get("name") || "").trim(),
    kcal: parseNumber(form.get("kcal")),
  };
  if (!payload.name || payload.kcal === null) {
    toast("Заполни активность и калории");
    return;
  }
  await api("/webapp/me/activity", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  nodes.activityForm.reset();
  await Promise.all([loadToday(), loadWeek()]);
  toast("Активность добавлена");
});

if (!initData) {
  nodes.authWarning.classList.remove("hidden");
  renderEmptyApp();
} else {
  loadAll();
}

window.addEventListener("unhandledrejection", (event) => {
  toast(event.reason?.message || "Что-то пошло не так");
});

async function loadAll() {
  if (!initData) return;
  await Promise.all([
    loadToday(),
    loadWeek(),
    loadBody(),
    loadFrequent(),
    loadFavorites(),
  ]);
}

async function loadToday() {
  state.today = await api("/webapp/me/today");
  renderToday(state.today);
}

async function loadWeek() {
  state.week = await api("/webapp/me/week");
  renderWeek(state.week);
}

async function loadBody() {
  state.body = await api("/webapp/me/body");
  renderBody(state.body);
}

async function loadFrequent() {
  const items = await api("/webapp/me/frequent");
  renderReusableFood(nodes.frequentList, items.map((item) => ({
    id: item.entry.id,
    name: item.entry.name,
    kcal: item.entry.kcal,
    meta: `${item.count} раза`,
    action: () => repeatEntry(item.entry.id),
  })));
}

async function loadFavorites() {
  const items = await api("/webapp/me/favorites");
  renderReusableFood(nodes.favoritesList, items.map((item) => ({
    id: item.id,
    name: item.name,
    kcal: item.kcal,
    meta: item.weight_g ? `${formatNumber(item.weight_g)} г` : "шаблон",
    action: () => addFavorite(item.id),
  })));
}

function renderToday(data) {
  const diary = data.diary;
  const progress = diary.target_kcal > 0 ? Math.min(diary.kcal / diary.target_kcal, 1) : 0;
  nodes.kcalProgress.style.width = `${Math.round(progress * 100)}%`;
  nodes.kcalRing.style.setProperty("--ring-progress", `${Math.round(progress * 100)}%`);
  nodes.kcalPercent.textContent = `${Math.round(progress * 100)}%`;
  const left = Math.round(diary.target_kcal - diary.kcal);
  nodes.kcalEaten.textContent = Math.round(diary.kcal);
  nodes.kcalBurned.textContent = Math.round(diary.activity_kcal);
  nodes.kcalLeft.textContent = left >= 0 ? String(left) : `+${Math.abs(left)}`;
  nodes.kcalTarget.textContent = `${Math.round(diary.kcal)} / ${diary.target_kcal} ккал`;
  nodes.protein.textContent = `${Math.round(diary.protein)}/${Math.round(diary.target_protein)} г`;
  nodes.fat.textContent = `${Math.round(diary.fat)}/${Math.round(diary.target_fat)} г`;
  nodes.carbs.textContent = `${Math.round(diary.carbs)}/${Math.round(diary.target_carbs)} г`;
  nodes.water.textContent = `${data.water_ml} мл воды`;
  nodes.activityTotal.textContent = `${Math.round(diary.activity_kcal)} ккал активности`;
  nodes.weightValue.textContent = data.latest_weight_kg ? `${formatNumber(data.latest_weight_kg)} кг` : "Записать";
  nodes.weightGoal.textContent = data.weight_goal.forecast_text;
  nodes.aiUsage.textContent = data.ai_usage.daily_limit
    ? `${data.ai_usage.used_today} / ${data.ai_usage.daily_limit}`
    : `${data.ai_usage.used_today} / ∞`;
  nodes.goalKind.value = data.weight_goal.goal || "maintain";
  nodes.goalWeight.value = data.weight_goal.target_weight_kg ? formatNumber(data.weight_goal.target_weight_kg) : "";
  nodes.goalPace.value = data.weight_goal.weekly_weight_change_kg ? formatNumber(data.weight_goal.weekly_weight_change_kg) : "";

  if (!diary.entries.length) {
    nodes.entries.innerHTML = '<p class="empty-state">Сегодня пока пусто. Добавь первый приём еды.</p>';
    return;
  }
  nodes.entries.innerHTML = diary.entries.map((entry) => `
    <article class="entry food-card">
      <div class="food-thumb">${escapeHtml(entry.emoji || foodInitial(entry.name))}</div>
      <div class="food-content">
      <div class="entry-main">
        <strong>${escapeHtml(entry.name)}</strong>
        <b>${Math.round(entry.kcal)} ккал</b>
      </div>
      <div class="entry-meta">
        <span>${entry.weight_g ? `${formatNumber(entry.weight_g)} г` : "без граммовки"}</span>
        <span>${Math.round(entry.protein)}Б</span>
        <span>${Math.round(entry.fat)}Ж</span>
        <span>${Math.round(entry.carbs)}У</span>
      </div>
      <div class="entry-actions">
        <button type="button" data-delete-entry="${entry.id}">Удалить</button>
        <button type="button" data-favorite-entry="${entry.id}">В шаблон</button>
      </div>
      </div>
    </article>
  `).join("");

  nodes.entries.querySelectorAll("[data-delete-entry]").forEach((button) => {
    button.addEventListener("click", () => deleteEntry(button.dataset.deleteEntry));
  });
  nodes.entries.querySelectorAll("[data-favorite-entry]").forEach((button) => {
    button.addEventListener("click", () => favoriteEntry(button.dataset.favoriteEntry));
  });
}

function renderWeek(data) {
  nodes.weekAverage.textContent = `${Math.round(data.average_kcal)} ккал`;
  nodes.weekTarget.textContent = `Цель: ${data.target_kcal} ккал`;
  nodes.weekInTarget.textContent = `${data.days_in_target} дней в цели`;
  const max = Math.max(data.target_kcal, ...data.days.map((day) => day.kcal), 1);
  nodes.weekChart.innerHTML = data.days.map((day) => {
    const height = Math.max(5, Math.round((day.kcal / max) * 116));
    const color = day.kcal > data.target_kcal + 150 ? "var(--red)" : day.entries_count ? "var(--accent)" : "rgba(120,120,128,.28)";
    return `
      <div class="week-bar">
        <i style="height:${height}px;background:${color}"></i>
        <span>${escapeHtml(day.date)}</span>
      </div>
    `;
  }).join("");
}

function renderBody(data) {
  nodes.weightTrend.textContent = data.latest_weight_kg
    ? `${formatNumber(data.latest_weight_kg)} кг, ${data.trend_label}`
    : "нет данных";
  if (!data.weight_logs.length) {
    nodes.weightChart.innerHTML = '<p class="empty-state">Запиши вес, чтобы увидеть тренд.</p>';
  } else {
    const weights = data.weight_logs.map((item) => item.weight_kg);
    const min = Math.min(...weights);
    const max = Math.max(...weights);
    const range = Math.max(max - min, 1);
    nodes.weightChart.innerHTML = data.weight_logs.map((item) => {
      const height = Math.round(22 + ((item.weight_kg - min) / range) * 78);
      return `<span class="weight-dot" title="${escapeHtml(item.date)}: ${formatNumber(item.weight_kg)} кг" style="height:${height}px"></span>`;
    }).join("");
  }

  const habits = data.habit_summary;
  nodes.habitList.innerHTML = [
    ["Еда", `${habits.food_streak_days} дней подряд`, `${habits.tracked_food_days_30}/30`],
    ["Вода", `${habits.water_streak_days} дней подряд`, `${habits.tracked_water_days_30}/30`],
    ["Вес", `${habits.weight_streak_days} дней подряд`, `${habits.tracked_weight_days_30}/30`],
  ].map(([title, streak, count]) => `
    <div class="list-item entry-main">
      <strong>${title}</strong>
      <b>${streak}</b>
      <span class="muted">${count}</span>
    </div>
  `).join("");
}

function renderReusableFood(container, items) {
  if (!items.length) {
    container.innerHTML = '<p class="empty-state">Пока пусто.</p>';
    return;
  }
  container.innerHTML = items.map((item) => `
    <button class="list-item" type="button" data-reuse-id="${item.id}">
      <div class="entry-main">
        <strong>${escapeHtml(item.name)}</strong>
        <b>${Math.round(item.kcal)} ккал</b>
      </div>
      <div class="entry-meta"><span>${escapeHtml(item.meta)}</span></div>
    </button>
  `).join("");
  container.querySelectorAll("[data-reuse-id]").forEach((button) => {
    const item = items.find((candidate) => String(candidate.id) === button.dataset.reuseId);
    button.addEventListener("click", item.action);
  });
}

async function repeatEntry(entryId) {
  await api(`/webapp/me/repeat-entry/${entryId}`, { method: "POST" });
  await Promise.all([loadToday(), loadWeek()]);
  switchView("today");
  toast("Добавлено");
}

async function addFavorite(favoriteId) {
  await api(`/webapp/me/favorites/${favoriteId}`, { method: "POST" });
  await Promise.all([loadToday(), loadWeek()]);
  switchView("today");
  toast("Шаблон добавлен");
}

async function repeatYesterday() {
  const entries = await api("/webapp/me/repeat-yesterday", { method: "POST" });
  await Promise.all([loadToday(), loadWeek()]);
  switchView("today");
  toast(entries.length ? "Вчерашний день добавлен" : "Вчера нечего повторять");
}

async function deleteLatestEntry() {
  const result = await api("/webapp/me/entries/latest", { method: "DELETE" });
  await Promise.all([loadToday(), loadWeek(), loadFrequent()]);
  toast(result.deleted ? "Последняя запись удалена" : "Удалять нечего");
}

async function deleteEntry(entryId) {
  await api(`/webapp/me/entries/${entryId}`, { method: "DELETE" });
  await Promise.all([loadToday(), loadWeek(), loadFrequent()]);
  toast("Запись удалена");
}

async function favoriteEntry(entryId) {
  await api(`/webapp/me/entries/${entryId}/favorite`, { method: "POST" });
  await loadFavorites();
  toast("Сохранено в шаблоны");
}

async function exportFood() {
  const response = await fetch("/webapp/me/exports/food.csv", {
    headers: { "X-Telegram-Init-Data": initData },
  });
  if (!response.ok) {
    toast("Не получилось подготовить экспорт");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "kcal_food.csv";
  link.click();
  URL.revokeObjectURL(url);
  toast("Экспорт готов");
}

function switchView(view) {
  state.activeView = view;
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  const active = document.querySelector(`#view-${view}`);
  nodes.screenTitle.textContent = active?.dataset.title || "Kcal";
  document.body.dataset.view = view;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function switchFoodTab(tab) {
  document.querySelectorAll("[data-food-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.foodTab === tab);
  });
  document.querySelectorAll(".food-tab").forEach((section) => {
    section.classList.toggle("active", section.id === `food-tab-${tab}`);
  });
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
    throw new Error(message || `Ошибка ${response.status}`);
  }
  return response.json();
}

function renderEmptyApp() {
  nodes.entries.innerHTML = '<p class="empty-state">Нет данных без Telegram-авторизации.</p>';
  nodes.frequentList.innerHTML = '<p class="empty-state">Открой из Telegram.</p>';
  nodes.favoritesList.innerHTML = '<p class="empty-state">Открой из Telegram.</p>';
  nodes.weekChart.innerHTML = "";
  nodes.weightChart.innerHTML = "";
}

function parseNumber(value) {
  const text = String(value || "").replace(",", ".").trim();
  if (!text) return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value) {
  return Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function foodInitial(value) {
  return String(value || "Е").trim().slice(0, 1).toUpperCase();
}

function toast(message) {
  nodes.toast.textContent = message;
  nodes.toast.classList.remove("hidden");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => nodes.toast.classList.add("hidden"), 2200);
}
