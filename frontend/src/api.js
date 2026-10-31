export function resolveApiBase(configuredBase, pageOrigin) {
  return String(configuredBase || pageOrigin || 'http://localhost').replace(/\/+$/, '');
}

const base = resolveApiBase(import.meta.env?.VITE_API_BASE_URL, globalThis.window?.location?.origin);

export async function request(path, options = {}) {
  const started = performance.now();
  const response = await fetch(`${base}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const elapsed = Math.round(performance.now() - started);
  const body = await response.json().catch(() => null);
  return { response, elapsed, body };
}

export { base as apiBase };
