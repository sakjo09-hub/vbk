import { api, getToken, setToken, clearToken } from "./api.js";

const $ = (sel) => document.querySelector(sel);

let currentUser = null;
let currentBalance = null;
let currentSport = "all";

const SPORT_LABELS = { football: "Футбол", dota: "Dota 2" };

/* ============ UTILS ============ */
function formatMoney(n) {
    return Number(n).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function statusLabel(s) {
    return { pending: "Ожидает", won: "Выигрыш", lost: "Проигрыш", cancelled: "Возврат" }[s] || s;
}

function txTypeLabel(t) {
    return { bonus: "Бонус", bet: "Ставка", payout: "Выплата", refund: "Возврат", deposit: "Пополнение", withdraw: "Списание" }[t] || t;
}

function toast(message, type = "info", timeout = 3500) {
    const el = $("#toast");
    el.textContent = message;
    el.className = `toast ${type}`;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, timeout);
}

function h(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
        if (k === "class") node.className = v;
        else if (k === "dataset") Object.assign(node.dataset, v);
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
        else if (v !== null && v !== undefined) node.setAttribute(k, v);
    }
    for (const child of children.flat()) {
        if (child == null || child === false) continue;
        node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
}

/* ============ AUTH ============ */
async function init() {
    document.querySelectorAll(".tab").forEach((t) => {
        t.addEventListener("click", () => switchAuthTab(t.dataset.tab));
    });
    $("#login-form").addEventListener("submit", handleLogin);
    $("#register-form").addEventListener("submit", handleRegister);
    $("#logout-btn").addEventListener("click", logout);
    $("#bet-modal-close").addEventListener("click", closeBetModal);
    $("#bet-modal").addEventListener("click", (e) => {
        if (e.target.id === "bet-modal") closeBetModal();
    });
    window.addEventListener("auth-expired", () => {
        currentUser = null;
        showAuth();
        toast("Сессия истекла, войдите снова", "error");
    });
    window.addEventListener("hashchange", router);

    if (getToken()) {
        try {
            currentUser = await api.me();
            await enterApp();
            return;
        } catch {
            clearToken();
        }
    }
    showAuth();
}

function switchAuthTab(tab) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
    $("#login-form").hidden = tab !== "login";
    $("#register-form").hidden = tab !== "register";
    $("#auth-error").hidden = true;
}

function showAuthError(msg) {
    const el = $("#auth-error");
    el.textContent = msg;
    el.hidden = false;
}

async function handleLogin(e) {
    e.preventDefault();
    const form = e.target;
    const email = form.email.value.trim();
    const password = form.password.value;
    try {
        const data = await api.login(email, password);
        setToken(data.access_token);
        currentUser = await api.me();
        await enterApp();
        toast("Добро пожаловать!", "success");
    } catch (err) {
        showAuthError(err.message);
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const form = e.target;
    const username = form.username.value.trim();
    const email = form.email.value.trim();
    const password = form.password.value;
    try {
        await api.register(username, email, password);
        const data = await api.login(email, password);
        setToken(data.access_token);
        currentUser = await api.me();
        await enterApp();
        toast("Аккаунт создан, начислено 10 000 VC", "success");
    } catch (err) {
        showAuthError(err.message);
    }
}

function logout() {
    clearToken();
    currentUser = null;
    currentBalance = null;
    showAuth();
}

function showAuth() {
    $("#auth-view").hidden = false;
    $("#app-view").hidden = true;
}

async function enterApp() {
    $("#auth-view").hidden = true;
    $("#app-view").hidden = false;
    await updateBalance();
    if (!location.hash) location.hash = "#/events";
    router();
}

async function updateBalance() {
    try {
        const data = await api.balance();
        currentBalance = Number(data.balance);
        $("#balance-value").textContent = formatMoney(currentBalance) + " " + data.currency_code;
    } catch {
        $("#balance-value").textContent = "—";
    }
}

/* ============ ROUTER ============ */
function router() {
    const route = (location.hash.replace("#/", "") || "events").split("/")[0];
    document.querySelectorAll(".nav-link").forEach((l) => l.classList.toggle("active", l.dataset.route === route));
    const content = $("#content");
    content.innerHTML = "";

    if (route === "bets") viewBets(content);
    else if (route === "wallet") viewWallet(content);
    else viewEvents(content);
}

/* ============ VIEW: EVENTS ============ */
async function viewEvents(content) {
    const header = h("div", { class: "page-header" },
        h("h2", { class: "page-title" }, "Спортивные события"),
        h("div", { class: "filter-tabs" },
            ...[["all", "Все"], ["football", "Футбол"], ["dota", "Dota 2"]].map(([key, label]) =>
                h("button", {
                    class: `filter-tab ${currentSport === key ? "active" : ""}`,
                    onclick: () => { currentSport = key; router(); },
                }, label)
            )
        )
    );
    content.append(header);

    const loader = h("div", { class: "loading" }, "Загрузка событий...");
    content.append(loader);

    try {
        const sport = currentSport === "all" ? null : currentSport;
        const events = await api.events(sport);
        loader.remove();

        if (!events.length) {
            content.append(h("div", { class: "empty-state" },
                h("h3", {}, "Нет доступных событий"),
                h("p", {}, "Попробуйте обновить позже или выбрать другой вид спорта")
            ));
            return;
        }

        const grid = h("div", { class: "events-grid" });
        for (const ev of events) grid.append(renderEventCard(ev));
        content.append(grid);
    } catch (err) {
        loader.remove();
        content.append(h("div", { class: "empty-state" },
            h("h3", {}, "Не удалось загрузить события"), h("p", {}, err.message)
        ));
    }
}

function renderEventCard(ev) {
    const market = ev.markets && ev.markets[0];
    const selections = (market?.selections || []).filter((s) => s.status === "open");

    const oddsRow = selections.length
        ? h("div", { class: "odds-row" }, ...selections.map((s) =>
            h("button", {
                class: "odds-btn",
                onclick: () => openBetModal(ev, s),
            },
                h("span", { class: "odds-label" }, s.label.replace(/^П[12]\s/, "")),
                h("span", { class: "odds-value" }, Number(s.odds).toFixed(2))
            )
        ))
        : h("div", { class: "empty-state" }, "Приём ставок закрыт");

    return h("div", { class: "event-card" },
        h("div", { class: "event-meta" },
            h("span", { class: `sport-badge ${ev.sport}` }, SPORT_LABELS[ev.sport] || ev.sport),
            ev.tournament ? h("span", { class: "event-tournament" }, ev.tournament) : null,
            h("span", { class: "event-time" }, formatDate(ev.starts_at))
        ),
        h("div", { class: "event-teams" },
            h("div", { class: "team home" }, ev.home_team),
            h("div", { class: "vs" }, "—"),
            h("div", { class: "team away" }, ev.away_team)
        ),
        oddsRow
    );
}

/* ============ BET MODAL ============ */
let modalSelection = null;

async function openBetModal(event, selection) {
    modalSelection = { event, selection };
    const odds = Number(selection.odds);
    const body = $("#bet-modal-body");
    body.innerHTML = "";

    const amountInput = h("input", {
        type: "number", class: "bet-amount-input", id: "bet-amount",
        value: "100", min: "1", step: "1", inputmode: "decimal",
    });

    const payoutValue = h("span", { class: "value" }, formatMoney(100 * odds));
    const errorBox = h("div", { class: "modal-error", id: "bet-error", hidden: true });

    function recalc() {
        const amt = parseFloat(amountInput.value) || 0;
        payoutValue.textContent = formatMoney(amt * odds);
    }
    amountInput.addEventListener("input", recalc);

    body.append(
        h("div", { class: "bet-summary" },
            h("div", { class: "bet-summary-row" },
                h("span", { class: "label" }, "Матч"),
                h("span", { class: "value" }, `${event.home_team} — ${event.away_team}`)
            ),
            h("div", { class: "bet-summary-row" },
                h("span", { class: "label" }, "Исход"),
                h("span", { class: "value" }, selection.label)
            ),
            h("div", { class: "bet-summary-row" },
                h("span", { class: "label" }, "Коэффициент"),
                h("span", { class: "value" }, odds.toFixed(2))
            )
        ),
        h("div", {},
            h("div", { class: "bet-summary-row", style: "margin-bottom:8px" },
                h("span", { class: "label" }, "Сумма ставки, VC")
            ),
            amountInput,
        ),
        h("div", { class: "quick-amounts" },
            h("button", { class: "quick-amount", onclick: () => { amountInput.value = 100; recalc(); } }, "100"),
            h("button", { class: "quick-amount", onclick: () => { amountInput.value = 500; recalc(); } }, "500"),
            h("button", { class: "quick-amount", onclick: () => { amountInput.value = 1000; recalc(); } }, "1000"),
            h("button", { class: "quick-amount", onclick: () => { amountInput.value = Math.floor(currentBalance || 0); recalc(); } }, "Всё")
        ),
        h("div", { class: "bet-payout-preview" },
            h("div", { class: "label" }, "Возможный выигрыш"),
            payoutValue
        ),
        errorBox,
        h("button", { class: "btn btn-success btn-block", id: "bet-confirm" }, "Сделать ставку")
    );

    $("#bet-confirm").addEventListener("click", () => confirmBet(amountInput.value, errorBox));
    $("#bet-modal").hidden = false;
}

async function confirmBet(amountStr, errorBox) {
    const amount = parseFloat(amountStr);
    const btn = $("#bet-confirm");
    if (!amount || amount <= 0) {
        errorBox.textContent = "Введите сумму больше нуля";
        errorBox.hidden = false;
        return;
    }
    if (currentBalance !== null && amount > currentBalance) {
        errorBox.textContent = "Недостаточно средств на балансе";
        errorBox.hidden = false;
        return;
    }

    btn.disabled = true;
    btn.textContent = "Обработка...";
    errorBox.hidden = true;

    try {
        const { event, selection } = modalSelection;
        const bet = await api.placeBet(selection.id, amount);
        closeBetModal();
        await updateBalance();
        toast(`Ставка принята: ${formatMoney(bet.amount)} VC на «${selection.label}»`, "success");
        if (location.hash.includes("bets")) router();
    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.hidden = false;
        btn.disabled = false;
        btn.textContent = "Сделать ставку";
    }
}

function closeBetModal() {
    $("#bet-modal").hidden = true;
    modalSelection = null;
}

/* ============ VIEW: MY BETS ============ */
async function viewBets(content) {
    content.append(h("div", { class: "page-header" },
        h("h2", { class: "page-title" }, "Мои ставки")
    ));
    const loader = h("div", { class: "loading" }, "Загрузка...");
    content.append(loader);

    try {
        const bets = await api.myBets();
        loader.remove();

        if (!bets.length) {
            content.append(h("div", { class: "empty-state" },
                h("h3", {}, "Ставок пока нет"),
                h("p", {}, "Перейдите на вкладку «События», чтобы сделать первую ставку")
            ));
            return;
        }

        const rows = bets.map((b) => h("tr", {},
            h("td", {}, "#" + b.id),
            h("td", {}, formatDate(b.created_at)),
            h("td", {}, Number(b.odds).toFixed(2)),
            h("td", { class: "num" }, formatMoney(b.amount)),
            h("td", { class: "num" }, formatMoney(b.potential_payout)),
            h("td", {}, h("span", { class: `status-badge status-${b.status}` }, statusLabel(b.status))),
            h("td", { class: "num" }, b.payout != null ? formatMoney(b.payout) : "—")
        ));

        content.append(h("div", { class: "table-wrap" },
            h("table", {},
                h("thead", {}, h("tr", {},
                    h("th", {}, "№"),
                    h("th", {}, "Дата"),
                    h("th", {}, "Коэф."),
                    h("th", { class: "num" }, "Сумма"),
                    h("th", { class: "num" }, "Возможный выигрыш"),
                    h("th", {}, "Статус"),
                    h("th", { class: "num" }, "Выплата")
                )),
                h("tbody", {}, ...rows)
            )
        ));
    } catch (err) {
        loader.remove();
        content.append(h("div", { class: "empty-state" },
            h("h3", {}, "Ошибка загрузки"), h("p", {}, err.message)
        ));
    }
}

/* ============ VIEW: WALLET ============ */
async function viewWallet(content) {
    content.append(h("div", { class: "page-header" },
        h("h2", { class: "page-title" }, "Кошелёк")
    ));
    const loader = h("div", { class: "loading" }, "Загрузка...");
    content.append(loader);

    try {
        const [bal, txs] = await Promise.all([api.balance(), api.transactions()]);
        loader.remove();

        content.append(h("div", { class: "balance-card" },
            h("div", { class: "label" }, "Доступный баланс"),
            h("div", {},
                h("span", { class: "amount" }, formatMoney(bal.balance)),
                h("span", { class: "currency" }, bal.currency_code)
            )
        ));

        if (!txs.length) {
            content.append(h("div", { class: "empty-state" },
                h("h3", {}, "Нет транзакций")
            ));
            return;
        }

        const rows = txs.map((t) => {
            const sign = Number(t.amount) >= 0 ? "+" : "";
            return h("tr", {},
                h("td", {}, formatDate(t.created_at)),
                h("td", {}, txTypeLabel(t.type)),
                h("td", { class: "num" }, sign + formatMoney(t.amount)),
                h("td", { class: "num" }, formatMoney(t.balance_after))
            );
        });

        content.append(h("div", { class: "table-wrap" },
            h("table", {},
                h("thead", {}, h("tr", {},
                    h("th", {}, "Дата"),
                    h("th", {}, "Тип"),
                    h("th", { class: "num" }, "Сумма"),
                    h("th", { class: "num" }, "Баланс после")
                )),
                h("tbody", {}, ...rows)
            )
        ));
    } catch (err) {
        loader.remove();
        content.append(h("div", { class: "empty-state" },
            h("h3", {}, "Ошибка загрузки"), h("p", {}, err.message)
        ));
    }
}

init();
