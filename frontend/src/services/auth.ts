import api from './api';

type RefreshResponse = { access_token: string; refresh_token?: string };

let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
const pendingQueue: Array<(token: string | null) => void> = [];

const ENC_KEY = 'mtrader-auth-key';

function encrypt(text: string): string {
  const key = btoa(ENC_KEY).slice(0, 16);
  return btoa(text.split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ key.charCodeAt(i % key.length))).join(''));
}

function decrypt(text: string): string {
  const key = btoa(ENC_KEY).slice(0, 16);
  const raw = atob(text);
  return raw.split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ key.charCodeAt(i % key.length))).join('');
}

export function setAccessToken(token: string | null) {
  inMemoryAccessToken = token;
}

export function getAccessToken() {
  return inMemoryAccessToken;
}

export function storeRefreshToken(token: string) {
  localStorage.setItem('refresh_token_enc', encrypt(token));
}

export function getRefreshToken() {
  const enc = localStorage.getItem('refresh_token_enc');
  return enc ? decrypt(enc) : null;
}

export function clearSession(returnTo?: string) {
  inMemoryAccessToken = null;
  localStorage.removeItem('refresh_token_enc');
  localStorage.removeItem('access_token');
  const target = returnTo ? `/login?returnTo=${encodeURIComponent(returnTo)}` : '/login';
  window.location.assign(target);
}

async function backoff(attempt: number) {
  const delay = Math.min(2000, 200 * Math.pow(2, attempt));
  await new Promise((r) => setTimeout(r, delay));
}

async function performRefresh(): Promise<string> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new Error('no refresh token');

  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const { data } = await api.post<RefreshResponse>('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
        device_fingerprint: localStorage.getItem('device_fingerprint') || 'web-client',
      });
      if (data.refresh_token) storeRefreshToken(data.refresh_token);
      setAccessToken(data.access_token);
      localStorage.setItem('access_token', data.access_token);
      return data.access_token;
    } catch (err) {
      if (attempt === 2) throw err;
      await backoff(attempt);
    }
  }
  throw new Error('refresh failed');
}

export async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = performRefresh()
    .then((token) => {
      pendingQueue.splice(0).forEach((r) => r(token));
      return token;
    })
    .catch((e) => {
      pendingQueue.splice(0).forEach((r) => r(null));
      clearSession(window.location.pathname + window.location.search);
      throw e;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

export function enqueuePendingRequest(cb: (token: string | null) => void) {
  pendingQueue.push(cb);
}
