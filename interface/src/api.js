const BASE = "/api";

async function request(method, path, body) {
  const opts = {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
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
