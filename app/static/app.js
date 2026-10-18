"use strict";

const DAY_START = 8;
const DAY_END = 20;
const ROLE_LABEL = { admin: "Адміністратор", user: "Користувач" };
const STATUS_LABEL = { confirmed: "Підтверджено", cancelled: "Скасовано", pending: "Очікує" };
const TYPE_LABEL = { coworking_desk: "Робоче місце", conference_room: "Переговорна" };
const TABS = {
  user: [["book", "Забронювати"], ["mine", "Мої бронювання"]],
  admin: [["book", "Забронювати"], ["all", "Усі бронювання"], ["rooms", "Зали"], ["users", "Користувачі"]],
};

const pad = (n) => String(n).padStart(2, "0");
const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const state = {
  token: sessionStorage.getItem("token"),
  me: null,
  tab: "book",
  authMode: "login",
  rooms: [],
  roomId: null,
  date: todayStr(),
  start: "10:00",
  end: "11:00",
  busy: [],
};

const $app = document.getElementById("app");
const $status = document.getElementById("status");
let statusTimer = null;

/* ---------- Допоміжне ---------- */

// Усі дані з сервера вставляються через текстові вузли (без innerHTML) — захист від XSS.
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function say(message, kind = "info") {
  $status.textContent = message;
  $status.className = `status show ${kind}`;
  clearTimeout(statusTimer);
  statusTimer = setTimeout(() => { $status.className = "status"; }, 6000);
}

const safe = (fn) => (event) => {
  if (event && event.preventDefault) event.preventDefault();
  return Promise.resolve(fn(event)).catch((err) => say(err.message, "error"));
};

function errorText(status, data) {
  if (data && typeof data.detail === "string") {
    return data.error_id ? `${data.detail} (код помилки: ${data.error_id})` : data.detail;
  }
  if (data && Array.isArray(data.detail)) {
    return "Перевірте введені дані: " + data.detail.map((d) => d.msg).join("; ");
  }
  return `Помилка запиту (${status}).`;
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  let payload;
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (form) payload = new URLSearchParams(form);
  else if (body) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }

  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* тіло не є JSON */ }
  if (!res.ok) {
    if (res.status === 401 && state.token) { logout(); throw new Error("Сесія завершилась. Увійдіть знову."); }
    throw new Error(errorText(res.status, data));
  }
  return data;
}

const fmt = (iso) => new Date(iso).toLocaleString("uk-UA", { dateStyle: "medium", timeStyle: "short" });
const minutesOf = (hhmm) => { const [a, b] = hhmm.split(":").map(Number); return a * 60 + b; };

/* ---------- Автентифікація ---------- */

function logout() {
  sessionStorage.removeItem("token");
  Object.assign(state, { token: null, me: null, tab: "book", roomId: null });
  render();
}

async function login(email, password) {
  const data = await api("/auth/login", { method: "POST", form: { username: email, password } });
  state.token = data.access_token;
  sessionStorage.setItem("token", state.token);
  state.me = await api("/auth/me");
  state.tab = "book";
  render();
}

function authScreen() {
  const registering = state.authMode === "register";
  const field = (label, name, type, extra = {}) =>
    h("label", {}, label, h("input", { name, type, required: true, ...extra }));

  const form = h("form", {
    onsubmit: safe(async (e) => {
      const f = new FormData(e.target);
      if (registering) {
        await api("/auth/register", {
          method: "POST",
          body: { email: f.get("email"), full_name: f.get("full_name"), password: f.get("password") },
        });
      }
      await login(f.get("email"), f.get("password"));
    }),
  },
    registering && field("Ім'я та прізвище", "full_name", "text", { autocomplete: "name" }),
    field("Електронна пошта", "email", "email", { autocomplete: "email" }),
    field(registering ? "Пароль (щонайменше 8 символів)" : "Пароль", "password", "password",
      { minlength: registering ? 8 : 1, autocomplete: registering ? "new-password" : "current-password" }),
    h("button", { class: "btn signal", type: "submit" }, registering ? "Створити акаунт" : "Увійти"),
  );

  const modeBtn = (mode, text) =>
    h("button", {
      class: `btn ${state.authMode === mode ? "" : "ghost"}`, type: "button",
      onclick: () => { state.authMode = mode; render(); },
    }, text);

  return h("div", { class: "auth" },
    h("section", { class: "pitch" },
      h("div", { class: "brand" }, "слот"),
      h("h1", {}, "Займіть вільне місце на свій час"),
      h("p", {}, "Бачите, коли зала зайнята, і бронюєте вільний інтервал за кілька секунд."),
      h("div", { class: "demo", "aria-hidden": "true" }, h("span", { class: "a" }), h("span", { class: "b" }), h("span", { class: "c" })),
    ),
    h("section", { class: "panel" },
      h("div", { class: "switch" }, modeBtn("login", "Вхід"), modeBtn("register", "Реєстрація")),
      form,
    ),
  );
}

/* ---------- Шкала дня ---------- */

function drawRuler() {
  const box = document.getElementById("ruler-box");
  if (!box) return;
  const span = (DAY_END - DAY_START) * 60;
  const pct = (mins) => Math.max(0, Math.min(100, ((mins - DAY_START * 60) / span) * 100));
  const dayBase = new Date(`${state.date}T00:00:00`);
  const place = (cls, a, b, title) => {
    const left = pct(a), right = pct(b);
    return right > left ? h("div", { class: cls, style: `left:${left}%;width:${right - left}%`, title }) : null;
  };

  const ruler = h("div", { class: "ruler" });
  for (const slot of state.busy) {
    const a = (new Date(slot.start_time) - dayBase) / 60000;
    const b = (new Date(slot.end_time) - dayBase) / 60000;
    ruler.append(place("busy", a, b, "Зайнято"));
  }
  const s = minutesOf(state.start), e = minutesOf(state.end);
  ruler.append(place(e > s ? "pick" : "pick bad", s, Math.max(e, s + 5), "Ваш вибір"));
  for (let hr = DAY_START; hr <= DAY_END; hr += 2) {
    ruler.append(h("span", { class: "hour", style: `left:${pct(hr * 60)}%` }, `${pad(hr)}:00`));
  }
  box.replaceChildren(ruler);
}

async function loadBusy() {
  if (!state.roomId) { state.busy = []; return; }
  const from = new Date(`${state.date}T00:00:00`);
  const to = new Date(from.getTime() + 24 * 3600 * 1000);
  const q = `start=${encodeURIComponent(from.toISOString())}&end=${encodeURIComponent(to.toISOString())}`;
  state.busy = await api(`/rooms/${state.roomId}/availability?${q}`);
}

/* ---------- Розділи ---------- */

function roomLine(room) {
  return `${TYPE_LABEL[room.room_type] || room.room_type} · ${room.location} · місць: ${room.capacity}`;
}

function bookView() {
  if (!state.rooms.length) {
    return h("p", { class: "empty" },
      state.me.role === "admin"
        ? "Залів ще немає. Додайте перший у розділі «Зали»."
        : "Залів ще немає. Адміністратор має додати їх.");
  }
  const room = state.rooms.find((r) => r.id === state.roomId);

  const list = h("ul", { class: "rooms" }, state.rooms.map((r) =>
    h("li", {}, h("button", {
      type: "button", "aria-pressed": String(r.id === state.roomId),
      onclick: safe(async () => { state.roomId = r.id; await loadBusy(); render(false); }),
    }, r.name, h("small", {}, roomLine(r))))));

  let detail;
  if (!room) {
    detail = h("p", { class: "empty" }, "Оберіть зал зліва, щоб побачити його зайнятість.");
  } else {
    const timeInput = (label, key) => h("label", {}, label,
      h("input", { type: "time", step: "1800", value: state[key], required: true,
        oninput: (e) => { state[key] = e.target.value; drawRuler(); } }));
    detail = h("div", {},
      h("h2", {}, room.name),
      h("p", {}, roomLine(room)),
      h("form", { onsubmit: safe(submitBooking) },
        h("div", { class: "row" },
          h("label", {}, "Дата", h("input", { type: "date", value: state.date, min: todayStr(), required: true,
            onchange: safe(async (e) => { state.date = e.target.value; await loadBusy(); drawRuler(); }) })),
          timeInput("Початок", "start"),
          timeInput("Кінець", "end"),
        ),
        h("div", { id: "ruler-box" }),
        h("div", { class: "legend" },
          h("span", {}, h("i", { class: "b" }), "Зайнято"), h("span", {}, h("i", { class: "p" }), "Ваш вибір")),
        h("button", { class: "btn signal", type: "submit" }, "Забронювати")),
    );
  }
  return h("div", { class: "book" }, list, detail);
}

async function submitBooking() {
  const start = new Date(`${state.date}T${state.start}`);
  const end = new Date(`${state.date}T${state.end}`);
  if (!(end > start)) throw new Error("Час завершення має бути пізніше за початок.");
  await api("/bookings/", {
    method: "POST",
    body: { room_id: state.roomId, start_time: start.toISOString(), end_time: end.toISOString() },
  });
  say("Заброньовано. Дивіться розділ «Мої бронювання».", "ok");
  await loadBusy();
  drawRuler();
}

function bookingsTable(rows, { admin }) {
  if (!rows.length) return h("p", { class: "empty" }, "Бронювань поки немає.");
  const roomName = (b) => b.room_name || (state.rooms.find((r) => r.id === b.room_id) || {}).name || "—";
  const cancel = (b) => b.status === "cancelled" ? null : h("button", {
    class: "btn danger", type: "button",
    onclick: safe(async () => {
      if (!window.confirm("Скасувати це бронювання?")) return;
      await api(`/bookings/${b.id}`, { method: "DELETE" });
      say("Бронювання скасовано.", "ok");
      await fill();
    }),
  }, "Скасувати");

  return h("div", { class: "tablewrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Зала", admin && "Користувач", "Початок", "Кінець", "Статус", ""].map((t) => (t === false ? null : h("th", {}, t))))),
    h("tbody", {}, rows.map((b) => h("tr", {},
      h("td", {}, roomName(b)),
      admin && h("td", {}, b.user_email),
      h("td", {}, fmt(b.start_time)),
      h("td", {}, fmt(b.end_time)),
      h("td", {}, h("span", { class: `tag ${b.status}` }, STATUS_LABEL[b.status] || b.status)),
      h("td", {}, cancel(b)))))));
}

function roomsAdminView() {
  const f = (label, name, type, extra = {}) => h("label", {}, label, h("input", { name, type, required: true, ...extra }));
  const form = h("form", { class: "inline-form", onsubmit: safe(async (e) => {
    const d = new FormData(e.target);
    await api("/rooms/", { method: "POST", body: {
      name: d.get("name"), room_type: d.get("room_type"), capacity: Number(d.get("capacity")), location: d.get("location") } });
    say("Зал додано.", "ok");
    await fill();
  }) },
    f("Назва", "name", "text"),
    h("label", {}, "Тип", h("select", { name: "room_type" },
      h("option", { value: "conference_room" }, TYPE_LABEL.conference_room),
      h("option", { value: "coworking_desk" }, TYPE_LABEL.coworking_desk))),
    f("Місць", "capacity", "number", { min: 1, max: 500, value: 6 }),
    f("Розташування", "location", "text"),
    h("button", { class: "btn signal", type: "submit" }, "Додати зал"));
  return h("div", {}, form,
    state.rooms.length
      ? h("ul", { class: "rooms" }, state.rooms.map((r) => h("li", {}, h("div", { style: "padding:.8rem .6rem;border-bottom:1.5px solid var(--rule)" }, r.name, h("small", { style: "display:block;color:var(--muted)" }, roomLine(r))))))
      : h("p", { class: "empty" }, "Залів ще немає."));
}

function usersView(users) {
  return h("div", { class: "tablewrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Ім'я", "Пошта", "Роль", "Створено"].map((t) => h("th", {}, t)))),
    h("tbody", {}, users.map((u) => h("tr", {},
      h("td", {}, u.full_name), h("td", {}, u.email), h("td", {}, ROLE_LABEL[u.role] || u.role), h("td", {}, fmt(u.created_at)))))));
}

/* ---------- Каркас і рендер ---------- */

async function fill() {
  const main = document.getElementById("main");
  if (!main) return;
  state.rooms = await api("/rooms/");
  if (state.roomId && !state.rooms.some((r) => r.id === state.roomId)) state.roomId = null;
  let view;
  if (state.tab === "book") {
    if (!state.roomId && state.rooms.length) state.roomId = state.rooms[0].id;
    await loadBusy();
    view = bookView();
  } else if (state.tab === "mine") {
    view = bookingsTable(await api("/bookings/my"), { admin: false });
  } else if (state.tab === "all") {
    view = bookingsTable(await api("/admin/bookings"), { admin: true });
  } else if (state.tab === "rooms") {
    view = roomsAdminView();
  } else {
    view = usersView(await api("/admin/users"));
  }
  main.replaceChildren(view);
  drawRuler();
}

function shell() {
  const tabs = TABS[state.me.role] || TABS.user;
  return h("div", {},
    h("header", { class: "topbar" },
      h("div", { class: "brand" }, "слот"),
      h("div", { class: "who" }, `${state.me.full_name} · ${ROLE_LABEL[state.me.role] || state.me.role}`),
      h("button", { class: "btn ghost", type: "button", onclick: logout }, "Вийти")),
    h("nav", { class: "tabs", role: "tablist" }, tabs.map(([key, label]) =>
      h("button", { role: "tab", type: "button", "aria-selected": String(state.tab === key),
        onclick: () => { state.tab = key; render(); } }, label))),
    h("main", { id: "main" }, h("p", { class: "empty" }, "Завантаження…")));
}

function render(reload = true) {
  if (!state.token || !state.me) { $app.replaceChildren(authScreen()); return; }
  if (reload) { $app.replaceChildren(shell()); fill().catch((err) => say(err.message, "error")); }
  else { fill().catch((err) => say(err.message, "error")); }
}

async function boot() {
  if (state.token) {
    try { state.me = await api("/auth/me"); } catch { state.token = null; }
  }
  render();
}

boot();
