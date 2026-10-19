const base = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, '');

export async function request(path, options = {}) {
  const started = performance.now();
  const response = await fetch(`${base}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const elapsed = Math.round(performance.now() - started);
  const body = await response.json().catch(() => null);
  return { response, elapsed, body };
}

export { base as apiBase };
