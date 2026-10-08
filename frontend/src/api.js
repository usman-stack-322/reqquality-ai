// Authentication credentials stay in HttpOnly cookies; only CSRF lives in memory.
const nativeFetch = (...args) => globalThis.fetch(...args);
let csrfToken = '';
let refreshPromise = null;

async function rememberCsrf(response, pathname) {
  if (!pathname.startsWith('/api/auth/') || !response.ok) return;
  try {
    const data = await response.clone().json();
    if (data.csrf_token) csrfToken = data.csrf_token;
    if (pathname === '/api/auth/logout' || pathname === '/api/auth/reset-password' || pathname === '/api/auth/change-password') csrfToken = '';
  } catch { /* Download and non-JSON responses have no CSRF value. */ }
}

async function refreshAuthentication() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const bootstrap = await nativeFetch('/api/auth/csrf', { credentials: 'include' });
      if (!bootstrap.ok) return false;
      const data = await bootstrap.json();
      const response = await nativeFetch('/api/auth/refresh', {
        method: 'POST', credentials: 'include',
        headers: { 'X-CSRF-Token': data.csrf_token },
      });
      await rememberCsrf(response, '/api/auth/refresh');
      return response.ok;
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function apiFetch(input, options = {}) {
  const url = new URL(typeof input === 'string' ? input : input.url, globalThis.location.origin);
  const pathname = url.pathname;
  if (url.origin !== globalThis.location.origin || !pathname.startsWith('/api/')) return nativeFetch(input, options);
  const send = async () => {
    const headers = new Headers(options.headers);
    const method = (options.method || 'GET').toUpperCase();
    if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes(method) && !pathname.startsWith('/api/invitations/')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
    const response = await nativeFetch(input, { ...options, credentials: 'include', headers });
    await rememberCsrf(response, pathname);
    return response;
  };
  let response = await send();
  // csrf_failed is returned before any protected action executes, so one retry is safe.
  if (response.status === 403 && !pathname.startsWith('/api/invitations/')) {
    let csrfFailed = false;
    try { csrfFailed = (await response.clone().json()).code === 'csrf_failed'; } catch { /* Leave other errors unchanged. */ }
    if (csrfFailed) {
      const bootstrap = await nativeFetch('/api/auth/csrf', { credentials: 'include' });
      await rememberCsrf(bootstrap, '/api/auth/csrf');
      if (bootstrap.ok) response = await send();
    }
  }
  const excluded = ['/api/auth/login', '/api/auth/logout', '/api/auth/refresh', '/api/auth/csrf', '/api/auth/forgot-password', '/api/auth/reset-password'];
  if (!excluded.includes(pathname)) {
    let needsRefresh = response.status === 401;
    if (pathname === '/api/auth/me' && response.ok) {
      try { needsRefresh = !(await response.clone().json()).authenticated; } catch { /* Invalid JSON is handled by the caller. */ }
    }
    if (needsRefresh && await refreshAuthentication()) response = await send();
  }
  return response;
}
