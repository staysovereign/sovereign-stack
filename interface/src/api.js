const BASE = "/api";
const TOKEN_KEY = "sovereign_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Called when a protected request comes back 401 (expired/invalid session).
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(method, path, body) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    // A 401 on a normal call means our session is gone — drop it and re-login.
    // (Auth endpoints handle their own 401s, e.g. a wrong password on login.)
    if (res.status === 401 && !path.startsWith("/auth/")) {
      clearToken();
      if (onUnauthorized) onUnauthorized();
    }
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Auth
  authStatus:  () => request("GET", "/auth/status"),
  authSetup:   (password) => request("POST", "/auth/setup", { password }),
  authLogin:   (password) => request("POST", "/auth/login", { password }),
  authChange:  (current_password, new_password) =>
    request("POST", "/auth/change", { current_password, new_password }),
  authLogout:  () => request("POST", "/auth/logout"),

  // Vault
  vault:          (page = 1, retrieved = false) => request("GET", `/vault?page=${page}&retrieved=${retrieved}`),
  vaultRetrieve:  (id) => request("POST", `/vault/${id}/retrieve`),

  // Council
  council:        () => request("GET", "/council"),
  councilAdd:     (body) => request("POST", "/council", body),
  councilUpdate:  (id, body) => request("PUT", `/council/${id}`, body),
  councilRemove:  (id) => request("DELETE", `/council/${id}`),

  // Decrees
  decrees:        () => request("GET", "/decrees"),
  decreesCreate:  (body) => request("POST", "/decrees", body),
  decreesUpdate:  (id, body) => request("PUT", `/decrees/${id}`, body),
  decreesDelete:  (id) => request("DELETE", `/decrees/${id}`),

  // Advisor
  advisor:        () => request("GET", "/advisor"),
  advisorDismiss: (id) => request("POST", `/advisor/suggestions/${id}/dismiss`),
  advisorReset:   () => request("POST", "/advisor/reset"),

  // Chronicle
  chronicle:      (days = 30) => request("GET", `/chronicle?days=${days}`),

  // Settings
  settings:       () => request("GET", "/settings"),
  settingsUpdate: (values) => request("PUT", "/settings", { values }),
};
