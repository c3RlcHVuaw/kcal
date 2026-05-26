const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const state = {
  today: null,
  week: null,
  body: null,
  activeView: "today",
  selectedMeal: "lunch",
  editingEntryId: null,
  parsedFoods: [],
  parsedFoodSource: "ai",
};

const nodes = {
  authWarning: document.querySelector("#auth-warning"),
  refresh: document.querySelector("#refresh"),
  hello: document.querySelector("#hello"),
  todayHello: document.querySelector("#today-hello"),
  screenTitle: document.querySelector("#screen-title"),
  kcalEaten: document.querySelector("#kcal-eaten"),
  kcalBurned: document.querySelector("#kcal-burned"),
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
  foodTextForm: document.querySelector("#food-text-form"),
  foodText: document.querySelector("#food-text"),
  foodPreview: document.querySelector("#food-preview"),
  foodPreviewSource: document.querySelector("#food-preview-source"),
  foodPreviewList: document.querySelector("#food-preview-list"),
  saveParsedFood: document.querySelector("#save-parsed-food"),
  foodPhotoButton: document.querySelector("#food-photo-button"),
  foodPhotoInput: document.querySelector("#food-photo-input"),
  barcodePhotoButton: document.querySelector("#barcode-photo-button"),
  barcodePhotoInput: document.querySelector("#barcode-photo-input"),
  barcodeCode: document.querySelector("#barcode-code"),
  barcodeCodeButton: document.querySelector("#barcode-code-button"),
  foodForm: document.querySelector("#food-form"),
  foodMeal: document.querySelector("#food-meal"),
  toast: document.querySelector("#toast"),
  weightButton: document.querySelector("#weight-button"),
  weightValue: document.querySelector("#weight-value"),
  weightGoal: document.querySelector("#weight-goal"),
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
  promoForm: document.querySelector("#promo-form"),
  promoCode: document.querySelector("#promo-code"),
  promoStatus: document.querySelector("#promo-status"),
  promoResult: document.querySelector("#promo-result"),
  entryEditor: document.querySelector("#entry-editor"),
  entryEditForm: document.querySelector("#entry-edit-form"),
  entryEditClose: document.querySelector("#entry-edit-close"),
  entryEditName: document.querySelector("#entry-edit-name"),
  entryEditKcal: document.querySelector("#entry-edit-kcal"),
  entryEditWeight: document.querySelector("#entry-edit-weight"),
  entryEditProtein: document.querySelector("#entry-edit-protein"),
  entryEditFat: document.querySelector("#entry-edit-fat"),
  entryEditCarbs: document.querySelector("#entry-edit-carbs"),
  entryEditMeal: document.querySelector("#entry-edit-meal"),
  openBot: document.querySelector("#open-bot"),
  exportFood: document.querySelector("#export-food"),
};

tg?.ready();
tg?.expand();
tg?.setHeaderColor?.("secondary_bg_color");
tg?.setBackgroundColor?.(window.matchMedia("(prefers-color-scheme: dark)").matches ? "#0d1117" : "#f3f6f8");

if (tg?.initDataUnsafe?.user?.first_name) {
  nodes.hello.textContent = `Привет, ${tg.initDataUnsafe.user.first_name}`;
  nodes.todayHello.textContent = `Привет, ${tg.initDataUnsafe.user.first_name}`;
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.querySelectorAll("[data-food-tab]").forEach((button) => {
  button.addEventListener("click", () => switchFoodTab(button.dataset.foodTab));
});

document.querySelectorAll("[data-food-example]").forEach((button) => {
  button.addEventListener("click", () => {
    nodes.foodText.value = button.dataset.foodExample || "";
    nodes.foodText.focus();
  });
});

state.selectedMeal = mealIdForNow();
setSelectedMeal(state.selectedMeal);

document.querySelectorAll("[data-meal]").forEach((button) => {
  button.addEventListener("click", () => setSelectedMeal(button.dataset.meal));
});

nodes.refresh.addEventListener("click", loadAll);
document.querySelector("#refresh-hero")?.addEventListener("click", loadAll);
document.addEventListener("click", (event) => {
  const shortcut = event.target.closest("[data-view-shortcut]");
  if (shortcut) {
    const meal = shortcut.dataset.mealShortcut;
    if (meal) setSelectedMeal(meal);
    switchView(shortcut.dataset.viewShortcut);
    return;
  }
  const deleteButton = event.target.closest("[data-delete-entry]");
  if (deleteButton) {
    deleteEntry(Number(deleteButton.dataset.deleteEntry));
    return;
  }
  const favoriteButton = event.target.closest("[data-favorite-entry]");
  if (favoriteButton) {
    favoriteEntry(Number(favoriteButton.dataset.favoriteEntry));
    return;
  }
  const editButton = event.target.closest("[data-edit-entry]");
  if (editButton) {
    openEntryEditor(Number(editButton.dataset.editEntry));
    return;
  }
  const scaleButton = event.target.closest("[data-scale-parsed]");
  if (scaleButton) {
    scaleParsedFood(Number(scaleButton.dataset.index), Number(scaleButton.dataset.scaleParsed));
  }
});
nodes.repeatYesterday.addEventListener("click", repeatYesterday);
nodes.openBot.addEventListener("click", () => tg?.close());
nodes.exportFood.addEventListener("click", exportFood);
nodes.foodTextForm.addEventListener("submit", parseFoodText);
nodes.saveParsedFood.addEventListener("click", saveParsedFoods);
nodes.foodPreviewList.addEventListener("input", updateParsedFoodField);
nodes.foodPreviewList.addEventListener("click", removeParsedFood);
nodes.foodPhotoButton.addEventListener("click", () => nodes.foodPhotoInput.click());
nodes.foodPhotoInput.addEventListener("change", parseFoodPhoto);
nodes.barcodePhotoButton.addEventListener("click", () => nodes.barcodePhotoInput.click());
nodes.barcodePhotoInput.addEventListener("change", scanBarcodePhoto);
nodes.barcodeCodeButton.addEventListener("click", lookupBarcodeCode);
nodes.barcodeCode.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    lookupBarcodeCode();
  }
});
nodes.entryEditClose.addEventListener("click", closeEntryEditor);
nodes.entryEditor.addEventListener("click", (event) => {
  if (event.target === nodes.entryEditor) closeEntryEditor();
});

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

async function parseFoodText(event) {
  event.preventDefault();
  const text = nodes.foodText.value.trim();
  if (text.length < 3) {
    toast("Опиши еду чуть подробнее");
    return;
  }

  const submit = nodes.foodTextForm.querySelector("button[type='submit']");
  setButtonBusy(submit, "Разбираю...");
  try {
    const result = await api("/webapp/me/food/parse-text", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    setParsedFoods(result);
    toast(result.ai_used ? "AI разобрал еду" : "Нашёл похожее");
  } catch (error) {
    const message = error.status === 402
      ? "Лимит AI на сегодня закончился"
      : "Не получилось разобрать еду";
    toast(message);
  } finally {
    restoreButton(submit);
  }
}

async function parseFoodPhoto() {
  const file = nodes.foodPhotoInput.files?.[0];
  if (!file) return;
  const hint = nodes.foodText.value.trim();
  const form = new FormData();
  form.append("image", file);
  if (hint) form.append("text_hint", hint);

  setButtonBusy(nodes.foodPhotoButton, "Распознаю...");
  try {
    const result = await apiForm("/webapp/me/food/parse-photo", form);
    setParsedFoods(result);
    toast("Фото распознано");
  } catch (error) {
    const message = error.status === 402
      ? "Лимит AI на сегодня закончился"
      : "Не получилось распознать фото";
    toast(message);
  } finally {
    nodes.foodPhotoInput.value = "";
    restoreButton(nodes.foodPhotoButton);
  }
}

async function scanBarcodePhoto() {
  const file = nodes.barcodePhotoInput.files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append("image", file);

  setButtonBusy(nodes.barcodePhotoButton, "Сканирую...");
  try {
    const result = await apiForm("/webapp/me/food/scan-barcode", form);
    setParsedFoods(result);
    if (result.barcode) nodes.barcodeCode.value = result.barcode;
    toast("Штрихкод найден");
  } catch (error) {
    const message = error.status === 404
      ? "Продукта нет в базе"
      : "Штрихкод не считался";
    toast(message);
  } finally {
    nodes.barcodePhotoInput.value = "";
    restoreButton(nodes.barcodePhotoButton);
  }
}

async function lookupBarcodeCode() {
  const code = nodes.barcodeCode.value.trim();
  if (code.length < 8) {
    toast("Введи цифры штрихкода");
    return;
  }
  setButtonBusy(nodes.barcodeCodeButton, "Ищу...");
  try {
    const result = await api("/webapp/me/food/barcode", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    setParsedFoods(result);
    if (result.barcode) nodes.barcodeCode.value = result.barcode;
    toast("Продукт найден");
  } catch (error) {
    const message = error.status === 404
      ? "Продукта нет в базе"
      : "Штрихкод не подходит";
    toast(message);
  } finally {
    restoreButton(nodes.barcodeCodeButton);
  }
}

function setParsedFoods(result) {
  state.parsedFoods = result.foods.map(normalizeParsedFood);
  state.parsedFoodSource = result.source;
  renderParsedFoods(result);
}

async function saveParsedFoods() {
  const foods = state.parsedFoods.filter((food) => food.name && food.kcal !== null);
  if (!foods.length) {
    toast("Нет позиций для сохранения");
    return;
  }

  setButtonBusy(nodes.saveParsedFood, "Сохраняю...");
  try {
    for (const food of foods) {
      await api("/webapp/me/entries", {
        method: "POST",
        body: JSON.stringify({
          ...food,
          protein: food.protein ?? 0,
          fat: food.fat ?? 0,
          carbs: food.carbs ?? 0,
          source: entrySourceForParsed(state.parsedFoodSource),
          meal_type: state.selectedMeal,
        }),
      });
    }
    state.parsedFoods = [];
    nodes.foodTextForm.reset();
    nodes.barcodeCode.value = "";
    nodes.foodPreview.classList.add("hidden");
    await Promise.all([loadToday(), loadWeek(), loadFrequent()]);
    switchView("today");
    toast(foods.length === 1 ? "Еда добавлена" : `Добавлено позиций: ${foods.length}`);
  } finally {
    restoreButton(nodes.saveParsedFood);
  }
}

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
    meal_type: String(form.get("meal_type") || state.selectedMeal),
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

nodes.promoForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = nodes.promoCode.value.trim();
  if (!code) {
    toast("Введи промокод");
    return;
  }
  const button = nodes.promoForm.querySelector("button[type='submit']");
  setButtonBusy(button, "Проверяю...");
  try {
    const result = await api("/webapp/me/promos/validate", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    renderPromo(result);
  } finally {
    restoreButton(button);
  }
});

nodes.entryEditForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.editingEntryId) return;
  const form = new FormData(nodes.entryEditForm);
  const payload = {
    name: String(form.get("name") || "").trim(),
    kcal: parseNumber(form.get("kcal")),
    weight_g: parseNumber(form.get("weight_g")),
    protein: parseNumber(form.get("protein")) || 0,
    fat: parseNumber(form.get("fat")) || 0,
    carbs: parseNumber(form.get("carbs")) || 0,
    meal_type: String(form.get("meal_type") || mealIdForNow()),
  };
  if (!payload.name || payload.kcal === null) {
    toast("Заполни название и калории");
    return;
  }
  const button = nodes.entryEditForm.querySelector("button[type='submit']");
  setButtonBusy(button, "Сохраняю...");
  try {
    await api(`/webapp/me/entries/${state.editingEntryId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    closeEntryEditor();
    await Promise.all([loadToday(), loadWeek(), loadFrequent(), loadFavorites()]);
    toast("Запись обновлена");
  } finally {
    restoreButton(button);
  }
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

  nodes.entries.innerHTML = renderMealDiary(diary.entries);
}

function renderMealDiary(entries) {
  const meals = [
    { id: "breakfast", title: "Завтрак", hint: "до 11:00", items: [] },
    { id: "lunch", title: "Обед", hint: "11:00-16:00", items: [] },
    { id: "dinner", title: "Ужин", hint: "16:00-21:00", items: [] },
    { id: "snack", title: "Перекус", hint: "после 21:00", items: [] },
  ];
  const byId = Object.fromEntries(meals.map((meal) => [meal.id, meal]));

  entries.forEach((entry) => byId[mealIdForEntry(entry)].items.push(entry));

  return meals.map((meal) => {
    const kcal = meal.items.reduce((total, entry) => total + Number(entry.kcal || 0), 0);
    const content = meal.items.length
      ? meal.items.map(renderFoodEntry).join("")
      : `
        <button class="meal-empty" type="button" data-view-shortcut="food" data-meal-shortcut="${meal.id}">
          <span>Пока нет записей</span>
          <b aria-hidden="true"><svg><use href="#icon-plus"></use></svg></b>
        </button>
      `;
    return `
      <section class="meal-section">
        <div class="meal-header">
          <div>
            <strong>${meal.title}</strong>
            <span>${meal.hint}</span>
          </div>
          <button class="meal-add" type="button" data-view-shortcut="food" data-meal-shortcut="${meal.id}" aria-label="Добавить в ${meal.title}">
            <span>${Math.round(kcal)} ккал</span>
            <svg><use href="#icon-plus"></use></svg>
          </button>
        </div>
        <div class="meal-items">${content}</div>
      </section>
    `;
  }).join("");
}

function renderFoodEntry(entry) {
  return `
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
          <button type="button" data-edit-entry="${entry.id}">Изменить</button>
          <button type="button" data-favorite-entry="${entry.id}">В шаблон</button>
          <button type="button" data-delete-entry="${entry.id}">Удалить</button>
        </div>
      </div>
    </article>
  `;
}

function mealIdForEntry(entry) {
  if (["breakfast", "lunch", "dinner", "snack"].includes(entry.meal_type)) {
    return entry.meal_type;
  }
  const hour = entry.created_at ? new Date(entry.created_at).getHours() : 12;
  if (hour < 11) return "breakfast";
  if (hour < 16) return "lunch";
  if (hour < 21) return "dinner";
  return "snack";
}

function mealIdForNow() {
  const hour = new Date().getHours();
  if (hour < 11) return "breakfast";
  if (hour < 16) return "lunch";
  if (hour < 21) return "dinner";
  return "snack";
}

function renderWeek(data) {
  nodes.weekAverage.textContent = `${Math.round(data.average_kcal)} ккал`;
  nodes.weekTarget.textContent = `Цель: ${data.target_kcal} ккал`;
  nodes.weekInTarget.textContent = `${data.days_in_target} дней в цели`;
  const max = Math.max(data.target_kcal, ...data.days.map((day) => day.kcal), 1);
  nodes.weekChart.innerHTML = data.days.map((day) => {
    const height = Math.max(5, Math.round((day.kcal / max) * 116));
    const color = day.kcal > data.target_kcal + 150 ? "var(--danger)" : day.entries_count ? "var(--accent)" : "rgba(120,120,128,.28)";
    return `
      <div class="week-bar">
        <strong>${day.entries_count ? Math.round(day.kcal) : ""}</strong>
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
    nodes.weightChart.innerHTML = '<div class="empty-state">Запиши вес, чтобы увидеть тренд.</div>';
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
    <div class="list-item habit-row">
      <div class="list-content">
        <div class="entry-main">
          <strong>${title}</strong>
          <b>${count}</b>
        </div>
        <div class="entry-meta"><span>${streak}</span></div>
      </div>
    </div>
  `).join("");
}

function renderPromo(result) {
  nodes.promoResult.classList.remove("hidden");
  if (!result.valid) {
    nodes.promoStatus.textContent = "Промокод не найден или уже закончился";
    nodes.promoResult.innerHTML = "";
    toast("Промокод не применился");
    return;
  }

  nodes.promoStatus.textContent = `${result.code}: скидка ${result.discount_percent}%`;
  nodes.promoResult.innerHTML = result.plans.map((plan) => {
    const limit = plan.daily_limit ? `${plan.daily_limit} AI/день` : "без дневного лимита";
    return `
      <div class="promo-plan">
        <div>
          <strong>${escapeHtml(plan.title)}</strong>
          <span>${escapeHtml(limit)}</span>
        </div>
        <b>${plan.rub} ₽ / ${plan.stars} ⭐</b>
      </div>
    `;
  }).join("");
  toast("Промокод применён");
}

function renderReusableFood(container, items) {
  if (!items.length) {
    container.innerHTML = '<div class="empty-state">Пока пусто.</div>';
    return;
  }
  container.innerHTML = items.map((item) => `
    <button class="list-item" type="button" data-reuse-id="${item.id}">
      <div class="list-content">
        <div class="entry-main">
          <strong>${escapeHtml(item.name)}</strong>
          <b>${Math.round(item.kcal)} ккал</b>
        </div>
      <div class="entry-meta"><span>${escapeHtml(item.meta)}</span></div>
      </div>
      <span class="row-action" aria-hidden="true"><svg><use href="#icon-plus"></use></svg></span>
    </button>
  `).join("");
  container.querySelectorAll("[data-reuse-id]").forEach((button) => {
    const item = items.find((candidate) => String(candidate.id) === button.dataset.reuseId);
    button.addEventListener("click", item.action);
  });
}

function renderParsedFoods(result) {
  const sourceText = {
    ai: "AI-оценка. Проверь граммы и калории перед сохранением.",
    photo: "Распознано по фото. Проверь состав, граммы и БЖУ.",
    barcode: "Продукт найден по штрихкоду. Значения указаны на 100 г.",
    common: "Оценка из базовых продуктов. Можно поправить значения.",
    history: "Похоже на то, что ты уже добавлял раньше.",
  };
  nodes.foodPreviewSource.textContent = sourceText[result.source] || "Можно поправить значения";
  nodes.foodPreview.classList.toggle("hidden", !state.parsedFoods.length);
  nodes.foodPreviewList.innerHTML = state.parsedFoods.map((food, index) => `
    <article class="parsed-food-card" data-index="${index}">
      <div class="parsed-food-head preview-head">
        <div class="food-thumb small">${escapeHtml(food.emoji || foodInitial(food.name))}</div>
        <div class="preview-title">
          <input data-field="name" value="${escapeHtml(food.name)}" aria-label="Название" />
          <span>${mealLabel(state.selectedMeal)} · ${sourceLabel(result.source)}</span>
        </div>
        <button class="icon-mini" type="button" data-remove-parsed="${index}" aria-label="Удалить">×</button>
      </div>
      <div class="preview-summary">
        <strong>${Math.round(food.kcal || 0)} ккал</strong>
        <span>${food.weight_g ? `${formatNumber(food.weight_g)} г` : "граммы не указаны"}</span>
      </div>
      <div class="field-row compact-fields">
        <label><span>ккал</span><input data-field="kcal" inputmode="decimal" value="${formatInput(food.kcal)}" /></label>
        <label><span>граммы</span><input data-field="weight_g" inputmode="decimal" value="${formatInput(food.weight_g)}" /></label>
      </div>
      <div class="field-row three compact-fields">
        <label><span>Б</span><input data-field="protein" inputmode="decimal" value="${formatInput(food.protein)}" /></label>
        <label><span>Ж</span><input data-field="fat" inputmode="decimal" value="${formatInput(food.fat)}" /></label>
        <label><span>У</span><input data-field="carbs" inputmode="decimal" value="${formatInput(food.carbs)}" /></label>
      </div>
      <div class="portion-actions">
        <button type="button" data-index="${index}" data-scale-parsed="0.5">1/2</button>
        <button type="button" data-index="${index}" data-scale-parsed="1.25">+ порция</button>
        <button type="button" data-index="${index}" data-scale-parsed="2">x2</button>
      </div>
    </article>
  `).join("");
}

function setSelectedMeal(meal) {
  if (!["breakfast", "lunch", "dinner", "snack"].includes(meal)) return;
  state.selectedMeal = meal;
  document.querySelectorAll("[data-meal]").forEach((button) => {
    button.classList.toggle("active", button.dataset.meal === meal);
  });
  if (nodes.foodMeal) nodes.foodMeal.value = meal;
}

function openEntryEditor(entryId) {
  const entry = state.today?.diary?.entries?.find((item) => Number(item.id) === entryId);
  if (!entry) {
    toast("Запись не найдена");
    return;
  }
  state.editingEntryId = entryId;
  nodes.entryEditName.value = entry.name || "";
  nodes.entryEditKcal.value = formatInput(entry.kcal);
  nodes.entryEditWeight.value = formatInput(entry.weight_g);
  nodes.entryEditProtein.value = formatInput(entry.protein);
  nodes.entryEditFat.value = formatInput(entry.fat);
  nodes.entryEditCarbs.value = formatInput(entry.carbs);
  nodes.entryEditMeal.value = mealIdForEntry(entry);
  nodes.entryEditor.classList.remove("hidden");
  nodes.entryEditName.focus();
}

function closeEntryEditor() {
  state.editingEntryId = null;
  nodes.entryEditor.classList.add("hidden");
  nodes.entryEditForm.reset();
}

function scaleParsedFood(index, multiplier) {
  const food = state.parsedFoods[index];
  if (!food || !Number.isFinite(multiplier) || multiplier <= 0) return;
  ["weight_g", "kcal", "protein", "fat", "carbs"].forEach((field) => {
    if (food[field] === null || food[field] === undefined) return;
    food[field] = Math.max(0, Math.round(Number(food[field]) * multiplier * 10) / 10);
  });
  renderParsedFoods({ source: state.parsedFoodSource });
}

async function deleteEntry(entryId) {
  if (!entryId) return;
  await api(`/webapp/me/entries/${entryId}`, { method: "DELETE" });
  await Promise.all([loadToday(), loadWeek(), loadFrequent()]);
  toast("Запись удалена");
}

async function favoriteEntry(entryId) {
  if (!entryId) return;
  await api(`/webapp/me/entries/${entryId}/favorite`, { method: "POST" });
  await loadFavorites();
  toast("Добавлено в шаблоны");
}

function updateParsedFoodField(event) {
  const input = event.target.closest("[data-field]");
  if (!input) return;
  const card = input.closest("[data-index]");
  const index = Number(card?.dataset.index);
  const food = state.parsedFoods[index];
  if (!food) return;
  const field = input.dataset.field;
  food[field] = field === "name" ? input.value.trim() : parseNumber(input.value);
}

function removeParsedFood(event) {
  const button = event.target.closest("[data-remove-parsed]");
  if (!button) return;
  const index = Number(button.dataset.removeParsed);
  state.parsedFoods.splice(index, 1);
  if (!state.parsedFoods.length) {
    nodes.foodPreview.classList.add("hidden");
    return;
  }
  renderParsedFoods({ source: state.parsedFoodSource });
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

function renderEmptyApp() {
  nodes.entries.innerHTML = '<div class="empty-state">Нет данных без Telegram-авторизации.</div>';
  nodes.frequentList.innerHTML = '<div class="empty-state">Открой из Telegram.</div>';
  nodes.favoritesList.innerHTML = '<div class="empty-state">Открой из Telegram.</div>';
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

function formatInput(value) {
  return value === null || value === undefined ? "" : String(formatNumber(value)).replace(/\s/g, "");
}

function mealLabel(meal) {
  return {
    breakfast: "Завтрак",
    lunch: "Обед",
    dinner: "Ужин",
    snack: "Перекус",
  }[meal] || "Приём пищи";
}

function sourceLabel(source) {
  return {
    ai: "AI",
    photo: "Фото",
    barcode: "Штрихкод",
    common: "База",
    history: "История",
  }[source] || "Оценка";
}

function entrySourceForParsed(source) {
  return {
    ai: "manual",
    photo: "ai_photo",
    barcode: "barcode",
    common: "food_search",
    history: "history",
  }[source] || "manual";
}

function normalizeParsedFood(food) {
  return {
    name: String(food.name || "").trim(),
    weight_g: numberOrNull(food.weight_g),
    kcal: numberOrNull(food.kcal) ?? 0,
    protein: numberOrNull(food.protein) ?? 0,
    fat: numberOrNull(food.fat) ?? 0,
    carbs: numberOrNull(food.carbs) ?? 0,
    confidence: numberOrNull(food.confidence),
    emoji: food.emoji || null,
    advice: food.advice || null,
  };
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
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

function setButtonBusy(button, label) {
  if (!button) return;
  button.dataset.idleHtml = button.innerHTML;
  button.textContent = label;
  button.disabled = true;
}

function restoreButton(button) {
  if (!button) return;
  button.innerHTML = button.dataset.idleHtml || button.textContent;
  button.disabled = false;
  delete button.dataset.idleHtml;
}
