import test from 'node:test';
import assert from 'node:assert/strict';
import { BACKEND_UNAVAILABLE, loginErrorMessage } from './login-errors.js';

test('sign-in distinguishes unavailable database, proxy failures and throttling', () => {
  assert.match(loginErrorMessage(503, { code: 'database_unavailable' }), /database is temporarily unavailable/);
  for (const status of [500, 502, 503, 504]) {
    assert.equal(loginErrorMessage(status, { error: 'private driver details' }), BACKEND_UNAVAILABLE);
  }
  assert.match(loginErrorMessage(429), /Too many sign-in attempts/);
});

test('invalid credentials remain generic and validation errors remain useful', () => {
  assert.equal(loginErrorMessage(401, { error: 'private account details' }), 'Email or password is incorrect.');
  assert.equal(loginErrorMessage(400, { error: 'Send a JSON object.' }), 'Send a JSON object.');
  assert.match(loginErrorMessage(403), /Unable to sign in/);
});
