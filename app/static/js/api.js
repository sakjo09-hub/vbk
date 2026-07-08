const API_BASE = "/api";
const TOKEN_KEY = "vbk_token";

export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, auth = true } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth && getToken()) {
        headers["Authorization"] = "Bearer " + getToken();
    }
    const res = await fetch(API_BASE + path, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401 && auth) {
        clearToken();
        window.dispatchEvent(new CustomEvent("auth-expired"));
    }

    let data = null;
    const text = await res.text();
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            data = { detail: text };
        }
    }

    if (!res.ok) {
        const message = data?.detail || `Ошибка ${res.status}`;
        throw new Error(message);
    }
    return data;
}

export const api = {
    register: (username, email, password) =>
        request("/auth/register", { method: "POST", auth: false, body: { username, email, password } }),

    login: (email, password) =>
        request("/auth/login", { method: "POST", auth: false, body: { email, password } }),

    me: () => request("/auth/me"),

    events: (sport) => request("/events" + (sport ? `?sport=${sport}` : "")),

    event: (id) => request(`/events/${id}`),

    placeBet: (selectionId, amount) =>
        request("/bets", { method: "POST", body: { selection_id: selectionId, amount } }),

    myBets: () => request("/bets"),

    balance: () => request("/wallet/balance"),

    transactions: () => request("/wallet/transactions"),
};
