const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const state = {
  today: null,
};

const nodes = {
  authWarning: document.querySelector("#auth-warning"),
  refresh: document.querySelector("#refresh"),
  kcalValue: document.querySelector("#kcal-value"),
  kcalLeft: document.querySelector("#kcal-left"),
  protein: document.querySelector("#protein"),
  fat: document.querySelector("#fat"),
  carbs: document.querySelector("#carbs"),
  water: document.querySelector("#water"),
  entries: document.querySelector("#entries"),
  foodForm: document.querySelector("#food-form"),
  toast: document.querySelector("#toast"),
  weightButton: document.querySelector("#weight-button"),
  weightGoal: document.querySelector("#weight-goal"),
};

tg?.ready();
tg?.expand();

if (!initData) {
  nodes.authWarning.classList.remove("hidden");
} else {
  loadToday();
}

nodes.refresh.addEventListener("click", loadToday);

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
  const progress = diary.target_kcal > 0 ? Math.min(diary.kcal / diary.target_kcal, 1) * 100 : 0;
  document.documentElement.style.setProperty("--progress", `${progress}%`);
  nodes.kcalValue.textContent = Math.round(diary.kcal);
  const left = Math.round(diary.target_kcal - diary.kcal);
  nodes.kcalLeft.textContent = left >= 0 ? `Осталось ${left} ккал` : `Выше цели на ${Math.abs(left)} ккал`;
  nodes.protein.textContent = `${Math.round(diary.protein)}/${Math.round(diary.target_protein)}`;
  nodes.fat.textContent = `${Math.round(diary.fat)}/${Math.round(diary.target_fat)}`;
  nodes.carbs.textContent = `${Math.round(diary.carbs)}/${Math.round(diary.target_carbs)}`;
  nodes.water.textContent = `${data.water_ml} мл воды`;
  nodes.weightGoal.textContent = [
    data.weight_goal.forecast_text,
    data.latest_weight_kg ? `Текущий вес: ${formatNumber(data.latest_weight_kg)} кг.` : "",
  ].filter(Boolean).join(" ");

  if (!diary.entries.length) {
    nodes.entries.innerHTML = '<p class="muted">Сегодня пока нет еды.</p>';
    return;
  }
  nodes.entries.innerHTML = diary.entries.map((entry) => `
    <article class="entry">
      <div>
        <strong>${escapeHtml(entry.name)}</strong>
        <small>${entry.weight_g ? `${formatNumber(entry.weight_g)} г` : "без граммовки"}</small>
      </div>
      <b>${Math.round(entry.kcal)} ккал</b>
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
