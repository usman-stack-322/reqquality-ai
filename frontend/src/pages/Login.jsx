import { apiFetch as fetch } from '../api.js';
import React, { useRef, useState } from 'react';
import { BACKEND_UNAVAILABLE, loginErrorMessage } from '../login-errors.js';

export default function Login({ onLogin, onRegister, initialEmail = '', notice = '' }) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitting = useRef(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setIsSubmitting(true);
    setError('');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(loginErrorMessage(response.status, data || {}));
      if (!data?.user || !data.csrf_token) throw new Error(BACKEND_UNAVAILABLE);
      onLogin(data);
    } catch (loginError) {
      setError(loginError instanceof TypeError ? BACKEND_UNAVAILABLE : loginError.message || BACKEND_UNAVAILABLE);
    } finally {
      submitting.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="card auth-card" aria-labelledby="login-title">
        <p className="eyebrow">REQQUALITY AI</p>
        <h1 id="login-title">Sign in</h1>
        <p className="auth-intro">Use your project account to review requirements and quality data.</p>
        {notice && <p className="success auth-notice" role="status">{notice}</p>}
        <form className="auth-form" onSubmit={handleSubmit} aria-busy={isSubmitting} aria-describedby="login-feedback">
          <div className="requirement-field">
            <label htmlFor="login-email">Email</label>
            <input id="login-email" type="email" autoComplete="email" maxLength={254} required disabled={isSubmitting} value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="requirement-field">
            <label htmlFor="login-password">Password</label>
            <div className="password-input-row">
              <input id="login-password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required maxLength={1024} disabled={isSubmitting} value={password} onChange={(event) => setPassword(event.target.value)} />
              <button className="password-toggle" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)} disabled={isSubmitting}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          <div className="login-feedback" id="login-feedback" aria-live="polite" aria-atomic="true">
            {error ? <p className="error" role="alert">{error}</p> : <p role="status">{isSubmitting ? 'Signing in securely…' : '\u00a0'}</p>}
          </div>
          <button className="requirement-save-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="auth-switch auth-recovery"><a href="#forgot-password">Forgot password?</a></p>
        <p className="auth-switch">To create an account, ask your administrator for an invitation.</p>
        <p className="auth-switch"><a href="#home">Back to Home</a></p>
      </section>
    </main>
  );
}
