export const fmt = (value) => new Intl.NumberFormat('en-US').format(Number(value || 0));
export const fmtNumber = (value) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(Number(value));
export const money = (value, currency = 'USD') => new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value));
export const dt = (value) => value ? new Date(value).toLocaleString() : '—';
export const displayRunId = (id) => String(id || '').startsWith('python-') ? String(id) : String(id || '').slice(0, 8);

export function displayText(value, fallback = '—') {
  if (value == null || value === '') return fallback;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => displayText(item, '')).filter(Boolean).join(', ') || fallback;
  return String(value.name || value.label || value.code || value.value || JSON.stringify(value));
}

export function statusLabel(value) {
  return String(value || 'unknown').toLowerCase().replaceAll('_', ' ');
}

export function statusClass(value) {
  const label = statusLabel(value);
  if (['succeeded', 'success', 'integrated', 'online', 'reachable'].includes(label)) return 'good';
  if (['failed', 'unavailable', 'error'].includes(label)) return 'bad';
  if (['running', 'queued', 'in progress'].includes(label)) return 'working';
  if (label === 'partially succeeded') return 'partial';
  return 'neutral';
}
