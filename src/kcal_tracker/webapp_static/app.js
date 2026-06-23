const {
  tg,
  initData,
  readAppCache,
  writeAppCache,
  api,
  apiForm,
  recordWebappEvent,
} = window.KcalAppCore;
const ONBOARDING_KEY = "kcal:onboarding:v2";
const PREMIUM_THEME_KEY = "kcal:premium-theme:v1";
const PREMIUM_THEME_PREVIEW_MS = 6500;
const TOUR_SAFE_GAP = 18;
const DEFAULT_START_PROMO = "START20";
const PREMIUM_THEMES = [
  {
    id: "system",
    title: "Kcal",
    subtitle: "чистая база",
  },
  {
    id: "aurora",
    title: "Aurora",
    subtitle: "зелень, лед и свет",
  },
  {
    id: "noir",
    title: "Noir",
    subtitle: "тёмный премиум",
  },
  {
    id: "berry",
    title: "Berry",
    subtitle: "ягоды и спорт",
  },
  {
    id: "sunset",
    title: "Sunset",
    subtitle: "тёплый вечер",
  },
];
const PAYWALL_VARIANTS = [
  {
    id: "features",
    title: null,
    subtitle: null,
  },
  {
    id: "speed",
    title: "Считай еду за секунды",
    subtitle: "Premium убирает ручной поиск: фото, текст и уточнения превращаются в готовую запись быстрее, чем открывать таблицы калорий.",
  },
  {
    id: "real-life",
    title: "Для упаковок, кафе и доставки",
    subtitle: "Premium помогает с едой, которую неудобно считать руками: упаковки, домашние блюда, кафе, доставка и поправки по порции.",
  },
];
const FALLBACK_SUBSCRIPTION_PLANS = [
  {
    code: "basic",
    title: "Старт",
    rub: 299,
    stars: 499,
    daily_limit: 30,
  },
  {
    code: "unlimited",
    title: "Безлимит",
    rub: 699,
    stars: 1199,
    daily_limit: null,
  },
];

const AI_LIMIT_CONTEXTS = {
  text: {
    badge: "Текстовый AI",
    title: "Продолжить разбор еды текстом",
    subtitle: "Premium вернёт разбор обычным языком: блюда, порции, соусы и примерное КБЖУ без ручного поиска.",
    benefits: [
      ["Фразы как в чате", "«омлет с сыром и кофе» сразу превращается в запись"],
      ["Порции и БЖУ", "AI подсказывает граммы, калории, белки, жиры и углеводы"],
      ["Уточнения после разбора", "можно поправить соус, вес или состав блюда"],
    ],
    manualLabel: "Добавить вручную",
  },
  photo: {
    badge: "Фото еды",
    title: "Распознавать блюда по фото",
    subtitle: "Premium помогает быстро заносить кафе, доставку и домашние блюда, когда искать продукт вручную неудобно.",
    benefits: [
      ["Фото блюда", "кафе, доставка и тарелки с несколькими продуктами"],
      ["Подсказка к фото", "можно добавить текст, если на снимке есть нюансы"],
      ["Проверка перед записью", "результат остаётся редактируемым перед сохранением"],
    ],
    manualLabel: "Ввести значения",
  },
  search: {
    badge: "AI-поиск",
    title: "Найти продукт через AI",
    subtitle: "Если базы не хватает, Premium предложит продукт и порцию для проверки вместо пустого результата.",
    benefits: [
      ["Редкие продукты", "бренды, готовые блюда и формулировки из меню"],
      ["Порция из запроса", "«латте 300 мл» или «сырники 2 шт» учитываются сразу"],
      ["Быстрая запись", "найденный вариант можно сохранить одним нажатием"],
    ],
    manualLabel: "Заполнить вручную",
  },
  refine: {
    badge: "AI-уточнение",
    title: "Уточнять порции и состав",
    subtitle: "Premium позволяет поправлять AI-оценку диалогом, не пересобирая блюдо заново.",
    benefits: [
      ["Поправка порции", "например: «было 250 г, без масла»"],
      ["Сложные блюда", "соусы, гарниры и состав можно уточнить после первого результата"],
      ["Меньше пересчётов", "AI обновляет КБЖУ в уже найденной записи"],
    ],
    manualLabel: "Исправить вручную",
  },
  default: {
    badge: "AI-доступ",
    title: "Пробные AI-запросы закончились",
    subtitle: "Premium вернёт фото, текст, поиск и уточнения для сложной еды. Ручной ввод остаётся бесплатным.",
    benefits: [
      ["Фото еды", "кафе, доставка, сложные блюда"],
      ["Текст и голос", "обычным языком без таблиц"],
      ["Уточнения", "порции, соусы, граммы и БЖУ"],
    ],
    manualLabel: "Пока вручную",
  },
};

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
  foodSearchAiLoading: false,
  subscriptionPlans: [],
  subscriptionPromo: null,
  selectedSubscriptionPlan: "basic",
  selectedSubscriptionMethod: "sbp",
  subscriptionExpiresAt: null,
  onboardingOpenedFoodSheet: false,
  subscriptionDaysLeft: null,
  entryHighlightKeys: new Set(),
  entryHighlightTimer: null,
  loadingAll: false,
  hasActiveSubscription: false,
  aiUsage: null,
  appTheme: readStoredPremiumTheme(),
  themePreviewTimer: null,
  onboardingAutoChecked: false,
  onboardingStep: 0,
  reviewFeedbackSent: null,
  parsedFoodsInitialSnapshot: "",
  paywallVariant: null,
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
  kcalCompare: document.querySelector("#kcal-compare"),
  firstDayNudge: document.querySelector("#first-day-nudge"),
  firstDayCaption: document.querySelector("#first-day-caption"),
  firstDayTitle: document.querySelector("#first-day-title"),
  firstDayText: document.querySelector("#first-day-text"),
  firstDayAction: document.querySelector("#first-day-action"),
  weeklyMissionsTrigger: document.querySelector("#weekly-missions-trigger"),
  shareDay: document.querySelector("#share-day"),
  weeklyMissionsCount: document.querySelector("#weekly-missions-count"),
  weeklyMissionsSheet: document.querySelector("#weekly-missions-sheet"),
  weeklyMissionsClose: document.querySelector("#weekly-missions-close"),
  weeklyMissions: document.querySelector("#weekly-missions"),
  weeklyMissionsCaption: document.querySelector("#weekly-missions-caption"),
  weeklyMissionsTitle: document.querySelector("#weekly-missions-title"),
  weeklyMissionsText: document.querySelector("#weekly-missions-text"),
  weeklyMissionsList: document.querySelector("#weekly-missions-list"),
  weeklyMissionsClaim: document.querySelector("#weekly-missions-claim"),
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
  weekStyleInsight: document.querySelector("#week-style-insight"),
  tomorrowMicroPlan: document.querySelector("#tomorrow-micro-plan"),
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
  subscriptionFlow: document.querySelector("#subscription-flow"),
  subscriptionStatus: document.querySelector("#subscription-status"),
  subscriptionStatusLabel: document.querySelector("#subscription-status-label"),
  subscriptionStatusTitle: document.querySelector("#subscription-status-title"),
  subscriptionStatusText: document.querySelector("#subscription-status-text"),
  subscriptionStatusMeta: document.querySelector("#subscription-status-meta"),
  subscriptionCaption: document.querySelector("#subscription-caption"),
  subscriptionTitle: document.querySelector("#subscription-title"),
  subscriptionSubtitle: document.querySelector("#subscription-subtitle"),
  subscriptionPlans: document.querySelector("#subscription-plans"),
  subscriptionConnect: document.querySelector("#subscription-connect"),
  subscriptionHint: document.querySelector("#subscription-hint"),
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
  entryEditThumb: document.querySelector("#entry-edit-thumb"),
  entryEditSummaryKcal: document.querySelector("#entry-edit-summary-kcal"),
  entryEditSummaryWeight: document.querySelector("#entry-edit-summary-weight"),
  openBot: document.querySelector("#open-bot"),
  exportFood: document.querySelector("#export-food"),
  onboarding: document.querySelector("#onboarding"),
  onboardingSpotlight: document.querySelector("#onboarding-spotlight"),
  onboardingClose: document.querySelector("#onboarding-close"),
  onboardingSkip: document.querySelector("#onboarding-skip"),
  onboardingBack: document.querySelector("#onboarding-back"),
  onboardingNext: document.querySelector("#onboarding-next"),
  onboardingStart: document.querySelector("#onboarding-start"),
  onboardingStep: document.querySelector("#onboarding-step"),
  onboardingTotal: document.querySelector("#onboarding-total"),
  onboardingProgress: document.querySelector("#onboarding-progress"),
  onboardingTitle: document.querySelector("#onboarding-title"),
  onboardingText: document.querySelector("#onboarding-text"),
  onboardingMenu: document.querySelector("#onboarding-menu"),
  onboardingTips: document.querySelector("#onboarding-tips"),
  profileOnboarding: document.querySelector("#profile-onboarding"),
  profileOnboardingForm: document.querySelector("#profile-onboarding-form"),
  profileOnboardingClose: document.querySelector("#profile-onboarding-close"),
  setupGoal: document.querySelector("#setup-goal"),
  setupGender: document.querySelector("#setup-gender"),
  setupAge: document.querySelector("#setup-age"),
  setupHeight: document.querySelector("#setup-height"),
  setupWeight: document.querySelector("#setup-weight"),
  setupActivity: document.querySelector("#setup-activity"),
  setupTargetWeight: document.querySelector("#setup-target-weight"),
  dayShareSheet: document.querySelector("#day-share-sheet"),
  dayShareClose: document.querySelector("#day-share-close"),
  dayShareCard: document.querySelector("#day-share-card"),
  themeGrid: document.querySelector("#theme-grid"),
  themeStatus: document.querySelector("#theme-status"),
};

const onboardingSteps = [
  {
    title: "Сегодня — главный экран",
    text: "Здесь видно, сколько осталось калорий, что уже съедено и как идёт день. Начинай отсюда, когда хочешь быстро понять ситуацию.",
    target: ".calorie-card",
  },
  {
    title: "Еда добавляется отсюда",
    text: "Кнопка открывает фото, AI-описание, штрихкод, поиск и ручной ввод. Первый успех здесь: добавь один продукт и сразу увидишь день.",
    target: ".tab-bar [data-view='food']",
  },
  {
    title: "Поиск и штрихкод",
    text: "Введи продукт, блюдо или бренд в поиск. Для упаковки можно нажать сканер справа и найти товар по штрихкоду.",
    target: ".food-search-form",
    fallbackTarget: ".add-mode-actions",
    sheet: "food-add",
  },
  {
    title: "AI — когда проще описать",
    text: "Напиши обычной фразой, что съел: AI разберёт блюдо, порцию и КБЖУ. Хорошо подходит для домашней еды и кафе.",
    target: "[data-add-mode='ai']",
    fallbackTarget: ".add-mode-actions",
    sheet: "food-add",
  },
  {
    title: "Фото — самый быстрый путь",
    text: "Сфотографируй блюдо или упаковку. Если на фото бренд, этикетка или состав — лучше держать их в кадре.",
    target: "[data-add-mode='photo']",
    fallbackTarget: ".add-mode-actions",
    sheet: "food-add",
  },
  {
    title: "Точно — для своих цифр",
    text: "Если калории и БЖУ уже известны, введи их вручную. Это самый предсказуемый способ для готовых продуктов.",
    target: "[data-add-mode='manual']",
    fallbackTarget: ".add-mode-actions",
    sheet: "food-add",
  },
  {
    title: "Миссии живут в шапке",
    text: "Тут недельные задания и бонус AI. Нажми на значок, чтобы открыть прогресс и забрать награду, когда она доступна.",
    target: "#weekly-missions-trigger",
    fallbackTarget: ".today-actions",
  },
  {
    title: "Прогресс показывает неделю",
    text: "Смотри не только один день, а ритм недели: средние калории, попадание в цель и тренд веса.",
    target: ".tab-bar [data-view='progress']",
  },
  {
    title: "Ещё — настройки и помощь",
    text: "Там подписка, лимиты AI, экспорт, поддержка, напоминания и повтор этого обучения.",
    target: ".tab-bar [data-view='more']",
  },
  {
    title: "Сделай первую запись",
    text: "Лучший старт — занести один приём пищи любым способом. После сохранения дневник покажет остаток калорий и прогресс дня.",
    target: ".add-mode-actions",
    fallbackTarget: ".tab-bar [data-view='food']",
    sheet: "food-add",
    cta: "Добавить еду",
  },
];

tg?.ready();
tg?.expand();
tg?.setHeaderColor?.("secondary_bg_color");
applyThemeMode();
applyPremiumTheme(state.appTheme);
applyTelegramSafeArea();
["themeChanged", "viewportChanged", "safeAreaChanged", "contentSafeAreaChanged"].forEach((eventName) => {
  try {
    tg?.onEvent?.(eventName, () => {
      if (eventName === "themeChanged") applyThemeMode();
      applyTelegramSafeArea();
    });
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
nodes.shareDay?.addEventListener("click", openDayShareSheet);
nodes.weeklyMissionsTrigger?.addEventListener("click", openWeeklyMissionsSheet);
nodes.weeklyMissionsClose?.addEventListener("click", closeWeeklyMissionsSheet);
nodes.weeklyMissionsSheet?.addEventListener("click", (event) => {
  if (event.target === nodes.weeklyMissionsSheet) closeWeeklyMissionsSheet();
});
nodes.weeklyMissionsClaim?.addEventListener("click", claimWeeklyMissionBonus);
nodes.dayShareClose?.addEventListener("click", closeDayShareSheet);
nodes.dayShareSheet?.addEventListener("click", (event) => {
  if (event.target === nodes.dayShareSheet) closeDayShareSheet();
});
document.addEventListener("click", (event) => {
  const shortcut = event.target.closest("[data-view-shortcut]");
  if (shortcut) {
    closeWeeklyMissionsSheet();
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
  const reviewFeedback = event.target.closest("[data-review-feedback]");
  if (reviewFeedback) {
    handleReviewFeedback(reviewFeedback.dataset.reviewFeedback, reviewFeedback);
    return;
  }
  const themeChoice = event.target.closest("[data-theme-choice]");
  if (themeChoice) {
    selectPremiumTheme(themeChoice.dataset.themeChoice);
    return;
  }
  const moreAction = event.target.closest("[data-more-action]");
  if (moreAction) {
    handleMoreAction(moreAction.dataset.moreAction);
    return;
  }
  const planButton = event.target.closest("[data-subscription-plan]");
  if (planButton) {
    selectSubscriptionPlan(planButton.dataset.subscriptionPlan);
    recordWebappEvent("webapp_subscription_plan_select", {
      source: "subscription",
      details: { plan: planButton.dataset.subscriptionPlan || "" },
    });
    return;
  }
  const methodButton = event.target.closest("[data-subscription-method]");
  if (methodButton) {
    selectSubscriptionMethod(methodButton.dataset.subscriptionMethod);
    recordWebappEvent("webapp_subscription_method_select", {
      source: "subscription",
      details: { method: methodButton.dataset.subscriptionMethod || "" },
    });
  }
});
nodes.repeatYesterday.addEventListener("click", repeatYesterday);
nodes.openBot.addEventListener("click", openBotFromWebApp);
nodes.exportFood.addEventListener("click", exportFood);
nodes.subscriptionConnect?.addEventListener("click", connectSubscription);
nodes.firstDayAction?.addEventListener("click", handleSmartNudgeAction);
nodes.onboardingClose?.addEventListener("click", () => closeOnboarding({ remember: true }));
nodes.onboardingSkip?.addEventListener("click", () => closeOnboarding({ remember: true }));
nodes.onboardingBack?.addEventListener("click", () => setOnboardingStep(state.onboardingStep - 1));
nodes.onboardingNext?.addEventListener("click", () => setOnboardingStep(state.onboardingStep + 1));
nodes.onboardingStart?.addEventListener("click", () => {
  recordWebappEvent("webapp_onboarding_start_food", {
    source: "tour",
    details: {
      final_step: state.onboardingStep,
      total_steps: onboardingSteps.length,
    },
  });
  closeOnboarding({ remember: true });
  openFoodAddSheet();
});
nodes.onboardingMenu?.addEventListener("click", (event) => {
  const item = event.target.closest("[data-onboarding-step]");
  if (!item) return;
  setOnboardingStep(Number(item.dataset.onboardingStep));
});
nodes.profileOnboardingClose?.addEventListener("click", closeProfileOnboarding);
nodes.profileOnboardingForm?.addEventListener("submit", completeProfileOnboarding);
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
nodes.foodPreviewList.addEventListener("focusin", captureParsedFoodWeightBase);
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
[nodes.entryEditKcal, nodes.entryEditWeight, nodes.entryEditProtein, nodes.entryEditFat, nodes.entryEditCarbs].forEach((input) => {
  input.addEventListener("input", updateEntryEditSummary);
});
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
  setAiProcessing(nodes.foodTextForm, true);
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
    recordWebappEvent("webapp_ai_failed", {
      source: "text",
      query: text,
      details: { status: error.status || 0 },
    });
    if (error.status === 402) showPremiumUpsell("AI разбор еды", "text");
  } finally {
    setAiProcessing(nodes.foodTextForm, false);
    restoreButton(submit);
  }
}

async function parseFoodPhoto() {
  const files = Array.from(nodes.foodPhotoInput.files || []).slice(0, 6);
  if (!files.length) return;
  const hint = nodes.foodPhotoHint.value.trim() || nodes.foodText.value.trim();
  const form = new FormData();
  const endpoint = files.length > 1 ? "/webapp/me/food/parse-photos" : "/webapp/me/food/parse-photo";
  files.forEach((file) => form.append(files.length > 1 ? "images" : "image", file));
  if (hint) form.append("text_hint", hint);

  if (isBusy(nodes.foodPhotoButton)) return;
  setButtonBusy(nodes.foodPhotoButton, files.length > 1 ? "Распознаю фото..." : "Распознаю...");
  const photoPanel = nodes.foodPhotoButton.closest("[data-add-panel]");
  setAiProcessing(photoPanel, true);
  try {
    const result = await apiForm(endpoint, form);
    setParsedFoods(result);
    const hasBrandMatch = result.foods?.some((food) => food.source_label === "База бренда");
    const unverifiedPackagedCount = result.foods?.filter((food) => food.source_label === "Проверь бренд").length || 0;
    if (hasBrandMatch) {
      recordWebappEvent("webapp_brand_lookup", {
        source: "photo",
        query: hint,
        details: { photos: files.length, matched: true },
      });
    }
    if (unverifiedPackagedCount) {
      recordWebappEvent("webapp_packaged_unverified", {
        source: "photo",
        query: hint,
        details: {
          photos: files.length,
          count: unverifiedPackagedCount,
          foods: compactQualityFoods(result.foods || []),
        },
      });
    }
    toast(hasBrandMatch ? "Нашёл продукт в базе брендов" : files.length > 1 ? "Фото распознаны" : "Фото распознано");
  } catch (error) {
    const message = error.status === 402
      ? "Лимит AI на сегодня закончился"
      : "Не получилось распознать фото";
    toast(message);
    recordWebappEvent("webapp_ai_failed", {
      source: "photo",
      query: hint,
      details: { status: error.status || 0, has_hint: Boolean(hint), photos: files.length },
    });
    if (error.status === 402) showPremiumUpsell("Распознавание фото", "photo");
  } finally {
    nodes.foodPhotoInput.value = "";
    setAiProcessing(photoPanel, false);
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
    recordWebappEvent("webapp_barcode_failed", {
      source: "barcode_photo",
      details: { status: error.status || 0 },
    });
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
    recordWebappEvent("webapp_barcode_failed", {
      source: "barcode_code",
      query: code,
      details: { status: error.status || 0 },
    });
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
    state.foodSearchAiLoading = false;
    state.foodSearchResults = result.foods.map(normalizeParsedFood);
    renderFoodPickList(nodes.foodSearchResults, state.foodSearchResults, {
      source: result.source,
      emptyText: "Ничего не нашлось. Можно разобрать через AI.",
      query,
      showAiSearch: !state.foodSearchResults.some((food) => food.is_ai_suggestion),
    });
    switchAddMode("browse");
  } catch (error) {
    if (requestId !== state.searchRequestId) return;
    state.foodSearchResults = [];
    const text = error.status === 401
      ? "Открой mini-app из Telegram, чтобы поиск получил доступ к дневнику."
      : "Поиск не сработал. Попробуй AI или штрихкод.";
    renderFoodPickList(nodes.foodSearchResults, [], {
      emptyText: text,
      query,
      showAiSearch: error.status !== 401,
    });
    recordWebappEvent("webapp_search_failed", {
      source: "food_search",
      query,
      details: { status: error.status || 0 },
    });
  } finally {
    if (requestId === state.searchRequestId) {
      nodes.foodSearchResults.removeAttribute("aria-busy");
    }
  }
}

function clearFoodSearch(clearInput = true) {
  if (clearInput) nodes.foodSearch.value = "";
  state.searchRequestId += 1;
  state.foodSearchAiLoading = false;
  state.foodSearchResults = [];
  nodes.foodSearchSection.classList.add("hidden");
  nodes.foodSearchResults.innerHTML = "";
  nodes.foodSearchResults.removeAttribute("aria-busy");
}

function handleFoodPick(event) {
  const aiSearchButton = event.target.closest("[data-food-search-ai]");
  if (aiSearchButton) {
    searchFoodWithAi(aiSearchButton);
    return;
  }
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
  const wasFirstFood = !state.today?.diary?.entries?.length;
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
    recordWebappEvent("webapp_food_saved", {
      source,
      query: food.name || null,
      details: { foods_count: 1, meal_type: state.selectedMeal },
    });
    if (wasFirstFood) {
      recordWebappEvent("webapp_first_food_saved", {
        source,
        details: { foods_count: 1 },
      });
    }
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
  state.reviewFeedbackSent = null;
  state.parsedFoodsInitialSnapshot = parsedFoodsSnapshot(state.parsedFoods);
  document.querySelectorAll("[data-review-feedback]").forEach((button) => button.classList.remove("active"));
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
  const wasFirstFood = !state.today?.diary?.entries?.length;
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
    recordWebappEvent("webapp_food_saved", {
      source: state.parsedFoodSource,
      query: foods.map((food) => food.name).filter(Boolean).join(", ").slice(0, 240),
      details: {
        foods_count: foods.length,
        meal_type: state.selectedMeal,
        foods: compactQualityFoods(foods),
      },
    });
    recordAiSavedEvent(foods);
    if (wasFirstFood) {
      recordWebappEvent("webapp_first_food_saved", {
        source: state.parsedFoodSource,
        details: { foods_count: foods.length },
      });
    }
  } catch {
    toast("Не получилось сохранить еду");
  } finally {
    restoreButton(nodes.saveParsedFood);
  }
}

function recordAiSavedEvent(foods) {
  if (!isAiAssistedSource(state.parsedFoodSource)) return;
  const edited = state.reviewFeedbackSent === "adjust" || parsedFoodsSnapshot(foods) !== state.parsedFoodsInitialSnapshot;
  recordWebappEvent(edited ? "webapp_ai_saved_edited" : "webapp_ai_saved_unedited", {
    source: state.parsedFoodSource,
    query: foods.map((food) => food.name).filter(Boolean).join(", ").slice(0, 240),
    details: {
      foods_count: foods.length,
      meal_type: state.selectedMeal,
      review_feedback: state.reviewFeedbackSent,
      foods: compactQualityFoods(foods),
    },
  });
}

function isAiAssistedSource(source) {
  return source === "ai" || source === "photo";
}

function parsedFoodsSnapshot(foods) {
  return JSON.stringify(foods.map((food) => ({
    name: food.name || "",
    kcal: roundedSnapshotNumber(food.kcal),
    protein: roundedSnapshotNumber(food.protein),
    fat: roundedSnapshotNumber(food.fat),
    carbs: roundedSnapshotNumber(food.carbs),
    weight_g: roundedSnapshotNumber(food.weight_g),
  })));
}

function roundedSnapshotNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return Math.round(Number(value) * 10) / 10;
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
    recordWebappEvent("webapp_food_saved", {
      source: "manual",
      query: payload.name,
      details: { foods_count: 1, meal_type: payload.meal_type },
    });
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
  const button = nodes.promoForm.querySelector("button[type='submit']");
  await validatePromoCode(code, button);
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

renderThemePicker();

if (!initData) {
  nodes.authWarning.classList.remove("hidden");
  renderEmptyApp();
  loadSubscriptionPlans();
} else {
  renderCachedApp();
  loadAll();
  recordWebappEvent("webapp_open", {
    source: "app",
    details: {
      start_param: tg?.initDataUnsafe?.start_param || "",
      platform: tg?.platform || "",
    },
  });
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

function isDarkTheme() {
  return tg?.colorScheme === "dark" || window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyThemeMode() {
  const isDark = isDarkTheme();
  document.body.classList.toggle("theme-dark", isDark);
  syncTelegramThemeColor();
}

function syncTelegramThemeColor() {
  window.requestAnimationFrame(() => {
    const styles = window.getComputedStyle(document.body);
    const fallback = isDarkTheme() ? "#0d1117" : "#f3f6f8";
    const color = styles.getPropertyValue("--tg-bg-color").trim() || styles.getPropertyValue("--bg").trim() || fallback;
    tg?.setBackgroundColor?.(color);
  });
}

function readStoredPremiumTheme() {
  try {
    const value = localStorage.getItem(PREMIUM_THEME_KEY);
    return PREMIUM_THEMES.some((theme) => theme.id === value) ? value : "system";
  } catch {
    return "system";
  }
}

function writeStoredPremiumTheme(themeId) {
  try {
    localStorage.setItem(PREMIUM_THEME_KEY, themeId);
  } catch {
    // Storage can be unavailable in restricted webviews.
  }
}

function applyPremiumTheme(themeId) {
  const nextTheme = PREMIUM_THEMES.some((theme) => theme.id === themeId) ? themeId : "system";
  document.body.classList.remove("theme-previewing");
  document.body.classList.forEach((className) => {
    if (className.startsWith("premium-theme-")) {
      document.body.classList.remove(className);
    }
  });
  if (nextTheme !== "system") {
    document.body.classList.add(`premium-theme-${nextTheme}`);
  }
  document.body.dataset.appTheme = nextTheme;
  syncTelegramThemeColor();
}

function renderThemePicker() {
  if (!nodes.themeGrid) return;
  const activeTheme = state.hasActiveSubscription ? state.appTheme : document.body.dataset.appTheme || "system";
  nodes.themeGrid.innerHTML = PREMIUM_THEMES.map((theme) => {
    const active = theme.id === activeTheme;
    const locked = theme.id !== "system" && !state.hasActiveSubscription;
    return `
      <button
        class="theme-choice ${active ? "active" : ""} ${locked ? "locked" : ""}"
        type="button"
        data-theme-choice="${escapeHtml(theme.id)}"
        aria-pressed="${active ? "true" : "false"}"
      >
        <span class="theme-preview theme-preview-${escapeHtml(theme.id)}" aria-hidden="true">
          <i></i><i></i><i></i>
        </span>
        <strong>${escapeHtml(theme.title)}</strong>
        <em>${escapeHtml(locked ? "Premium" : theme.subtitle)}</em>
      </button>
    `;
  }).join("");
  if (nodes.themeStatus) {
    nodes.themeStatus.textContent = state.hasActiveSubscription
      ? "Выбери настроение интерфейса. Тема сохранится на этом устройстве."
      : "Нажми тему, чтобы увидеть preview. Постоянно сохраняется в Premium.";
  }
}

function selectPremiumTheme(themeId) {
  const theme = PREMIUM_THEMES.find((item) => item.id === themeId);
  if (!theme) return;
  if (!state.hasActiveSubscription && theme.id !== "system") {
    previewLockedTheme(theme);
    recordWebappEvent("webapp_theme_locked_click", {
      source: "theme",
      details: { theme: theme.id },
    });
    return;
  }
  window.clearTimeout(state.themePreviewTimer);
  state.appTheme = theme.id;
  applyPremiumTheme(state.appTheme);
  writeStoredPremiumTheme(state.appTheme);
  renderThemePicker();
  triggerSelectionHaptic();
  toast(theme.id === "system" ? "Вернул стандартную тему" : `Тема ${theme.title} включена`);
  recordWebappEvent("webapp_theme_select", {
    source: "theme",
    details: { theme: theme.id },
  });
}

function previewLockedTheme(theme) {
  window.clearTimeout(state.themePreviewTimer);
  applyPremiumTheme(theme.id);
  document.body.classList.add("theme-previewing");
  renderThemePicker();
  triggerSelectionHaptic();
  toast(`Preview: ${theme.title}. Сохранение в Premium`);
  state.themePreviewTimer = window.setTimeout(() => {
    applyPremiumTheme("system");
    document.body.classList.remove("theme-previewing");
    renderThemePicker();
  }, PREMIUM_THEME_PREVIEW_MS);
  window.setTimeout(() => openSubscriptionFlow({ highlight: true }), 720);
}

function triggerHaptic(style = "light") {
  try {
    tg?.HapticFeedback?.impactOccurred?.(style);
  } catch {
    // Haptics are optional and unavailable in local browsers.
  }
}

function triggerSelectionHaptic() {
  try {
    tg?.HapticFeedback?.selectionChanged?.();
  } catch {
    triggerHaptic("light");
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
    loadSubscriptionPlans(),
  ]);
  state.loadingAll = false;
  restoreButton(nodes.refresh);
  if (results.some((result) => result.status === "rejected")) {
    toast("Часть данных не загрузилась");
  }
}

async function loadToday() {
  state.today = await api("/webapp/me/today");
  writeAppCache("today", state.today);
  renderToday(state.today);
  maybeOpenOnboarding(state.today);
}

async function loadWeek() {
  state.week = await api("/webapp/me/week");
  writeAppCache("week", state.week);
  renderWeek(state.week);
}

async function loadBody() {
  state.body = await api("/webapp/me/body");
  writeAppCache("body", state.body);
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

async function loadSubscriptionPlans() {
  if (!initData) {
    state.subscriptionPlans = FALLBACK_SUBSCRIPTION_PLANS;
    renderSubscriptionPlans();
    return;
  }
  const data = await api("/webapp/me/subscription/plans");
  state.subscriptionPlans = data.plans || [];
  writeAppCache("subscriptionPlans", state.subscriptionPlans);
  if (!state.subscriptionPlans.some((plan) => plan.code === state.selectedSubscriptionPlan)) {
    state.selectedSubscriptionPlan = state.subscriptionPlans[0]?.code || "basic";
  }
  renderSubscriptionPlans();
}

function renderCachedApp() {
  const today = readAppCache("today", 4 * 60 * 60 * 1000);
  if (today) {
    state.today = today;
    renderToday(today);
  }
  const week = readAppCache("week", 4 * 60 * 60 * 1000);
  if (week) {
    state.week = week;
    renderWeek(week);
  }
  const body = readAppCache("body", 24 * 60 * 60 * 1000);
  if (body) {
    state.body = body;
    renderBody(body);
  }
  const plans = readAppCache("subscriptionPlans", 24 * 60 * 60 * 1000);
  if (plans) {
    state.subscriptionPlans = plans;
    renderSubscriptionPlans();
  }
}

function renderToday(data) {
  const diary = data.diary;
  state.hasActiveSubscription = Boolean(data.has_active_subscription);
  state.subscriptionExpiresAt = data.subscription_expires_at || null;
  state.subscriptionDaysLeft = data.subscription_days_left ?? null;
  state.aiUsage = data.ai_usage;
  document.body.classList.toggle("is-free-user", !state.hasActiveSubscription);
  document.body.classList.toggle("is-premium-user", state.hasActiveSubscription);
  if (!state.hasActiveSubscription && state.appTheme !== "system") {
    state.appTheme = "system";
    applyPremiumTheme(state.appTheme);
    writeStoredPremiumTheme(state.appTheme);
  }
  renderThemePicker();
  renderSubscriptionCopy();
  renderSubscriptionStatus();
  renderAiBadges();
  const progress = diary.target_kcal > 0 ? Math.min(diary.kcal / diary.target_kcal, 1) : 0;
  setProgressValue(nodes.kcalProgress, "width", `${Math.round(progress * 100)}%`);
  setTextWithPulse(nodes.kcalPercent, `${Math.round(progress * 100)}%`);
  const left = Math.round(diary.target_kcal - diary.kcal);
  setTextWithPulse(nodes.kcalEaten, Math.round(diary.kcal));
  setTextWithPulse(nodes.kcalBurned, Math.round(diary.activity_kcal));
  setTextWithPulse(nodes.kcalLeft, left >= 0 ? String(left) : `+${Math.abs(left)}`);
  setTextWithPulse(nodes.kcalTarget, `${Math.round(diary.kcal)} / ${diary.target_kcal} ккал`);
  renderKcalCompare(data);
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
  const aiUsageText = formatAiUsageValue(data.ai_usage);
  setTextWithPulse(nodes.aiUsage, aiUsageText);
  setTextWithPulse(nodes.moreAiCaption, formatAiUsageCaption(data.ai_usage));
  nodes.goalKind.value = data.weight_goal.goal || "maintain";
  nodes.goalWeight.value = data.weight_goal.target_weight_kg ? formatNumber(data.weight_goal.target_weight_kg) : "";
  nodes.goalPace.value = data.weight_goal.weekly_weight_change_kg ? formatNumber(data.weight_goal.weekly_weight_change_kg) : "";

  nodes.entries.innerHTML = renderMealDiary(diary.entries);
  renderWeeklyMissions(data.weekly_missions);
  renderSmartNudge(data);
}

function renderKcalCompare(data) {
  if (!nodes.kcalCompare) return;
  const todayKcal = Number(data?.diary?.kcal || 0);
  const yesterday = data?.yesterday_diary;
  const yesterdayKcal = Number(yesterday?.kcal || 0);
  const yesterdayEntries = Number(yesterday?.entries?.length || 0);
  let text = "";
  let tone = "neutral";
  if (todayKcal > 0 && yesterdayEntries > 0) {
    const delta = Math.round(todayKcal - yesterdayKcal);
    if (Math.abs(delta) < 80) {
      text = "Почти как вчера по калориям";
    } else if (delta > 0) {
      text = `На ${delta} ккал больше, чем вчера`;
      tone = "up";
    } else {
      text = `На ${Math.abs(delta)} ккал меньше, чем вчера`;
      tone = "down";
    }
  } else if (todayKcal > 0) {
    text = "Сегодня уже есть первая запись";
  } else if (yesterdayEntries > 0) {
    text = "Можно повторить вчерашнюю еду";
  }
  nodes.kcalCompare.className = `kcal-compare ${text ? "" : "hidden"} tone-${tone}`.trim();
  nodes.kcalCompare.textContent = text;
}

async function openDayShareSheet() {
  if (!state.today?.diary) {
    toast("День ещё загружается");
    return;
  }
  renderDayShareCard(state.today);
  nodes.dayShareSheet?.classList.remove("hidden");
  lockPageScroll("day-share");
  triggerHaptic("light");
}

function closeDayShareSheet() {
  nodes.dayShareSheet?.classList.add("hidden");
  unlockPageScroll("day-share");
}

function renderDayShareCard(data) {
  if (!nodes.dayShareCard) return;
  const diary = data.diary || {};
  const entries = [...(diary.entries || [])].sort((left, right) => Number(right.kcal || 0) - Number(left.kcal || 0));
  const kcal = Math.round(Number(diary.kcal || 0));
  const target = Math.max(Math.round(Number(diary.target_kcal || 0)), 1);
  const left = target - kcal;
  const progress = Math.max(0, Math.min(kcal / target, 1));
  const progressPercent = Math.round(progress * 100);
  const date = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(new Date());
  const foodLines = entries.slice(0, 3).map((entry) => ({
    name: entry.name || "Еда",
    kcal: Math.round(Number(entry.kcal || 0)),
    emoji: entry.emoji || "•",
  }));
  const summaryTitle = foodLines.length ? "Главное за день" : "День только начинается";
  const summaryText = foodLines.length
    ? foodLines
      .map((entry) => `${entry.emoji} ${entry.name} · ${entry.kcal} ккал`)
      .join("\n")
    : "Запиши первый приём пищи — карточка станет живее.";
  const stats = [
    ["Белки", `${Math.round(Number(diary.protein || 0))} г`],
    ["Жиры", `${Math.round(Number(diary.fat || 0))} г`],
    ["Углеводы", `${Math.round(Number(diary.carbs || 0))} г`],
    ["Вода", `${Math.round(Number(data.water_ml || 0))} мл`],
  ];
  nodes.dayShareCard.innerHTML = `
    <div class="day-share-card-top">
      <strong>Kcal</strong>
      <span>${escapeHtml(date)}</span>
    </div>
    <div class="day-share-card-main">
      <span>Мой день</span>
      <div>
        <strong>${left >= 0 ? formatNumber(left) : `+${formatNumber(Math.abs(left))}`}</strong>
        <em>${left >= 0 ? "ккал осталось" : "ккал выше цели"}</em>
      </div>
    </div>
    <div class="day-share-card-progress" aria-label="Прогресс калорий">
      <span style="width: ${progressPercent}%"></span>
    </div>
    <div class="day-share-card-kcal">${formatNumber(kcal)} / ${formatNumber(target)} ккал</div>
    <div class="day-share-card-stats">
      ${stats.map(([label, value]) => `
        <div>
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("")}
    </div>
    <div class="day-share-card-summary">
      <strong>${escapeHtml(summaryTitle)}</strong>
      <p>${escapeHtml(summaryText).replace(/\n/g, "<br>")}</p>
    </div>
    <footer>
      <strong>Сделано в @trackerkcal_bot</strong>
      <span>Дневник питания в Telegram</span>
    </footer>
  `;
}

function renderSmartNudge(data) {
  if (!nodes.firstDayNudge) return;
  const entriesCount = Number(data?.diary?.entries?.length || 0);
  const waterMl = Number(data?.water_ml || 0);
  const diary = data?.diary || {};
  const target = Number(diary.target_kcal || 0);
  const kcal = Number(diary.kcal || 0);
  const progress = target > 0 ? kcal / target : 0;
  const aiRemaining = Number(data?.ai_usage?.trial_remaining ?? data?.ai_usage?.remaining_today ?? 0);
  const freeUser = !Boolean(data?.has_active_subscription);
  const missions = data?.weekly_missions;
  let nudge = null;

  if (missions?.eligible_for_bonus) {
    nudge = {
      caption: "Бонус недели",
      title: "+1 день AI уже доступен",
      text: "Ты выполнил 2 недельные миссии. Забери бонус прямо в Mini App и продолжай с AI.",
      action: "claim-weekly-bonus",
      button: "Забрать",
    };
  } else if (!entriesCount) {
    nudge = {
      caption: "Первый шаг",
      title: "Добавь первую еду",
      text: data?.onboarding_completed
        ? "После первой записи дневник покажет остаток калорий, БЖУ и что можно съесть дальше."
        : "Настрой профиль и добавь первый приём пищи. Так день сразу станет понятным.",
      action: "add-food",
      button: "Добавить еду",
    };
  } else if (entriesCount === 1) {
    const left = Math.round(target - kcal);
    nudge = {
      caption: "Закрепить день",
      title: "Первая запись уже есть",
      text: left > 0
        ? `Добавь следующий приём или воду: осталось примерно ${left} ккал.`
        : "Проверь день и при необходимости добавь активность или уточни порции.",
      action: "add-food",
      button: "Добавить ещё",
    };
  } else if (waterMl < 500) {
    nudge = {
      caption: "Маленькая привычка",
      title: "Добавь воду",
      text: "Еда уже в дневнике. Отметь стакан воды, чтобы день выглядел полнее и серия привычки не терялась.",
      action: "body",
      button: "+ вода",
    };
  } else if (freeUser && aiRemaining <= 0) {
    nudge = {
      caption: "AI на сегодня",
      title: "Продолжить без ручного поиска",
      text: "Пробные AI-запросы закончились. Premium вернёт фото, текст и уточнения для сложной еды.",
      action: "subscription",
      button: "Открыть Premium",
    };
  } else if (progress >= 0.75 || entriesCount >= 3) {
    nudge = {
      caption: "Итог дня",
      title: "Посмотри прогресс",
      text: "День уже наполнен. Проверь неделю, чтобы понять, попадаешь ли в цель без лишней строгости.",
      action: "progress",
      button: "Прогресс",
    };
  }

  nodes.firstDayNudge.classList.toggle("hidden", !nudge);
  if (!nudge) return;
  nodes.firstDayCaption.textContent = nudge.caption;
  nodes.firstDayTitle.textContent = nudge.title;
  nodes.firstDayText.textContent = nudge.text;
  nodes.firstDayAction.textContent = nudge.button;
  nodes.firstDayAction.dataset.nudgeAction = nudge.action;
}

function handleSmartNudgeAction() {
  const action = nodes.firstDayAction?.dataset.nudgeAction || "add-food";
  recordWebappEvent("webapp_smart_nudge_click", {
    source: "today",
    details: {
      action,
      entries_count: Number(state.today?.diary?.entries?.length || 0),
      onboarding_completed: Boolean(state.today?.onboarding_completed),
    },
  });
  if (action === "add-food") {
    openFoodAddSheet();
    return;
  }
  if (action === "body") {
    switchView("body");
    return;
  }
  if (action === "progress") {
    switchView("progress");
    return;
  }
  if (action === "claim-weekly-bonus") {
    claimWeeklyMissionBonus();
    return;
  }
  if (action === "subscription") {
    openSubscriptionFlow();
    return;
  }
  openFoodAddSheet();
}

function openWeeklyMissionsSheet() {
  if (!nodes.weeklyMissionsSheet || nodes.weeklyMissionsTrigger?.classList.contains("hidden")) return;
  nodes.weeklyMissionsSheet.classList.remove("hidden");
  document.body.classList.add("sheet-open");
  triggerHaptic("light");
}

function closeWeeklyMissionsSheet() {
  if (!nodes.weeklyMissionsSheet || nodes.weeklyMissionsSheet.classList.contains("hidden")) return;
  nodes.weeklyMissionsSheet.classList.add("hidden");
  document.body.classList.remove("sheet-open");
}

function renderWeeklyMissions(missions) {
  if (!nodes.weeklyMissions || !nodes.weeklyMissionsList) return;
  const items = missions?.missions || [];
  nodes.weeklyMissions.classList.toggle("hidden", !items.length);
  nodes.weeklyMissionsTrigger?.classList.toggle("hidden", !items.length);
  if (!items.length) {
    closeWeeklyMissionsSheet();
    return;
  }

  const completedCount = Number(missions.completed_count || 0);
  const missionTarget = 2;
  if (nodes.weeklyMissionsCount) {
    nodes.weeklyMissionsCount.textContent = missions.bonus_claimed
      ? "OK"
      : `${Math.min(completedCount, missionTarget)}/${missionTarget}`;
  }
  nodes.weeklyMissionsTrigger?.classList.toggle("is-eligible", Boolean(missions.eligible_for_bonus));
  nodes.weeklyMissionsTrigger?.classList.toggle("is-claimed", Boolean(missions.bonus_claimed));
  nodes.weeklyMissions.classList.toggle("is-eligible", Boolean(missions.eligible_for_bonus));
  nodes.weeklyMissions.classList.toggle("is-claimed", Boolean(missions.bonus_claimed));
  nodes.weeklyMissionsCaption.textContent = missions.bonus_claimed
    ? "Бонус забран"
    : missions.eligible_for_bonus ? "Бонус доступен" : `Готово ${completedCount}/2`;
  nodes.weeklyMissionsTitle.textContent = missions.bonus_claimed
    ? "Недельный бонус уже у тебя"
    : missions.eligible_for_bonus ? "+1 день AI за неделю" : "Миссии недели";
  nodes.weeklyMissionsText.textContent = missions.bonus_claimed
    ? "Продолжай серию: новые миссии уже засчитываются до конца недели."
    : missions.eligible_for_bonus
      ? "Выполнено 2 миссии. Забери бонус AI прямо здесь."
      : "Выполни 2 миссии, чтобы открыть +1 день AI и закрепить привычку.";
  if (nodes.weeklyMissionsClaim) {
    nodes.weeklyMissionsClaim.classList.toggle("hidden", !missions.eligible_for_bonus || missions.bonus_claimed);
    nodes.weeklyMissionsClaim.disabled = !missions.eligible_for_bonus || missions.bonus_claimed;
  }

  const active = [...items]
    .sort((left, right) => Number(left.completed) - Number(right.completed))
    .slice(0, 3);
  nodes.weeklyMissionsList.innerHTML = active.map((mission) => {
    const current = Math.max(Number(mission.current || 0), 0);
    const target = Math.max(Number(mission.target || 0), 1);
    const progress = Math.min(Math.round((current / target) * 100), 100);
    return `
      <article class="weekly-mission ${mission.completed ? "completed" : ""}">
        <div>
          <strong>${escapeHtml(mission.title)}</strong>
          <span>${Math.min(current, target)}/${target}</span>
        </div>
        <i aria-hidden="true"><b style="width:${progress}%"></b></i>
      </article>
    `;
  }).join("");
}

async function claimWeeklyMissionBonus() {
  const button = nodes.weeklyMissionsClaim;
  if (!button || isBusy(button)) return;
  if (!initData) {
    toast("Бонус можно забрать внутри Telegram mini-app");
    return;
  }
  setButtonBusy(button, "Добавляю...");
  try {
    const today = await api("/webapp/me/weekly-missions/claim", { method: "POST" });
    state.today = today;
    renderToday(today);
    recordWebappEvent("webapp_weekly_bonus_claim", {
      source: "weekly_missions",
      details: {
        completed_count: today.weekly_missions?.completed_count || 0,
        subscription_days_left: today.subscription_days_left,
      },
    });
    toast("+1 день AI добавлен");
  } catch (error) {
    toast(error.status === 409 ? "Бонус пока недоступен" : "Не получилось забрать бонус");
    await loadToday().catch(() => {});
  } finally {
    restoreButton(button);
  }
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
          <span>${escapeHtml(emptyMealTitle(meal.id))}</span>
          <em>${escapeHtml(emptyMealText(meal.id))}</em>
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

function emptyMealTitle(mealId) {
  const current = mealIdForNow();
  if (mealId === current) {
    return {
      breakfast: "Добавить завтрак",
      lunch: "Добавить обед",
      dinner: "Добавить ужин",
      snack: "Добавить перекус",
    }[mealId] || "Добавить еду";
  }
  return "Пока пусто";
}

function emptyMealText(mealId) {
  const current = mealIdForNow();
  const activeSuffix = mealId === current ? " Сейчас самое время." : "";
  return {
    breakfast: `Кофе, яйца, каша или фото упаковки.${activeSuffix}`,
    lunch: `Сфоткай тарелку или найди продукт по бренду.${activeSuffix}`,
    dinner: `Закрой день: блюдо, доставка или ручные цифры.${activeSuffix}`,
    snack: `Батончик, йогурт, фрукт или напиток.${activeSuffix}`,
  }[mealId] || "Добавь запись любым способом.";
}

function renderFoodEntry(entry) {
  const highlightClass = isEntryHighlighted(entry) ? " is-highlighted" : "";
  return `
    <article class="entry food-card${highlightClass}">
      ${renderFoodThumb(entry)}
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
          <button type="button" data-edit-entry="${entry.id}" aria-label="Изменить ${escapeHtml(entry.name)}">
            Изменить
          </button>
          <button type="button" data-favorite-entry="${entry.id}" aria-label="Сохранить ${escapeHtml(entry.name)} в шаблоны">
            В шаблон
          </button>
          <button type="button" data-delete-entry="${entry.id}" aria-label="Удалить ${escapeHtml(entry.name)}">
            Удалить
          </button>
        </div>
      </div>
    </article>
  `;
}

function renderFoodThumb(food) {
  if (isActivePhotoThumb(food)) {
    return `
      <div class="food-thumb has-photo">
        <img src="${escapeHtml(food.photo_thumb_data_url)}" alt="" loading="lazy" />
      </div>
    `;
  }
  return `<div class="food-thumb">${escapeHtml(food.emoji || foodInitial(food.name))}</div>`;
}

function isActivePhotoThumb(food) {
  if (!food?.photo_thumb_data_url || !food.photo_thumb_expires_at) return false;
  const expiresAt = new Date(food.photo_thumb_expires_at).getTime();
  return Number.isFinite(expiresAt) && expiresAt > Date.now();
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
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
  setTextWithPulse(nodes.weekStyleInsight, data.personal_style_insight || "Пока стиль питания только собирается.");
  setTextWithPulse(nodes.tomorrowMicroPlan, data.tomorrow_micro_plan || "Завтра начни с одной честной записи.");
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
    state.subscriptionPromo = null;
    nodes.promoStatus.textContent = "Промокод не найден или уже закончился";
    nodes.promoResult.innerHTML = "";
    renderSubscriptionPlans();
    toast("Промокод не применился");
    return;
  }

  state.subscriptionPromo = result;
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
  renderSubscriptionPlans();
  toast("Промокод применён");
}

async function validatePromoCode(code, button) {
  if (!code) {
    toast("Введи промокод");
    return false;
  }
  if (button && isBusy(button)) return false;
  if (button) setButtonBusy(button, "Проверяю...");
  try {
    const result = await api("/webapp/me/promos/validate", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    renderPromo(result);
    recordWebappEvent("webapp_promo_apply", {
      source: "subscription",
      query: code,
      details: {
        valid: Boolean(result.valid),
        discount_percent: result.discount_percent || 0,
      },
    });
    if (result.valid) openSubscriptionFlow({ highlight: false });
    return Boolean(result.valid);
  } catch {
    toast("Не получилось проверить промокод");
    return false;
  } finally {
    if (button) restoreButton(button);
  }
}

function renderSubscriptionPlans() {
  if (!nodes.subscriptionPlans) return;
  renderSubscriptionCopy();
  renderSubscriptionStatus();
  const plans = subscriptionPlansForDisplay();
  if (!plans.length) {
    nodes.subscriptionPlans.innerHTML = '<div class="empty-state">Тарифы загружаются...</div>';
    return;
  }
  nodes.subscriptionPlans.innerHTML = plans.map((plan) => {
    const active = plan.code === state.selectedSubscriptionPlan;
    const limit = plan.daily_limit ? `${plan.daily_limit} AI в день` : "без дневного лимита";
    const accent = plan.code === "unlimited" ? "Максимум" : "Старт";
    return `
      <button class="subscription-plan-card ${active ? "active" : ""}" type="button" data-subscription-plan="${escapeHtml(plan.code)}">
        <span>${escapeHtml(accent)}</span>
        <strong>${escapeHtml(plan.title)}</strong>
        <p>${escapeHtml(limit)}</p>
        <b>${plan.rub} ₽ <em>или ${plan.stars} ⭐</em></b>
      </button>
    `;
  }).join("");
  renderSubscriptionMethodState();
}

function subscriptionPlansForDisplay() {
  return state.subscriptionPromo?.valid && state.subscriptionPromo.plans?.length
    ? state.subscriptionPromo.plans
    : state.subscriptionPlans;
}

function selectSubscriptionPlan(planCode) {
  if (!planCode) return;
  state.selectedSubscriptionPlan = planCode;
  renderSubscriptionPlans();
  triggerSelectionHaptic();
}

function selectSubscriptionMethod(method) {
  if (!["sbp", "auto", "stars"].includes(method)) return;
  state.selectedSubscriptionMethod = method;
  renderSubscriptionMethodState();
  triggerSelectionHaptic();
}

function renderSubscriptionMethodState() {
  document.querySelectorAll("[data-subscription-method]").forEach((button) => {
    button.classList.toggle("active", button.dataset.subscriptionMethod === state.selectedSubscriptionMethod);
  });
  const plan = subscriptionPlansForDisplay().find((item) => item.code === state.selectedSubscriptionPlan);
  if (!nodes.subscriptionHint || !plan) return;
  const methodText = {
    sbp: "СБП",
    auto: "карта/SberPay",
    stars: "звёзды Telegram",
  }[state.selectedSubscriptionMethod];
  const actionText = state.hasActiveSubscription ? "продление" : "подключение";
  nodes.subscriptionHint.textContent = `Откроем бота: ${plan.title}, ${methodText}. Там создастся счёт на ${actionText}.`;
}

function renderSubscriptionCopy() {
  const isRenewal = state.hasActiveSubscription;
  if (nodes.subscriptionCaption) {
    nodes.subscriptionCaption.textContent = isRenewal ? "Продление" : "Подключение";
  }
  if (nodes.subscriptionTitle) {
    nodes.subscriptionTitle.textContent = isRenewal ? "Продлите подписку" : "Выберите подписку";
  }
  if (nodes.subscriptionSubtitle) {
    nodes.subscriptionSubtitle.textContent = isRenewal
      ? "Выберите тариф и способ оплаты. Новый срок добавится к текущей подписке."
      : `Тариф, промокод и способ оплаты. Для первого запуска попробуй ${DEFAULT_START_PROMO}.`;
  }
  if (nodes.subscriptionConnect) {
    nodes.subscriptionConnect.textContent = isRenewal ? "Продолжить продление" : "Продолжить подключение";
  }
}

function renderSubscriptionStatus() {
  if (!nodes.subscriptionStatus) return;
  const isActive = state.hasActiveSubscription;
  const isExpiring = isActive && Number(state.subscriptionDaysLeft ?? 99) <= 2;
  const expiresText = state.subscriptionExpiresAt
    ? formatDateTime(state.subscriptionExpiresAt)
    : "";
  nodes.subscriptionStatus.classList.toggle("is-active", isActive);
  nodes.subscriptionStatus.classList.toggle("is-expiring", isExpiring);
  nodes.subscriptionStatusLabel.textContent = isExpiring
    ? "Скоро закончится"
    : isActive ? "Premium активен" : "Premium";
  nodes.subscriptionStatusTitle.textContent = isExpiring
    ? "Premium скоро закончится"
    : isActive
      ? "Подписка работает"
      : "AI для дневника питания";
  nodes.subscriptionStatusText.textContent = isExpiring
    ? "Продлите заранее: новый срок добавится к текущему, оставшиеся дни не пропадут."
    : isActive
      ? "Фото, текст, голос и уточнения уже доступны. Продление добавит новый срок к текущему."
      : "Фото, текст, голос и уточнения помогают вести дневник без ручного поиска.";
  nodes.subscriptionStatusMeta.innerHTML = isActive
    ? `
      <span><b>${escapeHtml(expiresText)}</b><em>активна до</em></span>
      <span><b>${state.subscriptionDaysLeft ?? "—"}</b><em>дней осталось</em></span>
      <span><b>${escapeHtml(formatAiUsageCaption(state.aiUsage))}</b><em>AI сегодня</em></span>
    `
    : `
      <span><b>${escapeHtml(formatAiUsageValue(state.aiUsage))}</b><em>пробные AI</em></span>
      <span><b>30 дней</b><em>срок тарифа</em></span>
      <span><b>ручной ввод</b><em>остаётся бесплатным</em></span>
    `;
}

function renderAiBadges() {
  const text = state.hasActiveSubscription
    ? "Premium"
    : `AI ${formatAiUsageValue(state.aiUsage)}`;
  document.querySelectorAll(".premium-badge").forEach((badge) => {
    badge.textContent = text;
  });
}

async function connectSubscription() {
  const plan = subscriptionPlansForDisplay().find((item) => item.code === state.selectedSubscriptionPlan);
  if (!plan) {
    toast("Тарифы ещё загружаются");
    return;
  }
  await recordWebappEvent("webapp_payment_start", {
    source: "subscription",
    details: {
      plan: plan.code,
      method: state.selectedSubscriptionMethod,
      price_rub: plan.rub,
      price_stars: plan.stars,
      promo: state.subscriptionPromo?.valid ? state.subscriptionPromo.code : "",
      renewal: state.hasActiveSubscription,
    },
  });
  if (nodes.subscriptionHint) {
    nodes.subscriptionHint.textContent =
      "Открываю бота для оплаты. После успешной оплаты Premium включится автоматически; " +
      "если не откроется за минуту, нажми «Проверить оплату» в боте.";
  }
  toast("Открываю бота для оплаты");
  openBotFromWebApp(`subscription_${plan.code}_${state.selectedSubscriptionMethod}`);
}

function formatAiUsageValue(usage) {
  if (!usage) return "0 / 0";
  if (usage.is_trial || !state.hasActiveSubscription) {
    const trialLimit = Number(usage.trial_limit || 3);
    const fallbackUsed = Number(usage.used_today || 0);
    const fallbackRemaining = Math.max(trialLimit - fallbackUsed, 0);
    const remaining = Math.max(Number(usage.trial_remaining ?? fallbackRemaining), 0);
    return `${remaining} / ${trialLimit}`;
  }
  return usage.daily_limit
    ? `${usage.used_today} / ${usage.daily_limit}`
    : `${usage.used_today} / ∞`;
}

function formatAiUsageCaption(usage) {
  if (!usage) return "загрузка";
  if (usage.is_trial || !state.hasActiveSubscription) {
    const trialLimit = Number(usage.trial_limit || 3);
    const fallbackUsed = Number(usage.used_today || 0);
    const fallbackRemaining = Math.max(trialLimit - fallbackUsed, 0);
    const remaining = Math.max(Number(usage.trial_remaining ?? fallbackRemaining), 0);
    return remaining ? `${remaining} пробных осталось` : "пробные закончились";
  }
  return usage.daily_limit
    ? `${Math.max(usage.daily_limit - usage.used_today, 0)} осталось`
    : "без дневного лимита";
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
  const aiCard = options.showAiSearch ? renderFoodSearchAiCard(options.query || nodes.foodSearch?.value || "") : "";
  if (!foods.length) {
    container.innerHTML = aiCard || `<div class="empty-state">${escapeHtml(options.emptyText || "Пока пусто.")}</div>`;
    return;
  }
  const listName = source === "history" && container === nodes.foodAddFavoritesList
    ? "favorites"
    : source === "history"
      ? "frequent"
      : "search";
  container.innerHTML = foods.map((food, index) => {
    const impact = foodPickImpact(food);
    const label = food.source_label || sourceLabel(source);
    const aiClass = food.is_ai_suggestion ? " is-ai-suggestion" : "";
    return `
      <article class="food-pick-card${aiClass}">
        <button class="food-pick-main" type="button" data-pick-edit="${index}" data-pick-index="${index}" data-pick-source="${listName}" data-entry-source="${source}">
          <strong>${escapeHtml(food.name)} <small class="food-source-badge">${escapeHtml(label)}</small></strong>
          <span>${Math.round(food.kcal || 0)} ккал${food.weight_g ? ` · ${formatNumber(food.weight_g)} г` : ""}</span>
          <em>Б ${formatNumber(food.protein || 0)} · Ж ${formatNumber(food.fat || 0)} · У ${formatNumber(food.carbs || 0)}</em>
          ${food.is_ai_suggestion ? '<small class="food-impact ai">AI-оценка, проверь перед сохранением</small>' : ""}
          ${impact ? `<small class="food-impact ${impact.kind}">${escapeHtml(impact.text)}</small>` : ""}
        </button>
        <button class="food-pick-add" type="button" data-pick-add="${index}" data-pick-index="${index}" data-pick-source="${listName}" data-entry-source="${source}" aria-label="Добавить ${escapeHtml(food.name)}">
          <svg aria-hidden="true"><use href="#icon-plus"></use></svg>
        </button>
      </article>
    `;
  }).join("") + aiCard;
}

function renderFoodSearchAiCard(query) {
  const text = String(query || "").trim();
  if (text.length < 4) return "";
  if (state.foodSearchAiLoading) {
    return `
      <article class="food-pick-card food-ai-search-card is-loading" aria-live="polite">
        <div class="food-ai-search-orb">AI</div>
        <div class="food-ai-search-copy">
          <strong>Ищу через AI <span class="premium-badge">Premium</span></strong>
          <span>${escapeHtml(text)}</span>
          <em>Проверяю КБЖУ и порцию</em>
        </div>
      </article>
    `;
  }
  return `
    <article class="food-pick-card food-ai-search-card" data-food-search-ai>
      <button class="food-ai-search-button" type="button" data-food-search-ai>
        <div class="food-ai-search-orb">AI</div>
        <div class="food-ai-search-copy">
          <strong>Найти через AI <span class="premium-badge">Premium</span></strong>
          <span>${escapeHtml(text)}</span>
          <em>Если базы мало, AI предложит продукт для проверки</em>
        </div>
        <i>→</i>
      </button>
    </article>
  `;
}

async function searchFoodWithAi(trigger = null) {
  const query = nodes.foodSearch.value.trim();
  if (query.length < 4 || state.foodSearchAiLoading) return;
  if (!initData) {
    toast("AI-поиск работает внутри Telegram mini-app");
    return;
  }
  trigger?.classList.add("is-pressed");
  const requestId = ++state.searchRequestId;
  state.foodSearchAiLoading = true;
  nodes.foodSearchSection.classList.remove("hidden");
  renderFoodPickList(nodes.foodSearchResults, state.foodSearchResults, {
    source: "food_search",
    query,
    showAiSearch: true,
  });
  nodes.foodSearchResults.setAttribute("aria-busy", "true");
  triggerHaptic("light");
  try {
    const result = await api(`/webapp/me/food/search?query=${encodeURIComponent(query)}&force_ai=true`);
    if (requestId !== state.searchRequestId) return;
    state.foodSearchAiLoading = false;
    state.foodSearchResults = result.foods.map(normalizeParsedFood);
    renderFoodPickList(nodes.foodSearchResults, state.foodSearchResults, {
      source: result.source,
      query,
      showAiSearch: !state.foodSearchResults.some((food) => food.is_ai_suggestion),
      emptyText: "AI тоже не нашёл уверенный вариант. Попробуй описать порцию подробнее.",
    });
    if (result.ai_used) {
      toast("AI предложил вариант");
    }
  } catch (error) {
    if (requestId !== state.searchRequestId) return;
    state.foodSearchAiLoading = false;
    renderFoodPickList(nodes.foodSearchResults, state.foodSearchResults, {
      source: "food_search",
      query,
      showAiSearch: true,
      emptyText: "AI-поиск не сработал. Попробуй позже.",
    });
    toast(error.status === 402 ? "Лимит AI на сегодня закончился" : "AI-поиск не сработал");
    recordWebappEvent(error.status === 402 ? "webapp_paywall_open" : "webapp_ai_failed", {
      source: "food_search_ai",
      query,
      details: { status: error.status || 0 },
    });
    if (error.status === 402) showPremiumUpsell("AI-поиск по еде", "search");
  } finally {
    trigger?.classList.remove("is-pressed");
    if (requestId === state.searchRequestId) {
      nodes.foodSearchResults.removeAttribute("aria-busy");
    }
  }
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
      ${renderFoodThumb(food)}
      <div class="food-content">
        <div class="entry-main">
          <strong>${escapeHtml(food.name || "Еда")}</strong>
          <b class="parsed-food-kcal">${Math.round(food.kcal || 0)} ккал</b>
        </div>
        <div class="entry-meta">
          <span class="parsed-food-weight">${food.weight_g ? `${formatNumber(food.weight_g)} г` : "без граммовки"}</span>
          <span class="parsed-food-protein">${Math.round(food.protein || 0)}Б</span>
          <span class="parsed-food-fat">${Math.round(food.fat || 0)}Ж</span>
          <span class="parsed-food-carbs">${Math.round(food.carbs || 0)}У</span>
          <span>${escapeHtml(food.source_label || sourceLabel(result.source))}${confidenceLabel(food.confidence)}</span>
        </div>
        <div class="entry-actions parsed-entry-actions">
          <button type="button" data-toggle-parsed="${index}">${state.expandedParsedFood === index ? "Свернуть" : "Изменить"}</button>
          <button type="button" data-remove-parsed="${index}" aria-label="Удалить ${escapeHtml(food.name)}">Удалить</button>
        </div>
        ${renderPackagedVerificationNote(food)}
        <div class="parsed-food-editor review-edit-card" ${state.expandedParsedFood === index ? "" : "hidden"}>
          <label class="review-edit-field review-name-field">
            <span>Название</span>
            <input data-field="name" value="${escapeHtml(food.name)}" aria-label="Название" />
          </label>
          <div class="preview-summary review-preview-summary">
            <strong>${Math.round(food.kcal || 0)} ккал</strong>
            <span>${food.weight_g ? `${formatNumber(food.weight_g)} г` : "граммы не указаны"}</span>
          </div>
          <div class="review-edit-row">
            <label class="review-edit-field"><span>ккал</span><input data-field="kcal" inputmode="decimal" value="${formatInput(food.kcal)}" /></label>
            <label class="review-edit-field"><span>граммы</span><input data-field="weight_g" inputmode="decimal" value="${formatInput(food.weight_g)}" /></label>
          </div>
          <div class="review-macro-grid" aria-label="БЖУ">
            <label class="review-edit-field macro-protein"><span>Б</span><input data-field="protein" inputmode="decimal" value="${formatInput(food.protein)}" /></label>
            <label class="review-edit-field macro-fat"><span>Ж</span><input data-field="fat" inputmode="decimal" value="${formatInput(food.fat)}" /></label>
            <label class="review-edit-field macro-carbs"><span>У</span><input data-field="carbs" inputmode="decimal" value="${formatInput(food.carbs)}" /></label>
          </div>
          <div class="portion-actions">
            <button type="button" data-index="${index}" data-scale-parsed="0.5">1/2</button>
            <button type="button" data-index="${index}" data-scale-parsed="1.25">+ порция</button>
            <button type="button" data-index="${index}" data-scale-parsed="2">x2</button>
          </div>
          ${food.advice ? `<p class="preview-advice">${escapeHtml(food.advice)}</p>` : ""}
          <details class="refine-details">
            <summary>Уточнить через AI <span class="premium-badge">Premium</span></summary>
            <form class="refine-form" data-refine-index="${index}">
              <input name="refinement" autocomplete="off" placeholder="Без хлеба, половина, ещё соус..." />
              <button class="secondary-button" type="submit">Уточнить <span class="premium-badge">Premium</span></button>
            </form>
          </details>
        </div>
      </div>
    </article>
  `).join("");
}

function renderPackagedVerificationNote(food) {
  if (!food?.packaged || food.source_label !== "Проверь бренд") return "";
  return `
    <div class="packaged-warning" role="status">
      <b>Упаковка не подтверждена базой</b>
      <span>Проверь название, вкус и КБЖУ на этикетке. Если есть штрихкод, лучше отсканировать его.</span>
    </div>
  `;
}

function handleReviewFeedback(kind, button) {
  const eventType = {
    accept: "webapp_ai_accept",
    adjust: "webapp_ai_adjust",
    reject: "webapp_ai_reject",
  }[kind];
  if (!eventType || state.reviewFeedbackSent === kind) return;
  state.reviewFeedbackSent = kind;
  document.querySelectorAll("[data-review-feedback]").forEach((item) => {
    item.classList.toggle("active", item === button);
  });

  recordWebappEvent(eventType, {
    source: state.parsedFoodSource,
    query: state.parsedFoods.map((food) => food.name).filter(Boolean).join(", ").slice(0, 240),
    details: {
      foods_count: state.parsedFoods.length,
      min_confidence: minConfidence(state.parsedFoods),
      foods: compactQualityFoods(state.parsedFoods),
    },
  });

  if (kind === "accept") {
    toast("Отлично, сохраним это для качества AI");
    return;
  }
  if (kind === "adjust") {
    state.expandedParsedFood = state.parsedFoods.length === 1 ? 0 : state.expandedParsedFood;
    renderParsedFoods({ source: state.parsedFoodSource });
    toast("Поправь граммы или уточни через AI");
    return;
  }
  toast("Спасибо, учту как ошибку распознавания", {
    kind: "warning",
    actionLabel: "Заново",
    duration: 5200,
    onAction: () => {
      switchView(state.foodReviewReturnView || "today");
      openFoodAddSheet();
    },
  });
}

function minConfidence(foods) {
  const values = foods
    .map((food) => Number(food.confidence))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return null;
  return Math.round(Math.min(...values) * 100) / 100;
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
  nodes.entryEditThumb.classList.toggle("has-photo", isActivePhotoThumb(entry));
  nodes.entryEditThumb.innerHTML = isActivePhotoThumb(entry)
    ? `<img src="${escapeHtml(entry.photo_thumb_data_url)}" alt="" />`
    : escapeHtml(entry.emoji || foodInitial(entry.name));
  state.editingEntryBase = {
    weight_g: numberOrNull(entry.weight_g),
    kcal: numberOrNull(entry.kcal) ?? 0,
    protein: numberOrNull(entry.protein) ?? 0,
    fat: numberOrNull(entry.fat) ?? 0,
    carbs: numberOrNull(entry.carbs) ?? 0,
  };
  updateEntryEditSummary();
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
  recordWebappEvent("webapp_add_food_open", {
    source: "food_add",
    details: { active_view: state.activeView || "" },
  });
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
  updateEntryEditSummary();
}

function scaledValue(value, scale) {
  return Math.round(Number(value || 0) * scale * 10) / 10;
}

function updateEntryEditSummary() {
  const kcal = parseNumber(nodes.entryEditKcal.value);
  const weight = parseNumber(nodes.entryEditWeight.value);
  nodes.entryEditSummaryKcal.textContent = `${Math.round(kcal || 0)} ккал`;
  nodes.entryEditSummaryWeight.textContent = weight ? `${formatNumber(weight)} г` : "без граммовки";
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
  const entry = findTodayEntry(entryId);
  triggerHaptic("medium");
  toast("Точно удалить?", {
    kind: "warning",
    actionLabel: "Удалить",
    duration: 5200,
    onAction: () => confirmDeleteEntry(entryId, entry),
  });
}

async function confirmDeleteEntry(entryId, entry) {
  try {
    await api(`/webapp/me/entries/${entryId}`, { method: "DELETE" });
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent()]);
    toast("Продукт удален", {
      kind: "success",
      actionLabel: "Вернуть",
      duration: 5600,
      onAction: () => restoreDeletedEntry(entry),
    });
  } catch {
    toast("Не получилось удалить запись");
  }
}

async function restoreDeletedEntry(entry) {
  if (!entry) {
    toast("Не получилось вернуть");
    return;
  }
  const payload = deletedEntryPayload(entry);
  try {
    const restored = await api("/webapp/me/entries", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    markEntryHighlights([restored], payload.meal_type);
    await Promise.allSettled([loadToday(), loadWeek(), loadFrequent()]);
    switchView("today");
    toast("Продукт вернули");
  } catch {
    toast("Не получилось вернуть");
  }
}

function findTodayEntry(entryId) {
  const entries = state.today?.diary?.entries || [];
  return entries.find((entry) => Number(entry.id) === Number(entryId)) || null;
}

function deletedEntryPayload(entry) {
  return {
    name: String(entry.name || "").trim(),
    weight_g: numberOrNull(entry.weight_g),
    kcal: numberOrNull(entry.kcal) ?? 0,
    protein: numberOrNull(entry.protein) ?? 0,
    fat: numberOrNull(entry.fat) ?? 0,
    carbs: numberOrNull(entry.carbs) ?? 0,
    confidence: numberOrNull(entry.confidence),
    emoji: entry.emoji || null,
    advice: entry.advice || null,
    source_label: entry.source_label || null,
    catalog_id: Number.isFinite(Number(entry.catalog_id)) ? Number(entry.catalog_id) : null,
    is_ai_suggestion: Boolean(entry.is_ai_suggestion),
    trust_score: numberOrNull(entry.trust_score),
    photo_thumb_data_url: isActivePhotoThumb(entry) ? entry.photo_thumb_data_url : null,
    photo_thumb_expires_at: isActivePhotoThumb(entry) ? entry.photo_thumb_expires_at : null,
    source: "history",
    meal_type: mealIdForEntry(entry),
  };
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
  if (field === "name") {
    food.name = input.value.trim();
    return;
  }

  const nextValue = parseNumber(input.value);
  if (field === "weight_g") {
    updateParsedFoodWeight(food, nextValue, card);
    return;
  }

  food[field] = nextValue;
  updateParsedFoodCardDisplay(card, food);
}

function captureParsedFoodWeightBase(event) {
  const input = event.target.closest('[data-field="weight_g"]');
  if (!input) return;
  const card = input.closest("[data-index]");
  const index = Number(card?.dataset.index);
  const food = state.parsedFoods[index];
  if (!food) return;
  food._weightEditBase = {
    weight_g: numberOrNull(food.weight_g),
    kcal: numberOrNull(food.kcal) ?? 0,
    protein: numberOrNull(food.protein) ?? 0,
    fat: numberOrNull(food.fat) ?? 0,
    carbs: numberOrNull(food.carbs) ?? 0,
  };
}

function updateParsedFoodWeight(food, nextWeight, card) {
  const base = food._weightEditBase || food;
  const baseWeight = numberOrNull(base.weight_g);
  if (baseWeight && baseWeight > 0 && nextWeight && nextWeight > 0) {
    const scale = nextWeight / baseWeight;
    ["kcal", "protein", "fat", "carbs"].forEach((field) => {
      food[field] = scaledValue(base[field], scale);
      const fieldInput = card.querySelector(`[data-field="${field}"]`);
      if (fieldInput) fieldInput.value = formatInput(food[field]);
    });
  }
  food.weight_g = nextWeight;
  updateParsedFoodCardDisplay(card, food);
}

function updateParsedFoodCardDisplay(card, food) {
  const kcal = Math.round(food.kcal || 0);
  const weight = food.weight_g ? `${formatNumber(food.weight_g)} г` : "без граммовки";
  const reviewWeight = food.weight_g ? `${formatNumber(food.weight_g)} г` : "граммы не указаны";
  const setText = (selector, text) => {
    const node = card.querySelector(selector);
    if (node) node.textContent = text;
  };
  setText(".parsed-food-kcal", `${kcal} ккал`);
  setText(".parsed-food-weight", weight);
  setText(".parsed-food-protein", `${Math.round(food.protein || 0)}Б`);
  setText(".parsed-food-fat", `${Math.round(food.fat || 0)}Ж`);
  setText(".parsed-food-carbs", `${Math.round(food.carbs || 0)}У`);
  setText(".review-preview-summary strong", `${kcal} ккал`);
  setText(".review-preview-summary span", reviewWeight);
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
    if (error.status === 402) showPremiumUpsell("AI-уточнение еды", "refine");
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
    case "onboarding":
      openOnboarding({ force: true });
      return;
    case "subscription":
      openSubscriptionFlow();
      return;
    case "reminders":
      openBotFromWebApp("reminders");
      return;
    case "support":
      openBotFromWebApp("support");
      return;
    default:
      toast("Скоро добавим");
  }
}

function openBotFromWebApp(target = "landing") {
  const payloads = new Set(["landing", "subscription", "reminders", "support"]);
  const subscriptionPayload = /^subscription_(basic|unlimited)_(sbp|auto|stars)$/.test(target);
  const payload = payloads.has(target) || subscriptionPayload ? target : "landing";
  recordWebappEvent("webapp_bot_open", {
    source: "bot_link",
    details: { payload },
  });
  const url = `https://t.me/trackerkcal_bot?start=${payload}`;
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(url);
    window.setTimeout(() => tg.close(), 250);
    return;
  }
  if (tg) {
    tg.close();
    return;
  }
  window.location.href = url;
}

function openSubscriptionFlow(options = {}) {
  const { highlight = true } = options;
  closeAiLimitScreen();
  switchView("subscription");
  recordWebappEvent("webapp_subscription_view", {
    source: "subscription",
    details: {
      highlight,
      has_subscription: state.hasActiveSubscription,
      days_left: state.subscriptionDaysLeft ?? null,
    },
  });
  if (!state.subscriptionPlans.length) {
    loadSubscriptionPlans().catch(() => toast("Не получилось загрузить тарифы"));
  }
  renderSubscriptionStatus();
  renderSubscriptionCopy();
  if (highlight) {
    nodes.subscriptionFlow?.classList.add("is-highlighted");
    window.setTimeout(() => nodes.subscriptionFlow?.classList.remove("is-highlighted"), 1200);
  }
}

function showPremiumUpsell(feature = "Premium", context = "default") {
  closeFoodAddSheet();
  closeFoodReviewSheet();
  openAiLimitScreen(feature, context);
}

function paywallVariant() {
  const key = "kcal:paywall-variant:v1";
  const saved = window.localStorage?.getItem(key);
  const existing = PAYWALL_VARIANTS.find((variant) => variant.id === saved);
  if (existing) return existing;
  const telegramId = Number(tg?.initDataUnsafe?.user?.id || 0);
  const index = telegramId
    ? Math.abs(telegramId) % PAYWALL_VARIANTS.length
    : Math.floor(Math.random() * PAYWALL_VARIANTS.length);
  const variant = PAYWALL_VARIANTS[index] || PAYWALL_VARIANTS[0];
  try {
    window.localStorage?.setItem(key, variant.id);
  } catch {
    // localStorage can be unavailable in restricted webviews.
  }
  return variant;
}

function openAiLimitScreen(feature = "AI", context = "default") {
  const screen = ensureAiLimitScreen();
  const title = screen.querySelector("[data-ai-limit-title]");
  const subtitle = screen.querySelector("[data-ai-limit-subtitle]");
  const counter = screen.querySelector("[data-ai-limit-counter]");
  const benefits = screen.querySelector("[data-ai-limit-benefits]");
  const manual = screen.querySelector("[data-ai-limit-manual]");
  const usage = state.aiUsage;
  const remaining = Number(usage?.trial_remaining ?? usage?.remaining_today ?? 0);
  const copy = AI_LIMIT_CONTEXTS[context] || AI_LIMIT_CONTEXTS.default;
  const variant = paywallVariant();
  state.paywallVariant = variant.id;

  title.textContent = variant.title || (remaining <= 0
    ? copy.title
    : "Для этого действия нужна подписка");
  subtitle.textContent = variant.subtitle || (remaining <= 0
    ? copy.subtitle
    : `${feature} доступен в подписке: можно разбирать еду текстом, фото и уточнениями без ручного поиска.`);
  counter.textContent = usage?.is_trial
    ? `${formatAiUsageValue(usage)} пробных AI-запросов`
    : copy.badge;
  if (benefits) {
    benefits.innerHTML = copy.benefits.map(([heading, text]) => `
      <div><b>${escapeHtml(heading)}</b><span>${escapeHtml(text)}</span></div>
    `).join("");
  }
  if (manual) {
    manual.textContent = copy.manualLabel;
  }

  screen.classList.remove("hidden");
  document.body.classList.add("paywall-open");
  screen.querySelector("[data-ai-limit-subscribe]")?.focus({ preventScroll: true });
  recordWebappEvent("webapp_paywall_open", {
    source: "ai_limit",
    details: {
      feature,
      context,
      paywall_variant: variant.id,
      remaining_ai: remaining,
      has_subscription: state.hasActiveSubscription,
    },
  });
  toast("Открой подписку, чтобы продолжить с AI");
}

function closeAiLimitScreen() {
  document.querySelector("#ai-limit-screen")?.classList.add("hidden");
  document.body.classList.remove("paywall-open");
}

function ensureAiLimitScreen() {
  let screen = document.querySelector("#ai-limit-screen");
  if (screen) return screen;
  screen = document.createElement("section");
  screen.id = "ai-limit-screen";
  screen.className = "ai-limit-screen hidden";
  screen.setAttribute("aria-modal", "true");
  screen.setAttribute("role", "dialog");
  screen.innerHTML = `
    <div class="ai-limit-backdrop" data-ai-limit-close></div>
    <div class="ai-limit-panel">
      <button class="ai-limit-close" type="button" data-ai-limit-close aria-label="Закрыть">×</button>
      <div class="ai-limit-mark">AI</div>
      <span data-ai-limit-counter>Пробные запросы</span>
      <h2 data-ai-limit-title>Пробные AI-запросы закончились</h2>
      <p data-ai-limit-subtitle>Открой подписку, чтобы продолжить разбирать еду через AI.</p>
      <div class="ai-limit-benefits" data-ai-limit-benefits>
        <div><b>Фото еды</b><span>кафе, доставка, сложные блюда</span></div>
        <div><b>Текст и голос</b><span>обычным языком без таблиц</span></div>
        <div><b>Уточнения</b><span>порции, соусы, граммы и БЖУ</span></div>
      </div>
      <form class="ai-limit-promo" data-ai-limit-promo-form>
        <input data-ai-limit-promo-code autocomplete="off" placeholder="${DEFAULT_START_PROMO}" />
        <button class="secondary-button" type="submit">Применить</button>
      </form>
      <button class="primary-button" type="button" data-ai-limit-subscribe>Купить подписку</button>
      <button class="secondary-button" type="button" data-ai-limit-manual>Пока вручную</button>
    </div>
  `;
  screen.addEventListener("click", (event) => {
    if (event.target.closest("[data-ai-limit-subscribe]")) {
      recordWebappEvent("webapp_paywall_subscribe", {
        source: "ai_limit",
        details: {
          paywall_variant: state.paywallVariant || paywallVariant().id,
          remaining_ai: Number(state.aiUsage?.trial_remaining ?? state.aiUsage?.remaining_today ?? 0),
          has_subscription: state.hasActiveSubscription,
        },
      });
      openSubscriptionFlow();
      return;
    }
    if (event.target.closest("[data-ai-limit-manual]")) {
      recordWebappEvent("webapp_paywall_manual", {
        source: "ai_limit",
        details: {
          paywall_variant: state.paywallVariant || paywallVariant().id,
          remaining_ai: Number(state.aiUsage?.trial_remaining ?? state.aiUsage?.remaining_today ?? 0),
        },
      });
      closeAiLimitScreen();
      openFoodAddSheet();
      switchAddMode("manual");
      return;
    }
    if (event.target.closest("[data-ai-limit-close]")) {
      closeAiLimitScreen();
    }
  });
  screen.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-ai-limit-promo-form]");
    if (!form) return;
    event.preventDefault();
    const input = form.querySelector("[data-ai-limit-promo-code]");
    const button = form.querySelector("button[type='submit']");
    const ok = await validatePromoCode(input?.value.trim() || "", button);
    if (ok) closeAiLimitScreen();
  });
  document.body.append(screen);
  return screen;
}

function maybeOpenOnboarding(today = state.today) {
  if (state.onboardingAutoChecked) return;
  state.onboardingAutoChecked = true;
  if (today?.onboarding_completed) {
    window.setTimeout(() => openOnboarding(), 520);
    return;
  }
  window.setTimeout(() => openProfileOnboarding(), 420);
}

function openProfileOnboarding() {
  if (!nodes.profileOnboarding || state.today?.onboarding_completed) return;
  lockPageScroll("profile-onboarding");
  nodes.profileOnboarding.classList.remove("hidden");
  triggerHaptic("light");
}

function closeProfileOnboarding() {
  if (!nodes.profileOnboarding) return;
  nodes.profileOnboarding.classList.add("hidden");
  unlockPageScroll("profile-onboarding");
}

async function completeProfileOnboarding(event) {
  event.preventDefault();
  const payload = {
    goal: nodes.setupGoal.value,
    gender: nodes.setupGender.value,
    age: parseNumber(nodes.setupAge.value),
    height: parseNumber(nodes.setupHeight.value),
    weight: parseNumber(nodes.setupWeight.value),
    activity: nodes.setupActivity.value,
    target_weight_kg: parseNumber(nodes.setupTargetWeight.value),
    weekly_weight_change_kg: null,
  };
  if (!payload.age || !payload.height || !payload.weight) {
    toast("Заполни возраст, рост и вес");
    return;
  }
  if (payload.goal === "maintain") {
    payload.target_weight_kg = null;
  }
  const button = nodes.profileOnboardingForm.querySelector("button[type='submit']");
  if (isBusy(button)) return;
  setButtonBusy(button, "Сохраняю...");
  try {
    const today = await api("/webapp/me/onboarding", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.today = today;
    renderToday(today);
    closeProfileOnboarding();
    recordWebappEvent("webapp_onboarding_complete", {
      source: "profile_onboarding",
      details: {
        goal: payload.goal,
        activity: payload.activity,
        has_target_weight: Boolean(payload.target_weight_kg),
      },
    });
    await Promise.allSettled([loadWeek(), loadBody()]);
    toast("Профиль настроен");
    window.setTimeout(() => openOnboarding({ force: true }), 320);
  } catch {
    toast("Не получилось настроить профиль");
  } finally {
    restoreButton(button);
  }
}

function openOnboarding({ force = false, startStep = 0 } = {}) {
  if (!nodes.onboarding) return;
  if (!force && hasSeenOnboarding()) return;
  if (document.body.dataset.view !== "today") switchView("today");
  state.onboardingStep = Math.max(0, Math.min(onboardingSteps.length - 1, startStep));
  window.scrollTo({ top: 0, behavior: "auto" });
  lockPageScroll("onboarding");
  nodes.onboarding.classList.remove("hidden");
  renderOnboardingStep();
  window.addEventListener("resize", updateOnboardingTarget, { passive: true });
  window.addEventListener("orientationchange", updateOnboardingTarget, { passive: true });
  window.setTimeout(updateOnboardingTarget, 60);
  recordWebappEvent("webapp_onboarding_tour_open", {
    source: force ? "forced" : "auto",
    details: {
      start_step: state.onboardingStep,
      total_steps: onboardingSteps.length,
    },
  });
  triggerHaptic("light");
}

function closeOnboarding({ remember = false } = {}) {
  if (!nodes.onboarding) return;
  nodes.onboarding.classList.add("hidden");
  hideOnboardingFoodSheet();
  if (remember) markOnboardingSeen();
  window.removeEventListener("resize", updateOnboardingTarget);
  window.removeEventListener("orientationchange", updateOnboardingTarget);
  unlockPageScroll("onboarding");
}

function setOnboardingStep(step) {
  const max = onboardingSteps.length - 1;
  state.onboardingStep = Math.max(0, Math.min(max, step));
  renderOnboardingStep();
  triggerHaptic("light");
}

function renderOnboardingStep() {
  const total = onboardingSteps.length;
  const step = onboardingSteps[state.onboardingStep] || onboardingSteps[0];
  prepareOnboardingStep(step);
  const current = state.onboardingStep + 1;
  nodes.onboardingStep.textContent = current;
  nodes.onboardingTotal.textContent = total;
  nodes.onboardingProgress.style.width = `${(current / total) * 100}%`;
  nodes.onboardingTitle.textContent = step.title;
  nodes.onboardingText.textContent = step.text;
  nodes.onboardingBack.disabled = state.onboardingStep === 0;
  nodes.onboardingNext.classList.toggle("hidden", state.onboardingStep === total - 1);
  nodes.onboardingStart.classList.toggle("hidden", state.onboardingStep !== total - 1);
  if (nodes.onboardingStart) nodes.onboardingStart.textContent = step.cta || "Начать";
  nodes.onboardingMenu.innerHTML = onboardingSteps
    .map((item, index) => `
      <button type="button" data-onboarding-step="${index}" ${index === state.onboardingStep ? 'class="active"' : ""}>
        <span>${index + 1}</span>
        <b>${escapeHtml(item.title)}</b>
      </button>
    `)
    .join("");
  nodes.onboardingTips.innerHTML = "";
  window.requestAnimationFrame(() => window.requestAnimationFrame(updateOnboardingTarget));
}

function prepareOnboardingStep(step) {
  if (step.sheet === "food-add") {
    if (nodes.foodAddSheet?.classList.contains("hidden")) {
      state.onboardingOpenedFoodSheet = true;
      switchAddMode("browse");
      nodes.foodAddSheet.classList.remove("hidden");
    }
    nodes.foodAddSheet?.querySelector(".food-add-scroll")?.scrollTo({ top: 0, behavior: "auto" });
    return;
  }
  hideOnboardingFoodSheet();
}

function hideOnboardingFoodSheet() {
  if (!state.onboardingOpenedFoodSheet || !nodes.foodAddSheet) return;
  switchAddMode("browse");
  nodes.foodAddSheet.classList.add("hidden");
  state.onboardingOpenedFoodSheet = false;
}

function getOnboardingTarget(step, viewportWidth, viewportHeight) {
  const candidates = [step.target, step.fallbackTarget, ".calorie-card"].filter(Boolean);
  for (const selector of candidates) {
    const element = document.querySelector(selector);
    if (!element) continue;
    const rect = element.getBoundingClientRect();
    const isVisible =
      rect.width >= 2 &&
      rect.height >= 2 &&
      rect.right > 0 &&
      rect.bottom > 0 &&
      rect.left < viewportWidth &&
      rect.top < viewportHeight;
    if (isVisible) return { element, rect };
  }
  return null;
}

function updateOnboardingTarget() {
  if (!nodes.onboarding || nodes.onboarding.classList.contains("hidden")) return;
  const step = onboardingSteps[state.onboardingStep] || onboardingSteps[0];
  const panel = nodes.onboarding.querySelector(".onboarding-panel");
  if (!panel) return;

  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 390;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 720;
  const target = getOnboardingTarget(step, viewportWidth, viewportHeight);
  if (!target) return;
  const targetRect = target.rect;
  const inset = 10;
  const spotlightLeft = Math.max(inset, targetRect.left - inset);
  const spotlightTop = Math.max(inset, targetRect.top - inset);
  const spotlightRight = Math.min(viewportWidth - inset, targetRect.right + inset);
  const spotlightBottom = Math.min(viewportHeight - inset, targetRect.bottom + inset);
  const spotlightWidth = Math.max(44, spotlightRight - spotlightLeft);
  const spotlightHeight = Math.max(44, spotlightBottom - spotlightTop);

  nodes.onboardingSpotlight?.style.setProperty("--spotlight-left", `${spotlightLeft}px`);
  nodes.onboardingSpotlight?.style.setProperty("--spotlight-top", `${spotlightTop}px`);
  nodes.onboardingSpotlight?.style.setProperty("--spotlight-width", `${spotlightWidth}px`);
  nodes.onboardingSpotlight?.style.setProperty("--spotlight-height", `${spotlightHeight}px`);

  const panelWidth = Math.min(390, viewportWidth - 32);
  const measuredHeight = panel.offsetHeight || 238;
  const targetCenterX = targetRect.left + targetRect.width / 2;
  let panelLeft = targetCenterX - panelWidth / 2;
  panelLeft = Math.max(16, Math.min(panelLeft, viewportWidth - panelWidth - 16));

  const canPlaceBelow = targetRect.bottom + TOUR_SAFE_GAP + measuredHeight < viewportHeight - 16;
  const placeBelow = canPlaceBelow || targetRect.top < measuredHeight + TOUR_SAFE_GAP + 16;
  const panelTop = placeBelow
    ? Math.min(targetRect.bottom + TOUR_SAFE_GAP, viewportHeight - measuredHeight - 16)
    : Math.max(16, targetRect.top - measuredHeight - TOUR_SAFE_GAP);
  const arrowLeft = Math.max(28, Math.min(targetCenterX - panelLeft, panelWidth - 28));

  nodes.onboarding.classList.toggle("arrow-top", placeBelow);
  nodes.onboarding.classList.toggle("arrow-bottom", !placeBelow);
  panel.style.setProperty("--tour-panel-left", `${panelLeft}px`);
  panel.style.setProperty("--tour-panel-top", `${panelTop}px`);
  panel.style.setProperty("--tour-panel-width", `${panelWidth}px`);
  panel.style.setProperty("--tour-arrow-left", `${arrowLeft}px`);
}

function hasSeenOnboarding() {
  try {
    if (window.localStorage?.getItem(ONBOARDING_KEY) === "1") return true;
  } catch {
    // Storage can be unavailable in restricted webviews.
  }
  return document.cookie.split("; ").includes(`${ONBOARDING_KEY}=1`);
}

function markOnboardingSeen() {
  try {
    window.localStorage?.setItem(ONBOARDING_KEY, "1");
  } catch {
    // Storage can be unavailable in restricted webviews.
  }
  document.cookie = `${ONBOARDING_KEY}=1; max-age=31536000; path=/; samesite=lax`;
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

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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
    source_label: food.source_label || null,
    packaged: food.packaged === true,
    catalog_id: Number.isFinite(Number(food.catalog_id)) ? Number(food.catalog_id) : null,
    is_ai_suggestion: Boolean(food.is_ai_suggestion),
    trust_score: numberOrNull(food.trust_score),
    photo_thumb_data_url: isActivePhotoThumb(food) ? food.photo_thumb_data_url : null,
    photo_thumb_expires_at: isActivePhotoThumb(food) ? food.photo_thumb_expires_at : null,
  };
}

function compactQualityFoods(foods) {
  return foods.slice(0, 5).map((food) => ({
    name: String(food.name || "").trim().slice(0, 120),
    kcal: numberOrNull(food.kcal),
    protein: numberOrNull(food.protein),
    fat: numberOrNull(food.fat),
    carbs: numberOrNull(food.carbs),
    weight_g: numberOrNull(food.weight_g),
    confidence: numberOrNull(food.confidence),
    source_label: food.source_label || null,
    packaged: food.packaged === true,
    catalog_id: Number.isFinite(Number(food.catalog_id)) ? Number(food.catalog_id) : null,
  }));
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

function toast(message, options = {}) {
  const text = String(message || "").trim();
  const kind = options.kind || toastKind(text);
  const actionLabel = String(options.actionLabel || "").trim();
  nodes.toast.classList.remove("success", "warning", "info");
  nodes.toast.classList.add(kind);
  nodes.toast.classList.toggle("has-action", Boolean(actionLabel));
  nodes.toast.innerHTML = `
    <span class="toast-icon" aria-hidden="true">${toastIcon(kind)}</span>
    <span class="toast-text">${escapeHtml(text)}</span>
    ${actionLabel ? `<button class="toast-action" type="button" data-toast-action>${escapeHtml(actionLabel)}</button>` : ""}
  `;
  if (actionLabel && typeof options.onAction === "function") {
    nodes.toast.querySelector("[data-toast-action]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      if (button.disabled) return;
      button.disabled = true;
      triggerHaptic("medium");
      nodes.toast.classList.add("is-busy");
      try {
        await options.onAction();
      } finally {
        nodes.toast.classList.remove("is-busy");
      }
    }, { once: true });
  }
  nodes.toast.classList.remove("hidden");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => nodes.toast.classList.add("hidden"), options.duration || 2600);
}

function toastKind(message) {
  const text = message.toLowerCase();
  if (
    text.includes("не получилось")
    || text.includes("ошибка")
    || text.includes("лимит")
    || text.includes("законч")
    || text.includes("не найден")
    || text.includes("не сработ")
    || text.includes("попробуй")
    || text.includes("заполни")
    || text.includes("введи")
    || text.includes("напиши")
    || text.includes("нет ")
  ) {
    return "warning";
  }
  if (
    text.includes("добав")
    || text.includes("готов")
    || text.includes("сохран")
    || text.includes("обнов")
    || text.includes("найден")
    || text.includes("распознан")
    || text.includes("примен")
  ) {
    return "success";
  }
  return "info";
}

function toastIcon(kind) {
  if (kind === "success") return "✓";
  if (kind === "warning") return "!";
  return "i";
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

function setAiProcessing(container, active) {
  if (!container) return;
  container.classList.toggle("is-ai-processing", active);
  container.querySelector("[data-ai-processing]")?.classList.toggle("hidden", !active);
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
