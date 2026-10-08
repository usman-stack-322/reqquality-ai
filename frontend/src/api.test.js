import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.location = { origin: 'https://localhost:5173' };
let sequence = 0;
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
// Use a URL directly to work on both Windows and POSIX.
async function fresh(handler) {
  globalThis.fetch = handler;
  const url = new URL('./api.js', import.meta.url);
  url.searchParams.set('test', sequence++);
  return (await import(url.href)).apiFetch;
}

test('login CSRF is sent automatically while invitation CSRF stays separate', async () => {
  const fetch = await fresh(async (url, options) => {
    assert.equal(options.credentials, 'include');
    if (url === '/api/auth/login') return json({ csrf_token: 'login-csrf' });
    const expected = url === '/api/invitations/accept' ? 'invitation-csrf' : 'login-csrf';
    assert.equal(options.headers.get('X-CSRF-Token'), expected);
    return json({});
  });
  await fetch('/api/auth/login', { method: 'POST' });
  await fetch('/api/requirements', { method: 'POST' });
  await fetch('/api/invitations/accept', { method: 'POST', headers: { 'X-CSRF-Token': 'invitation-csrf' } });
});

test('expired access refreshes once and retries with the rotated CSRF value', async () => {
  let attempts = 0;
  const fetch = await fresh(async (url, options) => {
    if (url === '/api/auth/csrf') return json({ csrf_token: 'refresh-csrf' });
    if (url === '/api/auth/refresh') {
      assert.equal(options.headers['X-CSRF-Token'], 'refresh-csrf');
      return json({ csrf_token: 'rotated-csrf' });
    }
    if (++attempts === 1) return json({ code: 'access_token_expired' }, 401);
    assert.equal(options.headers.get('X-CSRF-Token'), 'rotated-csrf');
    return json({ saved: true });
  });
  const response = await fetch('/api/requirements', { method: 'POST', headers: { 'X-CSRF-Token': 'old-csrf' } });
  assert.equal(response.status, 200);
  assert.equal(attempts, 2);
});

test('initial user lookup refreshes after a 200 unauthenticated response', async () => {
  let attempts = 0;
  const fetch = await fresh(async (url) => {
    if (url === '/api/auth/csrf') return json({ csrf_token: 'refresh-csrf' });
    if (url === '/api/auth/refresh') return json({ csrf_token: 'new-csrf' });
    return json({ authenticated: ++attempts > 1 });
  });
  assert.equal((await (await fetch('/api/auth/me')).json()).authenticated, true);
});

test('parallel unauthorized requests share a single refresh operation', async () => {
  const attempts = new Map();
  let refreshes = 0;
  const fetch = await fresh(async (url) => {
    if (url === '/api/auth/csrf') return json({ csrf_token: 'csrf' });
    if (url === '/api/auth/refresh') { refreshes++; return json({ csrf_token: 'new-csrf' }); }
    const count = (attempts.get(url) || 0) + 1; attempts.set(url, count);
    return json({}, count === 1 ? 401 : 200);
  });
  const responses = await Promise.all([fetch('/api/dashboard'), fetch('/api/requirements')]);
  assert.deepEqual(responses.map(r => r.status), [200, 200]);
  assert.equal(refreshes, 1);
});

test('explicit CSRF rejection bootstraps once before retrying the untouched action', async () => {
  let attempts = 0;
  const fetch = await fresh(async (url, options) => {
    if (url === '/api/auth/csrf') return json({ csrf_token: 'fresh-csrf' });
    if (++attempts === 1) return json({ code: 'csrf_failed' }, 403);
    assert.equal(options.headers.get('X-CSRF-Token'), 'fresh-csrf');
    return json({});
  });
  assert.equal((await fetch('/api/requirements/1/review', { method: 'PATCH' })).status, 200);
  assert.equal(attempts, 2);
});

test('permission failures are never retried', async () => {
  let attempts = 0;
  const fetch = await fresh(async () => { attempts++; return json({ error: 'Forbidden' }, 403); });
  assert.equal((await fetch('/api/admin/settings', { method: 'PATCH' })).status, 403);
  assert.equal(attempts, 1);
});

test('an unavailable refresh returns the original unauthorized response', async () => {
  const calls = [];
  const fetch = await fresh(async url => { calls.push(url); return json({}, 401); });
  assert.equal((await fetch('/api/dashboard')).status, 401);
  assert.deepEqual(calls, ['/api/dashboard', '/api/auth/csrf']);
});
