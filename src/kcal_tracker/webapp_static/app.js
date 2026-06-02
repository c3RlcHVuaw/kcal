const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const state = {
  today: null,
  week: null,
  body: null,
  activeView: "today",
  selectedMeal: "lunch",
  editingEntryId: null,
  editingEntryBase: null,
  lockedScrollY: 0,
  activeSheet: null,
  parsedFoods: [],
  parsedFoodSource: "ai",
  foodReviewReturnView: "today",
  expandedParsedFood: null,
  addMode: "browse",
  foodSearchResults: [],
  frequentFoods: [],
  favoriteFoods: [],
  searchTimer: null,
  searchRequestId: 0,
  deleteConfirmTimer: null,
  entryHighlightKeys: new Set(),
  entryHighlightTimer: null,
  loadingAll: false,
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
  nutritionScore: document.querySelector("#nutrition-score"),
  nutritionStatus: document.querySelector("#nutrition-status"),
  macroTotal: document.querySelector("#macro-total"),
  macroBars: document.querySelector("#macro-bars"),
  protein: document.querySelector("#protein"),
  fat: document.querySelector("#fat"),
  carbs: document.querySelector("#carbs"),
  proteinRing: document.querySelector("#protein-ring"),
  fatRing: document.querySelector("#fat-ring"),
  carbsRing: document.querySelector("#carbs-ring"),
  proteinPercent: document.querySelector("#protein-percent"),
  fatPercent: document.querySelector("#fat-percent"),
  carbsPercent: document.querySelector("#carbs-percent"),
  proteinOverflow: document.querySelector("#protein-overflow"),
  fatOverflow: document.querySelector("#fat-overflow"),
  carbsOverflow: document.querySelector("#carbs-overflow"),
  water: document.querySelector("#water"),
  activityTotal: document.querySelector("#activity-total"),
  entries: document.querySelector("#entries"),
  foodTextForm: document.querySelector("#food-text-form"),
  foodText: document.querySelector("#food-text"),
  foodSearchForm: document.querySelector("#food-search-form"),
  foodSearch: document.querySelector("#food-search"),
  foodSearchBarcode: document.querySelector("#food-search-barcode"),
  foodSearchSection: document.querySelector("#food-search-section"),
  foodSearchResults: document.querySelector("#food-search-results"),
  foodSearchClear: document.querySelector("#food-search-clear"),
  foodAddKcalSummary: document.querySelector("#food-add-kcal-summary"),
  foodAddKcalLine: document.querySelector("#food-add-kcal-line"),
  foodAddProtein: document.querySelector("#food-add-protein"),
  foodAddFat: document.querySelector("#food-add-fat"),
  foodAddCarbs: document.querySelector("#food-add-carbs"),
  foodAddRecent: document.querySelector("#food-add-recent"),
  foodAddRecentList: document.querySelector("#food-add-recent-list"),
  foodAddFavorites: document.querySelector("#food-add-favorites"),
  foodAddFavoritesList: document.querySelector("#food-add-favorites-list"),
  foodPreview: document.querySelector("#food-preview"),
  foodPreviewSource: document.querySelector("#food-preview-source"),
  foodPreviewList: document.querySelector("#food-preview-list"),
  saveParsedFood: document.querySelector("#save-parsed-food"),
  foodPhotoButton: document.querySelector("#food-photo-button"),
  foodPhotoInput: document.querySelector("#food-photo-input"),
  foodPhotoHint: document.querySelector("#food-photo-hint"),
  barcodePhotoButton: document.querySelector("#barcode-photo-button"),
  barcodePhotoInput: document.querySelector("#barcode-photo-input"),
  barcodeCode: document.querySelector("#barcode-code"),
  barcodeCodeButton: document.querySelector("#barcode-code-button"),
  foodForm: document.querySelector("#food-form"),
  foodMeal: document.querySelector("#food-meal"),
  foodAddSheet: document.querySelector("#food-add-sheet"),
  foodAddPanel: document.querySelector(".food-add-panel"),
  foodAddClose: document.querySelector("#food-add-close"),
  foodReviewClose: document.querySelector("#food-review-close"),
  toast: document.querySelector("#toast"),
  weightButton: document.querySelector("#weight-button"),
  weightValue: document.querySelector("#weight-value"),
  weightGoal: document.querySelector("#weight-goal"),
  repeatYesterday: document.querySelector("#repeat-yesterday"),
  frequentList: document.querySelector("#frequent-list"),
  favoritesList: document.querySelector("#favorites-list"),
  weekAverage: document.querySelector("#week-average"),
  weekTarget: document.querySelector("#week-target"),
  weekTargetPercent: document.querySelector("#week-target-percent"),
  weekStatusLabel: document.querySelector("#week-status-label"),
  weekInsight: document.querySelector("#week-insight"),
  weekDelta: document.querySelector("#week-delta"),
  weekInTarget: document.querySelector("#week-in-target"),
  weekTracked: document.querySelector("#week-tracked"),
  weekConsistency: document.querySelector("#week-consistency"),
  weekChartNote: document.querySelector("#week-chart-note"),
  weekChart: document.querySelector("#week-chart"),
  goalForm: document.querySelector("#goal-form"),
  goalKind: document.querySelector("#goal-kind"),
  goalWeight: document.querySelector("#goal-weight"),
  goalPace: document.querySelector("#goal-pace"),
  activityForm: document.querySelector("#activity-form"),
  weightTrend: document.querySelector("#weight-trend"),
  weightChart: document.querySelector("#weight-chart"),
  habitList: document.querySelector("#habit-list"),
  moreKcal: document.querySelector("#more-kcal"),
  moreWater: document.querySelector("#more-water"),
  moreAiCaption: document.querySelector("#more-ai-caption"),
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
applyTelegramSafeArea();
["viewportChanged", "safeAreaChanged", "contentSafeAreaChanged"].forEach((eventName) => {
  try {
    tg?.onEvent?.(eventName, applyTelegramSafeArea);
  } catch {
    // Older Telegram clients can reject newer inset events.
  }
});
lockViewportZoom();

if (tg?.initDataUnsafe?.user?.first_name) {
  nodes.hello.textContent = `Привет, ${tg.initDataUnsafe.user.first_name}`;
  nodes.todayHello.textContent = `Привет, ${tg.initDataUnsafe.user.first_name}`;
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.view === "food") {
      openFoodAddSheet();
      return;
    }
    switchView(button.dataset.view);
  });
});

document.addEventListener("click", (event) => {
  const button = event.target.closest?.("button");
  if (!button || button.disabled) return;
  triggerHaptic(button.matches(".primary-button, .food-pick-add, [data-view='food']") ? "medium" : "light");
});

document.querySelectorAll("[data-food-tab]").forEach((button) => {
  button.addEventListener("click", () => switchFoodTab(button.dataset.foodTab));
});

document.querySelectorAll("[data-add-mode]").forEach((button) => {
  button.addEventListener("click", () => switchAddMode(button.dataset.addMode));
});

document.querySelectorAll("[data-add-mode-back]").forEach((button) => {
  button.addEventListener("click", () => switchAddMode("browse"));
});

document.querySelectorAll("[data-food-example]").forEach((button) => {
  button.addEventListener("click", () => {
    switchAddMode("ai");
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
    if (shortcut.dataset.viewShortcut === "food") {
      openFoodAddSheet();
      return;
    }
    switchView(shortcut.dataset.viewShortcut);
    return;
  }
  const foodSheetButton = event.target.closest("[data-open-food-sheet]");
  if (foodSheetButton) {
    openFoodAddSheet();
    return;
  }
  const deleteButton = event.target.closest("[data-delete-entry]");
  if (deleteButton) {
    deleteEntry(Number(deleteButton.dataset.deleteEntry), deleteButton);
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
    return;
  }
  const moreAction = event.target.closest("[data-more-action]");
  if (moreAction) {
    handleMoreAction(moreAction.dataset.moreAction);
  }
});
nodes.repeatYesterday.addEventListener("click", repeatYesterday);
nodes.openBot.addEventListener("click", openBotFromWebApp);
nodes.exportFood.addEventListener("click", exportFood);
nodes.foodAddClose.addEventListener("click", closeFoodAddSheet);
nodes.foodAddSheet.addEventListener("click", (event) => {
  if (event.target === nodes.foodAddSheet) closeFoodAddSheet();
});
nodes.foodReviewClose.addEventListener("click", closeFoodReviewSheet);
nodes.foodTextForm.addEventListener("submit", parseFoodText);
nodes.foodSearchForm.addEventListener("submit", searchFood);
nodes.foodSearch.addEventListener("input", queueFoodSearch);
nodes.foodSearchBarcode.addEventListener("click", () => {
  switchAddMode("barcode");
});
nodes.foodSearchClear.addEventListener("click", clearFoodSearch);
nodes.foodSearchResults.addEventListener("click", handleFoodPick);
nodes.foodAddRecentList.addEventListener("click", handleFoodPick);
nodes.foodAddFavoritesList.addEventListener("click", handleFoodPick);
nodes.saveParsedFood.addEventListener("click", saveParsedFoods);
nodes.foodPreviewList.addEventListener("input", updateParsedFoodField);
nodes.foodPreviewList.addEventListener("click", removeParsedFood);
nodes.foodPreviewList.addEventListener("submit", refineParsedFood);
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
nodes.entryEditWeight.addEventListener("input", recalculateEntryByWeight);
nodes.entryEditor.addEventListener("click", (event) => {
  if (event.target === nodes.entryEditor) closeEntryEditor();
});

document.querySelectorAll("[data-water]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (isBusy(button)) return;
    setButtonBusy(button, "...");
    try {
      await api("/webapp/me/water", {
        method: "POST",
        body: JSON.stringify({ amount_ml: Number(button.dataset.water) }),
      });
      await loadToday();
      toast("Вода добавлена");
    } catch {
      toast("Не получилось добавить воду");
    } finally {
      restoreButton(button);
    }
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
  if (isBusy(submit)) return;
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
  const hint = nodes.foodPhotoHint.value.trim() || nodes.foodText.value.trim();
  const form = new FormData();
  form.append("image", file);
  if (hint) form.append("text_hint", hint);

  if (isBusy(nodes.foodPhotoButton)) return;
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

  if (isBusy(nodes.barcodePhotoButton)) return;
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
  if (isBusy(nodes.barcodeCodeButton)) return;
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

function queueFoodSearch() {
  const query = nodes.foodSearch.value.trim();
  window.clearTimeout(state.searchTimer);
  if (query.length < 2) {
    clearFoodSearch(false);
    return;
  }
  state.searchTimer = window.setTimeout(() => searchFood(), 360);
}

async function searchFood(event) {
  event?.preventDefault();
  const query = nodes.foodSearch.value.trim();
  if (query.length < 2) {
    toast("Напиши, что найти");
    return;
  }
  nodes.foodSearchSection.classList.remove("hidden");
  if (!initData) {
    state.foodSearchResults = [];
    nodes.foodSearchResults.innerHTML = '<div class="empty-state">Поиск по базе работает внутри Telegram mini-app. В локальном браузере нет авторизации Telegram.</div>';
    return;
  }
  const requestId = ++state.searchRequestId;
  renderFoodPickLoading(nodes.foodSearchResults);
  nodes.foodSearchResults.setAttribute("aria-busy", "true");
  try {
    const result = await api(`/webapp/me/food/search?query=${encodeURIComponent(query)}`);
    if (requestId !== state.searchRequestId) return;
    state.foodSearchResults = result.foods.map(normalizeParsedFood);
    renderFoodPickList(nodes.foodSearchResults, state.foodSearchResults, {
      source: result.source,
      emptyText: "Ничего не нашлось. Можно разобрать через AI.",
    });
    switchAddMode("browse");
  } catch (error) {
    if (requestId !== state.searchRequestId) return;
    state.foodSearchResults = [];
    const text = error.status === 401
      ? "Открой mini-app из Telegram, чтобы поиск получил доступ к дневнику."
      : "Поиск не сработал. Попробуй AI или штрихкод.";
    nodes.foodSearchResults.innerHTML = `<div class="empty-state">${escapeHtml(text)}</div>`;
  } finally {
    if (requestId === state.searchRequestId) {
      nodes.foodSearchResults.removeAttribute("aria-busy");
    }
  }
}

function clearFoodSearch(clearInput = true) {
  if (clearInput) nodes.foodSearch.value = "";
  state.searchRequestId += 1;
  state.foodSearchResults = [];
  nodes.foodSearchSection.classList.add("hidden");
  nodes.foodSearchResults.innerHTML = "";
  nodes.foodSearchResults.removeAttribute("aria-busy");
}

function handleFoodPick(event) {
  const editButton = event.target.closest("[data-pick-edit]");
  const addButton = event.target.closest("[data-pick-add]");
  const button = editButton || addButton;
  if (!button) return;
  const list = foodPickSource(button.dataset.pickSource);
  const food = list[Number(button.dataset.pickIndex)];
  if (!food) return;
  if (editButton) {
    setParsedFoods({ foods: [food], source: button.dataset.entrySource || "food_search" });
    return;
  }
  addFoodEstimateToDiary(food, button.dataset.entrySource || "food_search", addButton);
}

async function addFoodEstimateToDiary(food, source, button) {
  if (button && isBusy(button)) return;
  if (button) setButtonBusy(button, "...");
  let added = false;
  try {
    await api("/webapp/me/entries", {
      method: "POST",
      body: JSON.stringify({
        ...food,
        source: entrySourceForParsed(source),
        meal_type: state.selectedMeal,
      }),
    });
    markEntryHighlights([food], state.selectedMeal);
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent()]);
    added = true;
    toast(`${food.name} добавлено`);
  } catch {
    toast("Не получилось добавить");
  } finally {
    if (button) restoreButton(button);
    if (added) flashFoodPickAdded(button);
  }
}

function setParsedFoods(result) {
  state.parsedFoods = result.foods.map(normalizeParsedFood);
  state.parsedFoodSource = result.source;
  state.expandedParsedFood = null;
  renderParsedFoods(result);
  openFoodReviewScreen();
}

async function saveParsedFoods() {
  const foods = state.parsedFoods.filter((food) => food.name && food.kcal !== null);
  if (!foods.length) {
    toast("Нет позиций для сохранения");
    return;
  }

  if (isBusy(nodes.saveParsedFood)) return;
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
    state.expandedParsedFood = null;
    nodes.foodTextForm.reset();
    nodes.barcodeCode.value = "";
    renderParsedFoods({ source: state.parsedFoodSource });
    markEntryHighlights(foods, state.selectedMeal);
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent()]);
    switchView("today");
    toast(foods.length === 1 ? "Еда добавлена" : `Добавлено позиций: ${foods.length}`);
  } catch {
    toast("Не получилось сохранить еду");
  } finally {
    restoreButton(nodes.saveParsedFood);
  }
}

nodes.weightButton.addEventListener("click", async () => {
  if (isBusy(nodes.weightButton)) return;
  const value = prompt("Вес в кг");
  const weight = parseNumber(value);
  if (!weight) return;
  setButtonBusy(nodes.weightButton, "...");
  try {
    await api("/webapp/me/weight", {
      method: "POST",
      body: JSON.stringify({ weight_kg: weight }),
    });
    await Promise.allSettled([loadToday(), loadBody()]);
    toast("Вес сохранён");
  } catch {
    toast("Не получилось сохранить вес");
  } finally {
    restoreButton(nodes.weightButton);
  }
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
  const button = nodes.foodForm.querySelector("button[type='submit']");
  if (isBusy(button)) return;
  setButtonBusy(button, "Сохраняю...");
  try {
    await api("/webapp/me/entries", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    nodes.foodForm.reset();
    closeFoodAddSheet();
    markEntryHighlights([payload], payload.meal_type);
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent()]);
    switchView("today");
    toast("Еда добавлена");
  } catch {
    toast("Не получилось добавить еду");
  } finally {
    restoreButton(button);
  }
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
  const button = nodes.goalForm.querySelector("button[type='submit']");
  if (isBusy(button)) return;
  setButtonBusy(button, "Сохраняю...");
  try {
    await api("/webapp/me/goals/weight", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    await Promise.allSettled([loadToday(), loadWeek()]);
    toast("Цель обновлена");
  } catch {
    toast("Не получилось обновить цель");
  } finally {
    restoreButton(button);
  }
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
  const button = nodes.activityForm.querySelector("button[type='submit']");
  if (isBusy(button)) return;
  setButtonBusy(button, "Сохраняю...");
  try {
    await api("/webapp/me/activity", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    nodes.activityForm.reset();
    await Promise.allSettled([loadToday(), loadWeek()]);
    toast("Активность добавлена");
  } catch {
    toast("Не получилось добавить активность");
  } finally {
    restoreButton(button);
  }
});

nodes.promoForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = nodes.promoCode.value.trim();
  if (!code) {
    toast("Введи промокод");
    return;
  }
  const button = nodes.promoForm.querySelector("button[type='submit']");
  if (isBusy(button)) return;
  setButtonBusy(button, "Проверяю...");
  try {
    const result = await api("/webapp/me/promos/validate", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    renderPromo(result);
  } catch {
    toast("Не получилось проверить промокод");
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
  if (isBusy(button)) return;
  setButtonBusy(button, "Сохраняю...");
  try {
    await api(`/webapp/me/entries/${state.editingEntryId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    closeEntryEditor();
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent(), loadFavorites()]);
    toast("Запись обновлена");
  } catch {
    toast("Не получилось обновить запись");
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
  event.preventDefault();
  toast(event.reason?.message || "Что-то пошло не так");
});

function lockViewportZoom() {
  let lastTouchEnd = 0;
  document.addEventListener("gesturestart", (event) => event.preventDefault(), { passive: false });
  document.addEventListener("gesturechange", (event) => event.preventDefault(), { passive: false });
  document.addEventListener("gestureend", (event) => event.preventDefault(), { passive: false });
  document.addEventListener("touchmove", (event) => {
    if (event.touches.length > 1) event.preventDefault();
  }, { passive: false });
  document.addEventListener("touchend", (event) => {
    const now = Date.now();
    if (now - lastTouchEnd <= 320) event.preventDefault();
    lastTouchEnd = now;
  }, { passive: false });
}

function applyTelegramSafeArea() {
  const top = Math.max(
    Number(tg?.safeAreaInset?.top) || 0,
    Number(tg?.contentSafeAreaInset?.top) || 0,
  );
  document.documentElement.style.setProperty("--telegram-top-safe-js", `${top}px`);
}

function triggerHaptic(style = "light") {
  try {
    tg?.HapticFeedback?.impactOccurred?.(style);
  } catch {
    // Haptics are optional and unavailable in local browsers.
  }
}

async function loadAll() {
  if (!initData || state.loadingAll) return;
  state.loadingAll = true;
  setButtonBusy(nodes.refresh, "...");
  const results = await Promise.allSettled([
    loadToday(),
    loadWeek(),
    loadBody(),
    loadFrequent(),
    loadFavorites(),
  ]);
  state.loadingAll = false;
  restoreButton(nodes.refresh);
  if (results.some((result) => result.status === "rejected")) {
    toast("Часть данных не загрузилась");
  }
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
  state.frequentFoods = items.map((item) => normalizeParsedFood(item.entry));
  renderFoodPickList(nodes.foodAddRecentList, state.frequentFoods, {
    source: "history",
    emptyText: "Недавние появятся после первых записей.",
  });
  renderReusableFood(nodes.frequentList, items.map((item) => ({
    id: item.entry.id,
    name: item.entry.name,
    kcal: item.entry.kcal,
    meta: `${item.count} раза`,
    action: () => repeatEntry(item.entry.id, item.entry),
  })));
}

async function loadFavorites() {
  const items = await api("/webapp/me/favorites");
  state.favoriteFoods = items.map(normalizeParsedFood);
  nodes.foodAddFavorites.classList.toggle("hidden", !state.favoriteFoods.length);
  renderFoodPickList(nodes.foodAddFavoritesList, state.favoriteFoods, {
    source: "history",
    emptyText: "Сохрани любимые продукты как шаблоны.",
  });
  renderReusableFood(nodes.favoritesList, items.map((item) => ({
    id: item.id,
    name: item.name,
    kcal: item.kcal,
    meta: item.weight_g ? `${formatNumber(item.weight_g)} г` : "шаблон",
    action: () => addFavorite(item.id, item),
  })));
}

function renderToday(data) {
  const diary = data.diary;
  const progress = diary.target_kcal > 0 ? Math.min(diary.kcal / diary.target_kcal, 1) : 0;
  setProgressValue(nodes.kcalProgress, "width", `${Math.round(progress * 100)}%`);
  setTextWithPulse(nodes.kcalPercent, `${Math.round(progress * 100)}%`);
  const left = Math.round(diary.target_kcal - diary.kcal);
  setTextWithPulse(nodes.kcalEaten, Math.round(diary.kcal));
  setTextWithPulse(nodes.kcalBurned, Math.round(diary.activity_kcal));
  setTextWithPulse(nodes.kcalLeft, left >= 0 ? String(left) : `+${Math.abs(left)}`);
  setTextWithPulse(nodes.kcalTarget, `${Math.round(diary.kcal)} / ${diary.target_kcal} ккал`);
  renderFoodAddSummary(diary);
  renderMacroRing("protein", diary.protein, diary.target_protein);
  renderMacroRing("fat", diary.fat, diary.target_fat);
  renderMacroRing("carbs", diary.carbs, diary.target_carbs);
  renderNutritionOverview(diary);
  setTextWithPulse(nodes.water, `${data.water_ml} мл воды`);
  setTextWithPulse(nodes.moreKcal, `${Math.round(diary.kcal)} / ${diary.target_kcal}`);
  setTextWithPulse(nodes.moreWater, `${data.water_ml} мл`);
  setTextWithPulse(nodes.activityTotal, `${Math.round(diary.activity_kcal)} ккал активности`);
  setTextWithPulse(nodes.weightValue, data.latest_weight_kg ? `${formatNumber(data.latest_weight_kg)} кг` : "Записать");
  setTextWithPulse(nodes.weightGoal, data.weight_goal.forecast_text);
  const aiUsageText = data.ai_usage.daily_limit
    ? `${data.ai_usage.used_today} / ${data.ai_usage.daily_limit}`
    : `${data.ai_usage.used_today} / ∞`;
  setTextWithPulse(nodes.aiUsage, aiUsageText);
  setTextWithPulse(nodes.moreAiCaption, data.ai_usage.daily_limit
    ? `${Math.max(data.ai_usage.daily_limit - data.ai_usage.used_today, 0)} осталось`
    : "без дневного лимита");
  nodes.goalKind.value = data.weight_goal.goal || "maintain";
  nodes.goalWeight.value = data.weight_goal.target_weight_kg ? formatNumber(data.weight_goal.target_weight_kg) : "";
  nodes.goalPace.value = data.weight_goal.weekly_weight_change_kg ? formatNumber(data.weight_goal.weekly_weight_change_kg) : "";

  nodes.entries.innerHTML = renderMealDiary(diary.entries);
}

function renderFoodAddSummary(diary) {
  if (!nodes.foodAddKcalSummary) return;
  const kcalTarget = Math.max(Number(diary.target_kcal || 0), 0);
  const kcal = Math.max(Number(diary.kcal || 0), 0);
  const ratio = kcalTarget > 0 ? Math.min(kcal / kcalTarget, 1) : 0;
  setTextWithPulse(nodes.foodAddKcalSummary, `${Math.round(kcal)} / ${Math.round(kcalTarget)} ккал`);
  setProgressValue(nodes.foodAddKcalLine, "--progress", `${Math.round(ratio * 100)}%`);
  setTextWithPulse(nodes.foodAddProtein, `${Math.round(diary.protein || 0)} / ${Math.round(diary.target_protein || 0)} г`);
  setTextWithPulse(nodes.foodAddFat, `${Math.round(diary.fat || 0)} / ${Math.round(diary.target_fat || 0)} г`);
  setTextWithPulse(nodes.foodAddCarbs, `${Math.round(diary.carbs || 0)} / ${Math.round(diary.target_carbs || 0)} г`);
}

function renderNutritionOverview(diary) {
  const macroTotal = Math.round(Number(diary.protein || 0) + Number(diary.fat || 0) + Number(diary.carbs || 0));
  const proteinTarget = Math.max(Number(diary.target_protein || 0), 1);
  const fatTarget = Math.max(Number(diary.target_fat || 0), 1);
  const carbsTarget = Math.max(Number(diary.target_carbs || 0), 1);
  const kcalTarget = Math.max(Number(diary.target_kcal || 0), 1);
  const macroFit = [
    ratioScore(Number(diary.protein || 0) / proteinTarget),
    ratioScore(Number(diary.fat || 0) / fatTarget),
    ratioScore(Number(diary.carbs || 0) / carbsTarget),
    ratioScore(Number(diary.kcal || 0) / kcalTarget),
  ];
  const score = Math.round(macroFit.reduce((sum, item) => sum + item, 0) / macroFit.length);
  const status = score >= 72 ? "Отличный баланс" : score >= 45 ? "В норме" : "Нужно поесть";

  setTextWithPulse(nodes.nutritionScore, String(score));
  setTextWithPulse(nodes.nutritionStatus, status);
  nodes.nutritionStatus.classList.toggle("warn-status", score < 45);
  setTextWithPulse(nodes.macroTotal, `${macroTotal} грамм`);
  nodes.macroBars.innerHTML = Array.from({ length: 28 }, (_, index) => {
    const kind = index % 3 === 0 ? "protein" : index % 3 === 1 ? "carbs" : "fat";
    return `<i class="${kind}"></i>`;
  }).join("");
}

function renderMacroRing(kind, rawValue, rawTarget) {
  const metric = macroMetric(rawValue, rawTarget);
  const valueNode = nodes[kind];
  const ringNode = nodes[`${kind}Ring`];
  const percentNode = nodes[`${kind}Percent`];
  const overflowNode = nodes[`${kind}Overflow`];

  setTextWithPulse(valueNode, `${metric.value}/${metric.target} г`);
  setTextWithPulse(percentNode, `${metric.percent}%`);
  setTextWithPulse(overflowNode, metric.overflowGrams > 0 ? `+${metric.overflowGrams} г` : "");
  overflowNode.classList.toggle("visible", metric.overflowGrams > 0);
  setProgressValue(ringNode, "--macro-base-end", `${metric.baseEndPercent}%`);
  ringNode.style.setProperty("--macro-overflow-start", `${metric.baseEndPercent}%`);
  ringNode.style.setProperty("--macro-overflow-end", `${metric.overflowEndPercent}%`);
}

function macroMetric(rawValue, rawTarget) {
  const value = Math.max(Number(rawValue || 0), 0);
  const target = Math.max(Number(rawTarget || 0), 0);
  const ratio = target > 0 ? value / target : 0;
  const baseRatio = Math.min(ratio, 1);
  const overflowRatio = Math.min(Math.max(ratio - 1, 0), 0.35);
  const baseEndPercent = Math.round((overflowRatio > 0 ? 1 - overflowRatio : baseRatio) * 100);
  return {
    value: Math.round(value),
    target: Math.round(target),
    ratio,
    percent: target > 0 ? Math.round(ratio * 100) : 0,
    baseRatio,
    overflowRatio,
    baseEndPercent,
    overflowEndPercent: overflowRatio > 0 ? 100 : baseEndPercent,
    overflowGrams: target > 0 ? Math.max(Math.round(value - target), 0) : 0,
  };
}

function ratioScore(ratio) {
  if (!Number.isFinite(ratio) || ratio <= 0) return 0;
  return Math.max(0, Math.min(100, 100 - Math.abs(1 - ratio) * 90));
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
    const mealMacros = mealMacroSummary(meal.items);
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
            <span>${mealSummaryText(meal, mealMacros)}</span>
            ${meal.items.length ? `
              <div class="meal-macros" aria-label="БЖУ за ${meal.title}">
                <i class="carbs">У ${Math.round(mealMacros.carbs)}</i>
                <i class="protein">Б ${Math.round(mealMacros.protein)}</i>
                <i class="fat">Ж ${Math.round(mealMacros.fat)}</i>
              </div>
            ` : ""}
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

function mealMacroSummary(items) {
  return items.reduce((total, entry) => ({
    protein: total.protein + Number(entry.protein || 0),
    fat: total.fat + Number(entry.fat || 0),
    carbs: total.carbs + Number(entry.carbs || 0),
  }), { protein: 0, fat: 0, carbs: 0 });
}

function mealSummaryText(meal, macros) {
  if (!meal.items.length) return meal.hint;
  const count = meal.items.length;
  const totalGrams = Math.round(macros.protein + macros.fat + macros.carbs);
  return `${count} ${pluralRu(count, "позиция", "позиции", "позиций")} · ${totalGrams} г БЖУ`;
}

function renderFoodEntry(entry) {
  const highlightClass = isEntryHighlighted(entry) ? " is-highlighted" : "";
  return `
    <article class="entry food-card${highlightClass}">
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
          <button type="button" data-delete-entry="${entry.id}" aria-label="Удалить ${escapeHtml(entry.name)}">Удалить</button>
        </div>
      </div>
    </article>
  `;
}

function entryHighlightKey(food, mealType) {
  return [
    String(food?.name || "").trim().toLowerCase(),
    Math.round(Number(food?.kcal || 0)),
    mealType || mealIdForNow(),
  ].join("|");
}

function markEntryHighlights(foods, mealType) {
  const keys = foods
    .filter((food) => food?.name)
    .map((food) => entryHighlightKey(food, food.meal_type || mealType));
  if (!keys.length) return;
  state.entryHighlightKeys = new Set(keys);
  window.clearTimeout(state.entryHighlightTimer);
  state.entryHighlightTimer = window.setTimeout(() => {
    state.entryHighlightKeys.clear();
    state.entryHighlightTimer = null;
  }, 2400);
}

function isEntryHighlighted(entry) {
  return state.entryHighlightKeys.has(entryHighlightKey(entry, mealIdForEntry(entry)));
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
  const days = data.days || [];
  const trackedDays = days.filter((day) => day.entries_count);
  const totalDays = Math.max(days.length, 1);
  const average = Math.round(Number(data.average_kcal || 0));
  const target = Math.round(Number(data.target_kcal || 0));
  const delta = average - target;
  const absDelta = Math.abs(delta);
  const ratio = target > 0 ? average / target : 0;
  const percent = target > 0 ? Math.round(ratio * 100) : 0;
  const status = weekStatus(delta, target, trackedDays.length);
  const trackedText = `${trackedDays.length}/${totalDays}`;

  setTextWithPulse(nodes.weekAverage, `${average} ккал`);
  setTextWithPulse(nodes.weekTarget, `Цель: ${target} ккал`);
  setTextWithPulse(nodes.weekTargetPercent, `${percent}%`);
  setTextWithPulse(nodes.weekStatusLabel, status.label);
  setTextWithPulse(nodes.weekInsight, status.text);
  setTextWithPulse(nodes.weekDelta, delta === 0 ? "0" : `${delta > 0 ? "+" : "-"}${absDelta} ккал`);
  setTextWithPulse(nodes.weekInTarget, `${data.days_in_target}/${totalDays}`);
  setTextWithPulse(nodes.weekTracked, trackedText);
  setTextWithPulse(nodes.weekConsistency, trackedDays.length >= 6 ? "отличная регулярность" : trackedDays.length >= 4 ? "почти вся неделя" : "мало данных");
  setTextWithPulse(nodes.weekChartNote, `${trackedDays.length} ${pluralRu(trackedDays.length, "день", "дня", "дней")} с записями`);
  document.querySelector(".week-target-ring")?.style.setProperty("--week-progress", `${Math.min(percent, 100)}%`);
  document.querySelector(".progress-insight-card")?.classList.toggle("is-over", status.kind === "over");
  document.querySelector(".progress-insight-card")?.classList.toggle("is-under", status.kind === "under");
  document.querySelector(".progress-insight-card")?.classList.toggle("is-good", status.kind === "good");

  const max = Math.max(target, ...days.map((day) => day.kcal), 1);
  nodes.weekChart.innerHTML = days.map((day) => {
    const height = Math.max(5, Math.round((day.kcal / max) * 116));
    const dayKind = weekDayKind(day, target);
    const kcalLabel = day.entries_count ? Math.round(day.kcal) : "—";
    const entryLabel = day.entries_count
      ? `${day.entries_count} ${pluralRu(day.entries_count, "запись", "записи", "записей")}`
      : "нет записей";
    return `
      <div class="week-bar ${dayKind}">
        <strong>${kcalLabel}</strong>
        <i style="height:${height}px"></i>
        <em>${entryLabel}</em>
        <span>${escapeHtml(day.date)}</span>
      </div>
    `;
  }).join("");
}

function weekStatus(delta, target, trackedCount) {
  if (!trackedCount) {
    return {
      kind: "empty",
      label: "Неделя пока пустая",
      text: "Добавь несколько приёмов пищи, и здесь появится честный тренд.",
    };
  }
  const tolerance = Math.max(120, Math.round(target * 0.08));
  if (Math.abs(delta) <= tolerance) {
    return {
      kind: "good",
      label: "Рядом с целью",
      text: "Среднее держится в рабочем коридоре. Продолжай в том же темпе.",
    };
  }
  if (delta > 0) {
    return {
      kind: "over",
      label: "Выше цели",
      text: "Неделя идёт с перебором. Посмотри дни с красными столбцами.",
    };
  }
  return {
    kind: "under",
    label: "Ниже цели",
    text: "Есть заметный недобор. Проверь, хватает ли белка и плотных приёмов пищи.",
  };
}

function weekDayKind(day, target) {
  if (!day.entries_count) return "empty";
  const tolerance = Math.max(120, Math.round(target * 0.08));
  if (day.kcal > target + tolerance) return "over";
  if (day.kcal < Math.max(target - tolerance, 0)) return "under";
  return "near";
}

function renderBody(data) {
  setTextWithPulse(nodes.weightTrend, data.latest_weight_kg
    ? `${formatNumber(data.latest_weight_kg)} кг, ${data.trend_label}`
    : "нет данных");
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

function renderFoodPickList(container, foods, options = {}) {
  const source = options.source || "food_search";
  if (!foods.length) {
    container.innerHTML = `<div class="empty-state">${escapeHtml(options.emptyText || "Пока пусто.")}</div>`;
    return;
  }
  const listName = source === "history" && container === nodes.foodAddFavoritesList
    ? "favorites"
    : source === "history"
      ? "frequent"
      : "search";
  container.innerHTML = foods.map((food, index) => {
    const impact = foodPickImpact(food);
    return `
      <article class="food-pick-card">
        <button class="food-pick-main" type="button" data-pick-edit="${index}" data-pick-index="${index}" data-pick-source="${listName}" data-entry-source="${source}">
          <strong>${escapeHtml(food.name)}</strong>
          <span>${Math.round(food.kcal || 0)} ккал${food.weight_g ? ` · ${formatNumber(food.weight_g)} г` : ""}</span>
          <em>Б ${formatNumber(food.protein || 0)} · Ж ${formatNumber(food.fat || 0)} · У ${formatNumber(food.carbs || 0)}</em>
          ${impact ? `<small class="food-impact ${impact.kind}">${escapeHtml(impact.text)}</small>` : ""}
        </button>
        <button class="food-pick-add" type="button" data-pick-add="${index}" data-pick-index="${index}" data-pick-source="${listName}" data-entry-source="${source}" aria-label="Добавить ${escapeHtml(food.name)}">
          <svg aria-hidden="true"><use href="#icon-plus"></use></svg>
        </button>
      </article>
    `;
  }).join("");
}

function foodPickImpact(food) {
  const diary = state.today?.diary;
  const target = Number(diary?.target_kcal || 0);
  const current = Number(diary?.kcal || 0);
  const kcal = Number(food?.kcal || 0);
  if (!target || !Number.isFinite(target) || !Number.isFinite(kcal) || kcal <= 0) return null;
  const after = current + kcal;
  const leftAfter = Math.round(target - after);
  if (leftAfter < 0) {
    return { kind: "over", text: `перебор +${Math.abs(leftAfter)} ккал` };
  }
  if (leftAfter <= 250) {
    return { kind: "near", text: `почти цель: останется ${leftAfter} ккал` };
  }
  const percent = Math.min(Math.round((kcal / target) * 100), 100);
  return { kind: "ok", text: `останется ${leftAfter} ккал · ${percent}% дня` };
}

function renderFoodPickLoading(container, count = 4) {
  container.innerHTML = Array.from({ length: count }, () => `
    <article class="food-pick-card food-pick-skeleton" aria-hidden="true">
      <div>
        <i class="skeleton-line title"></i>
        <i class="skeleton-line medium"></i>
        <i class="skeleton-line short"></i>
      </div>
      <i class="skeleton-add"></i>
    </article>
  `).join("");
}

function foodPickSource(source) {
  if (source === "frequent") return state.frequentFoods;
  if (source === "favorites") return state.favoriteFoods;
  return state.foodSearchResults;
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
  nodes.foodPreview.classList.remove("hidden");
  if (!state.parsedFoods.length) {
    nodes.saveParsedFood.disabled = true;
    nodes.foodPreviewList.innerHTML = `
      <article class="parsed-food-empty component-card">
        <strong>Позиции удалены</strong>
        <p>Можно вернуться назад и добавить еду заново через поиск, AI, фото или штрихкод.</p>
        <button class="secondary-button" type="button" data-review-add-again>Добавить заново</button>
      </article>
    `;
    return;
  }
  nodes.saveParsedFood.disabled = false;
  nodes.foodPreviewList.innerHTML = state.parsedFoods.map((food, index) => `
    <article class="parsed-food-card entry food-card${state.expandedParsedFood === index ? " is-expanded" : ""}" data-index="${index}">
      <div class="food-thumb">${escapeHtml(food.emoji || foodInitial(food.name))}</div>
      <div class="food-content">
        <div class="entry-main">
          <strong>${escapeHtml(food.name || "Еда")}</strong>
          <b>${Math.round(food.kcal || 0)} ккал</b>
        </div>
        <div class="entry-meta">
          <span>${food.weight_g ? `${formatNumber(food.weight_g)} г` : "без граммовки"}</span>
          <span>${Math.round(food.protein || 0)}Б</span>
          <span>${Math.round(food.fat || 0)}Ж</span>
          <span>${Math.round(food.carbs || 0)}У</span>
          <span>${sourceLabel(result.source)}${confidenceLabel(food.confidence)}</span>
        </div>
        <div class="entry-actions parsed-entry-actions">
          <button type="button" data-toggle-parsed="${index}">${state.expandedParsedFood === index ? "Свернуть" : "Изменить"}</button>
          <button type="button" data-remove-parsed="${index}" aria-label="Удалить ${escapeHtml(food.name)}">Удалить</button>
        </div>
        <div class="parsed-food-editor" ${state.expandedParsedFood === index ? "" : "hidden"}>
          <label class="wide-field compact-fields">
            <span>Название</span>
            <input data-field="name" value="${escapeHtml(food.name)}" aria-label="Название" />
          </label>
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
          ${food.advice ? `<p class="preview-advice">${escapeHtml(food.advice)}</p>` : ""}
          <details class="refine-details">
            <summary>Уточнить через AI</summary>
            <form class="refine-form" data-refine-index="${index}">
              <input name="refinement" autocomplete="off" placeholder="Без хлеба, половина, ещё соус..." />
              <button class="secondary-button" type="submit">Уточнить</button>
            </form>
          </details>
        </div>
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
  state.editingEntryBase = {
    weight_g: numberOrNull(entry.weight_g),
    kcal: numberOrNull(entry.kcal) ?? 0,
    protein: numberOrNull(entry.protein) ?? 0,
    fat: numberOrNull(entry.fat) ?? 0,
    carbs: numberOrNull(entry.carbs) ?? 0,
  };
  lockPageScroll("entry-editor");
  nodes.entryEditor.classList.remove("hidden");
}

function closeEntryEditor() {
  state.editingEntryId = null;
  state.editingEntryBase = null;
  nodes.entryEditor.classList.add("hidden");
  nodes.entryEditForm.reset();
  unlockPageScroll("entry-editor");
}

function openFoodAddSheet() {
  switchAddMode("browse");
  lockPageScroll("food-add");
  nodes.foodAddSheet.classList.remove("hidden");
}

function closeFoodAddSheet() {
  switchAddMode("browse");
  nodes.foodAddSheet.classList.add("hidden");
  unlockPageScroll("food-add");
}

function openFoodReviewScreen() {
  const returnView = state.activeView === "food-review" ? state.foodReviewReturnView : state.activeView;
  state.foodReviewReturnView = returnView || "today";
  if (!nodes.foodAddSheet.classList.contains("hidden")) {
    closeFoodAddSheet();
  }
  switchView("food-review");
  requestAnimationFrame(() => {
    window.scrollTo({ top: 0 });
  });
}

function closeFoodReviewSheet() {
  const returnView = state.foodReviewReturnView || "today";
  switchView(returnView === "food-review" ? "today" : returnView);
}

function lockPageScroll(sheetName) {
  if (state.activeSheet) {
    state.activeSheet = sheetName;
    return;
  }
  state.lockedScrollY = window.scrollY || document.documentElement.scrollTop || 0;
  document.body.style.top = `-${state.lockedScrollY}px`;
  state.activeSheet = sheetName;
  document.body.classList.add("sheet-open");
}

function unlockPageScroll(sheetName) {
  if (state.activeSheet && state.activeSheet !== sheetName) return;
  document.body.classList.remove("sheet-open");
  document.body.style.top = "";
  window.scrollTo(0, state.lockedScrollY || 0);
  state.lockedScrollY = 0;
  state.activeSheet = null;
}

function recalculateEntryByWeight() {
  const base = state.editingEntryBase;
  if (!base?.weight_g || base.weight_g <= 0) return;
  const nextWeight = parseNumber(nodes.entryEditWeight.value);
  if (!nextWeight || nextWeight <= 0) return;
  const scale = nextWeight / base.weight_g;
  nodes.entryEditKcal.value = formatInput(scaledValue(base.kcal, scale));
  nodes.entryEditProtein.value = formatInput(scaledValue(base.protein, scale));
  nodes.entryEditFat.value = formatInput(scaledValue(base.fat, scale));
  nodes.entryEditCarbs.value = formatInput(scaledValue(base.carbs, scale));
}

function scaledValue(value, scale) {
  return Math.round(Number(value || 0) * scale * 10) / 10;
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

async function deleteEntry(entryId, button) {
  if (!entryId) return;
  if (button && button.dataset.confirmDelete !== "true") {
    armDeleteConfirm(button);
    return;
  }
  if (button && isBusy(button)) return;
  if (button) {
    disarmDeleteConfirm(button);
    setButtonBusy(button, "...");
  }
  try {
    await api(`/webapp/me/entries/${entryId}`, { method: "DELETE" });
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent()]);
    toast("Запись удалена");
  } catch {
    toast("Не получилось удалить запись");
  } finally {
    if (button) restoreButton(button);
  }
}

function armDeleteConfirm(button) {
  clearDeleteConfirm();
  button.dataset.confirmDelete = "true";
  button.dataset.idleHtml = button.innerHTML;
  button.dataset.idleLabel = button.getAttribute("aria-label") || "";
  button.classList.add("confirm-delete");
  button.textContent = "Точно удалить?";
  button.setAttribute("aria-label", "Подтвердить удаление");
  triggerHaptic("medium");
  state.deleteConfirmTimer = window.setTimeout(clearDeleteConfirm, 2600);
}

function clearDeleteConfirm() {
  window.clearTimeout(state.deleteConfirmTimer);
  state.deleteConfirmTimer = null;
  document.querySelectorAll("[data-confirm-delete='true']").forEach((button) => {
    disarmDeleteConfirm(button);
  });
}

function disarmDeleteConfirm(button) {
  button.classList.remove("confirm-delete");
  button.innerHTML = button.dataset.idleHtml || "Удалить";
  if (button.dataset.idleLabel) {
    button.setAttribute("aria-label", button.dataset.idleLabel);
  } else {
    button.removeAttribute("aria-label");
  }
  delete button.dataset.confirmDelete;
  delete button.dataset.idleHtml;
  delete button.dataset.idleLabel;
}

async function favoriteEntry(entryId) {
  if (!entryId) return;
  try {
    await api(`/webapp/me/entries/${entryId}/favorite`, { method: "POST" });
    await loadFavorites();
    toast("Добавлено в шаблоны");
  } catch {
    toast("Не получилось добавить шаблон");
  }
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
  const addAgain = event.target.closest("[data-review-add-again]");
  if (addAgain) {
    switchView(state.foodReviewReturnView || "today");
    openFoodAddSheet();
    return;
  }
  const toggleButton = event.target.closest("[data-toggle-parsed]");
  if (toggleButton) {
    const index = Number(toggleButton.dataset.toggleParsed);
    state.expandedParsedFood = state.expandedParsedFood === index ? null : index;
    renderParsedFoods({ source: state.parsedFoodSource });
    return;
  }
  const button = event.target.closest("[data-remove-parsed]");
  if (!button) return;
  const index = Number(button.dataset.removeParsed);
  state.parsedFoods.splice(index, 1);
  if (state.expandedParsedFood === index) {
    state.expandedParsedFood = null;
  } else if (state.expandedParsedFood !== null && state.expandedParsedFood > index) {
    state.expandedParsedFood -= 1;
  }
  renderParsedFoods({ source: state.parsedFoodSource });
}

async function refineParsedFood(event) {
  event.preventDefault();
  const form = event.target.closest("[data-refine-index]");
  if (!form) return;
  const index = Number(form.dataset.refineIndex);
  const food = state.parsedFoods[index];
  const input = form.querySelector("input[name='refinement']");
  const text = input?.value.trim() || "";
  if (!food || text.length < 2) {
    toast("Напиши, что уточнить");
    return;
  }
  const button = form.querySelector("button[type='submit']");
  if (isBusy(button)) return;
  setButtonBusy(button, "Считаю...");
  try {
    const result = await api("/webapp/me/food/refine", {
      method: "POST",
      body: JSON.stringify({
        estimate: food,
        text,
        source: state.parsedFoodSource,
      }),
    });
    if (result.foods.length) {
      state.parsedFoods[index] = normalizeParsedFood(result.foods[0]);
      state.parsedFoodSource = result.source;
      renderParsedFoods(result);
      toast("Оценка уточнена");
    }
  } catch (error) {
    const message = error.status === 402
      ? "Лимит AI на сегодня закончился"
      : "Не получилось уточнить";
    toast(message);
  } finally {
    restoreButton(button);
  }
}

async function repeatEntry(entryId, entry = null) {
  try {
    await api(`/webapp/me/repeat-entry/${entryId}`, { method: "POST" });
    if (entry) markEntryHighlights([entry], mealIdForEntry(entry));
    await Promise.allSettled([loadToday(), loadWeek()]);
    switchView("today");
    toast("Добавлено");
  } catch {
    toast("Не получилось повторить запись");
  }
}

async function addFavorite(favoriteId, favorite = null) {
  try {
    await api(`/webapp/me/favorites/${favoriteId}`, { method: "POST" });
    if (favorite) markEntryHighlights([favorite], state.selectedMeal);
    await Promise.allSettled([loadToday(), loadWeek()]);
    switchView("today");
    toast("Шаблон добавлен");
  } catch {
    toast("Не получилось добавить шаблон");
  }
}

async function repeatYesterday() {
  if (isBusy(nodes.repeatYesterday)) return;
  setButtonBusy(nodes.repeatYesterday, "Повторяю...");
  try {
    const entries = await api("/webapp/me/repeat-yesterday", { method: "POST" });
    markEntryHighlights(entries, null);
    await Promise.allSettled([loadToday(), loadWeek()]);
    switchView("today");
    toast(entries.length ? "Вчерашний день добавлен" : "Вчера нечего повторять");
  } catch {
    toast("Не получилось повторить вчера");
  } finally {
    restoreButton(nodes.repeatYesterday);
  }
}

function handleMoreAction(action) {
  switch (action) {
    case "add-food":
      openFoodAddSheet();
      return;
    case "barcode":
      openFoodAddSheet();
      switchAddMode("barcode");
      return;
    case "templates":
      switchView("food");
      switchFoodTab("templates");
      return;
    case "repeat-yesterday":
      repeatYesterday();
      return;
    case "water":
    case "weight":
    case "activity":
      switchView("body");
      return;
    case "progress":
      switchView("progress");
      return;
    case "subscription":
    case "reminders":
    case "support":
      openBotFromWebApp();
      return;
    default:
      toast("Скоро добавим");
  }
}

function openBotFromWebApp() {
  if (tg) {
    tg.close();
    return;
  }
  toast("В Telegram откроется бот");
}

async function exportFood() {
  if (isBusy(nodes.exportFood)) return;
  setButtonBusy(nodes.exportFood, "Готовлю...");
  try {
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
  } catch {
    toast("Не получилось подготовить экспорт");
  } finally {
    restoreButton(nodes.exportFood);
  }
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

function switchAddMode(mode) {
  if (!["browse", "ai", "photo", "manual", "barcode"].includes(mode)) return;
  state.addMode = mode;
  document.querySelectorAll("[data-add-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.addMode === mode);
  });
  document.querySelectorAll("[data-add-browse]").forEach((panel) => {
    panel.classList.toggle("hidden", mode !== "browse");
  });
  document.querySelectorAll("[data-add-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.addPanel === mode);
  });
  nodes.foodAddPanel?.classList.remove("mode-browse", "mode-ai", "mode-photo", "mode-manual", "mode-barcode");
  nodes.foodAddPanel?.classList.add(`mode-${mode}`);
  requestAnimationFrame(() => {
    nodes.foodAddSheet.querySelector(".food-add-scroll")?.scrollTo({ top: 0 });
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
  nodes.kcalEaten.textContent = "0";
  nodes.kcalBurned.textContent = "0";
  nodes.kcalLeft.textContent = "0";
  nodes.kcalTarget.textContent = "0 / 0 ккал";
  nodes.kcalPercent.textContent = "0%";
  nodes.kcalProgress.style.width = "0%";
  renderMacroRing("protein", 0, 0);
  renderMacroRing("fat", 0, 0);
  renderMacroRing("carbs", 0, 0);
  renderNutritionOverview({
    protein: 0,
    fat: 0,
    carbs: 0,
    kcal: 0,
    target_protein: 0,
    target_fat: 0,
    target_carbs: 0,
    target_kcal: 0,
  });
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

function pluralRu(count, one, few, many) {
  const abs = Math.abs(Number(count) || 0);
  const mod10 = abs % 10;
  const mod100 = abs % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
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
    food_search: "База",
    history: "История",
  }[source] || "Оценка";
}

function confidenceLabel(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return ` · ${Math.round(number * 100)}%`;
}

function entrySourceForParsed(source) {
  return {
    ai: "manual",
    photo: "ai_photo",
    barcode: "barcode",
    common: "food_search",
    food_search: "food_search",
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

function setTextWithPulse(node, value) {
  if (!node) return;
  const nextValue = String(value ?? "");
  const previousValue = node.dataset.lastTextValue;
  node.textContent = nextValue;
  node.dataset.lastTextValue = nextValue;
  if (previousValue === undefined || previousValue === nextValue) return;
  restartMicroAnimation(node, "value-pop");
}

function setProgressValue(node, property, value) {
  if (!node) return;
  const nextValue = String(value ?? "");
  const key = property.replace(/[^a-z0-9]/gi, "");
  const previousValue = node.dataset[`last${key}`];
  if (property.startsWith("--")) {
    node.style.setProperty(property, nextValue);
  } else {
    node.style[property] = nextValue;
  }
  node.dataset[`last${key}`] = nextValue;
  if (previousValue === undefined || previousValue === nextValue) return;
  restartMicroAnimation(node, "progress-pop");
}

function restartMicroAnimation(node, className) {
  node.classList.remove(className);
  void node.offsetWidth;
  node.classList.add(className);
  window.clearTimeout(node[`_${className}Timer`]);
  node[`_${className}Timer`] = window.setTimeout(() => {
    node.classList.remove(className);
    node[`_${className}Timer`] = null;
  }, 760);
}

function flashFoodPickAdded(button) {
  if (!button) return;
  const card = button.closest(".food-pick-card");
  card?.classList.add("is-added");
  button.classList.add("is-added");
  button.innerHTML = '<svg aria-hidden="true"><use href="#icon-check"></use></svg>';
  window.setTimeout(() => {
    card?.classList.remove("is-added");
    button.classList.remove("is-added");
    if (!button.disabled) {
      button.innerHTML = '<svg aria-hidden="true"><use href="#icon-plus"></use></svg>';
    }
  }, 1400);
}

function setButtonBusy(button, label) {
  if (!button) return;
  button.dataset.idleHtml = button.innerHTML;
  button.dataset.idleLabel = button.getAttribute("aria-label") || "";
  if (button.classList.contains("food-pick-add")) {
    button.classList.add("is-loading");
    button.setAttribute("aria-label", "Добавляю");
  } else {
    button.textContent = label;
  }
  button.disabled = true;
}

function isBusy(button) {
  return Boolean(button?.disabled);
}

function restoreButton(button) {
  if (!button) return;
  button.innerHTML = button.dataset.idleHtml || button.textContent;
  button.classList.remove("is-loading");
  if (button.dataset.idleLabel) {
    button.setAttribute("aria-label", button.dataset.idleLabel);
  } else {
    button.removeAttribute("aria-label");
  }
  button.disabled = false;
  delete button.dataset.idleHtml;
  delete button.dataset.idleLabel;
}
