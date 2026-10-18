// Authentication credentials stay in HttpOnly cookies; only CSRF lives in memory.
const nativeFetch = async (input, options = {}) => {
  const path = typeof input === 'string' ? input : input.url;
  const controller = new AbortController();
  const abort = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) abort();
  else options.signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(() => controller.abort(new Error('Request timed out. Your input is preserved. Please retry.')), path.includes('analyze-requirement') ? 30000 : 20000);
  try { return await globalThis.fetch(input, { ...options, signal: controller.signal }); }
  finally { clearTimeout(timeout); options.signal?.removeEventListener('abort', abort); }
};
let csrfToken = '';
let refreshPromise = null;
let authGeneration = 0;

async function rememberCsrf(response, pathname, generation = authGeneration) {
  if (!pathname.startsWith('/api/auth/') || !response.ok) return;
  try {
    const data = await response.clone().json();
    if (generation !== authGeneration) return;
    if (data.csrf_token) csrfToken = data.csrf_token;
    if (pathname === '/api/auth/logout' || pathname === '/api/auth/reset-password' || pathname === '/api/auth/change-password') csrfToken = '';
  } catch { /* Download and non-JSON responses have no CSRF value. */ }
}

async function refreshAuthentication() {
  if (!refreshPromise) {
    const generation = authGeneration;
    refreshPromise = (async () => {
      const bootstrap = await nativeFetch('/api/auth/csrf', { credentials: 'include' });
      if (!bootstrap.ok) return false;
      const data = await bootstrap.json();
      const response = await nativeFetch('/api/auth/refresh', {
        method: 'POST', credentials: 'include',
        headers: { 'X-CSRF-Token': data.csrf_token },
      });
      await rememberCsrf(response, '/api/auth/refresh', generation);
      return response.ok && generation === authGeneration;
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function apiFetch(input, options = {}) {
  const url = new URL(typeof input === 'string' ? input : input.url, globalThis.location.origin);
  const pathname = url.pathname;
  if (url.origin !== globalThis.location.origin || !pathname.startsWith('/api/')) return nativeFetch(input, options);
  if (['/api/auth/login', '/api/auth/logout', '/api/auth/reset-password', '/api/auth/change-password'].includes(pathname)) {
    // Complete any rotation before login replaces cookies. A stale /me response
    // must not start a new refresh or overwrite the successful login's CSRF.
    if (refreshPromise) await refreshPromise.catch(() => false);
    authGeneration++;
  }
  const generation = authGeneration;
  const send = async () => {
    const headers = new Headers(options.headers);
    const method = (options.method || 'GET').toUpperCase();
    if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes(method) && !pathname.startsWith('/api/invitations/')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
    const response = await nativeFetch(input, { ...options, credentials: 'include', headers });
    await rememberCsrf(response, pathname, generation);
    return response;
  };
  let response = await send();
  // csrf_failed is returned before any protected action executes, so one retry is safe.
  if (response.status === 403 && generation === authGeneration && !pathname.startsWith('/api/invitations/')) {
    let csrfFailed = false;
    try { csrfFailed = (await response.clone().json()).code === 'csrf_failed'; } catch { /* Leave other errors unchanged. */ }
    if (csrfFailed) {
      const bootstrap = await nativeFetch('/api/auth/csrf', { credentials: 'include' });
      await rememberCsrf(bootstrap, '/api/auth/csrf', generation);
      if (bootstrap.ok && generation === authGeneration) response = await send();
    }
  }
  const excluded = ['/api/auth/login', '/api/auth/logout', '/api/auth/refresh', '/api/auth/csrf', '/api/auth/forgot-password', '/api/auth/reset-password'];
  if (!excluded.includes(pathname)) {
    let needsRefresh = response.status === 401;
    if (pathname === '/api/auth/me' && response.ok) {
      try {
        const data = await response.clone().json();
        needsRefresh = !data.authenticated && data.refresh_available !== false;
      } catch { /* Invalid JSON is handled by the caller. */ }
    }
    if (needsRefresh && generation === authGeneration && await refreshAuthentication().catch(() => false)) response = await send();
  }
  return response;
}
