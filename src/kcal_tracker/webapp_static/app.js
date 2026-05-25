const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const state = {
  today: null,
};

const nodes = {
  authWarning: document.querySelector("#auth-warning"),
  refresh: document.querySelector("#refresh"),
  hello: document.querySelector("#hello"),
  kcalLeft: document.querySelector("#kcal-left"),
  kcalTarget: document.querySelector("#kcal-target"),
  kcalPercent: document.querySelector("#kcal-percent"),
  kcalProgress: document.querySelector("#kcal-progress"),
  protein: document.querySelector("#protein"),
  fat: document.querySelector("#fat"),
  carbs: document.querySelector("#carbs"),
  water: document.querySelector("#water"),
  entries: document.querySelector("#entries"),
  foodForm: document.querySelector("#food-form"),
  toast: document.querySelector("#toast"),
  weightButton: document.querySelector("#weight-button"),
  weightValue: document.querySelector("#weight-value"),
  weightGoal: document.querySelector("#weight-goal"),
  openAdd: document.querySelector("#open-add"),
  addSheet: document.querySelector("#add-sheet"),
  closeAdd: document.querySelector("#close-add"),
  sheetBackdrop: document.querySelector("#sheet-backdrop"),
};

tg?.ready();
tg?.expand();

if (tg?.initDataUnsafe?.user?.first_name) {
  nodes.hello.textContent = `Привет, ${tg.initDataUnsafe.user.first_name}`;
}

if (!initData) {
  nodes.authWarning.classList.remove("hidden");
} else {
  loadToday();
}

nodes.refresh.addEventListener("click", loadToday);
nodes.openAdd.addEventListener("click", openSheet);
nodes.closeAdd.addEventListener("click", closeSheet);
nodes.sheetBackdrop.addEventListener("click", closeSheet);

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
  await loadToday();
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
  closeSheet();
  await loadToday();
  toast("Еда добавлена");
});

async function loadToday() {
  if (!initData) return;
  try {
    state.today = await api("/webapp/me/today");
    renderToday(state.today);
  } catch (error) {
    toast(error.message || "Не получилось обновить");
  }
}

function renderToday(data) {
  const diary = data.diary;
  const progress = diary.target_kcal > 0 ? Math.min(diary.kcal / diary.target_kcal, 1) : 0;
  nodes.kcalProgress.style.width = `${Math.round(progress * 100)}%`;
  nodes.kcalPercent.textContent = `${Math.round(progress * 100)}%`;
  const left = Math.round(diary.target_kcal - diary.kcal);
  nodes.kcalLeft.textContent = left >= 0 ? `${left} ккал осталось` : `+${Math.abs(left)} ккал`;
  nodes.kcalTarget.textContent = `${Math.round(diary.kcal)} / ${diary.target_kcal} ккал`;
  nodes.protein.textContent = `${Math.round(diary.protein)}/${Math.round(diary.target_protein)} г`;
  nodes.fat.textContent = `${Math.round(diary.fat)}/${Math.round(diary.target_fat)} г`;
  nodes.carbs.textContent = `${Math.round(diary.carbs)}/${Math.round(diary.target_carbs)} г`;
  nodes.water.textContent = `${data.water_ml} мл`;
  nodes.weightValue.textContent = data.latest_weight_kg ? `${formatNumber(data.latest_weight_kg)} кг` : "Записать";
  nodes.weightGoal.textContent = [
    data.weight_goal.forecast_text,
    data.latest_weight_kg ? `Сейчас ${formatNumber(data.latest_weight_kg)} кг.` : "",
  ].filter(Boolean).join(" ");

  if (!diary.entries.length) {
    nodes.entries.innerHTML = '<p class="empty-state">Сегодня пока пусто. Добавь первый приём еды.</p>';
    return;
  }
  nodes.entries.innerHTML = diary.entries.map((entry) => `
    <article class="entry">
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
    </article>
  `).join("");
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

function openSheet() {
  nodes.addSheet.classList.remove("hidden");
  nodes.addSheet.setAttribute("aria-hidden", "false");
  window.setTimeout(() => document.querySelector("#food-name")?.focus(), 40);
}

function closeSheet() {
  nodes.addSheet.classList.add("hidden");
  nodes.addSheet.setAttribute("aria-hidden", "true");
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

function toast(message) {
  nodes.toast.textContent = message;
  nodes.toast.classList.remove("hidden");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => nodes.toast.classList.add("hidden"), 2200);
}
