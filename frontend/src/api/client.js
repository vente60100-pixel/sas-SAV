const API_BASE = '/api';

function getAuthHeaders() {
  const token = localStorage.getItem('auth_token');
  if (token) return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
  const creds = localStorage.getItem('auth_basic');
  if (creds) return { 'Authorization': `Basic ${creds}`, 'Content-Type': 'application/json' };
  return { 'Content-Type': 'application/json' };
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...getAuthHeaders(), ...options.headers },
  });
  if (res.status === 401) {
    localStorage.removeItem('auth_basic');
    window.location.reload();
    throw new Error('Non autorisé');
  }
  if (!res.ok) throw new Error(`Erreur ${res.status}`);
  return res.json();
}

// Auth
export function login(username, password) {
  const basic = btoa(`${username}:${password}`);
  localStorage.setItem('auth_basic', basic);
}

export function logout() {
  localStorage.removeItem('auth_basic');
  localStorage.removeItem('auth_token');
}

export function isLoggedIn() {
  return !!(localStorage.getItem('auth_basic') || localStorage.getItem('auth_token'));
}

// Stats
export const getStats = (period = 'today') => apiFetch(`/stats?period=${period}`);

// Intelligence
export const getIntelligence = (period = '7d') => apiFetch(`/intelligence?period=${period}`);

// Metrics
export const getMetrics = () => apiFetch('/metrics');

// Health
export const getHealth = () => apiFetch('/health');

// Circuit breakers
export const getCircuitBreakers = () => apiFetch('/circuit-breakers');

// Clients
export const getClients = (search = '', limit = 50, offset = 0) =>
  apiFetch(`/clients?search=${encodeURIComponent(search)}&limit=${limit}&offset=${offset}`);
export const getClientDetail = (email) => apiFetch(`/clients/${encodeURIComponent(email)}`);

// Pipeline
export const getPipeline = (limit = 50, offset = 0, category = '') =>
  apiFetch(`/pipeline?limit=${limit}&offset=${offset}${category ? `&category=${category}` : ''}`);

// Escalations
export const getEscalations = () => apiFetch('/escalations');
export const getEscalationDetail = (id) => apiFetch(`/escalations/${id}`);
export const resolveEscalation = (id, action = 'resolved', responseText = null) =>
  apiFetch(`/escalations/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ action, response_text: responseText }),
  });
export const getEscalationAiDraft = (id) =>
  apiFetch(`/escalations/${id}/ai-draft`, { method: 'POST' });

// Chat
export const sendChatMessage = (message) =>
  apiFetch('/chat', { method: 'POST', body: JSON.stringify({ message }) });

// Email
export const sendEmail = (to, subject, body) =>
  apiFetch('/send-email', { method: 'POST', body: JSON.stringify({ to, subject, body }) });

// Settings
export const getSettings = () => apiFetch('/settings');
export const saveSettings = (data) =>
  apiFetch('/settings', { method: 'POST', body: JSON.stringify(data) });
export const settingsAiAssist = (message, currentSettings) =>
  apiFetch('/settings/ai-assist', {
    method: 'POST',
    body: JSON.stringify({ message, current_settings: currentSettings }),
  });
