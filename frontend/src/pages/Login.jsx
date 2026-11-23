import { apiFetch as fetch } from '../api.js';
import React, { useRef, useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { BACKEND_UNAVAILABLE, loginErrorMessage } from '../login-errors.js';
import BrandLogo from '../components/BrandLogo';
import { buttonPrimaryClass, inputClass } from '../components/ui';

export default function Login({ onLogin, initialEmail = '', notice = '' }) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState({ email: false, password: false });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitting = useRef(false);

  const emailInvalid = touched.email && (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()));
  const passwordInvalid = touched.password && !password;

  async function handleSubmit(event) {
    event.preventDefault();
    setTouched({ email: true, password: true });
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
    <main className="auth-shell auth-login-shell w-full max-w-md">
      <section className="card auth-card rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8 space-y-5" aria-labelledby="login-title">
        <div className="space-y-2">
          <div className="auth-brand flex items-center gap-2.5">
            <BrandLogo size={40} />
            <div>
              <span className="eyebrow block text-[11px] font-semibold uppercase tracking-wider text-accent">ReqQuality AI</span>
              <h1 id="login-title" className="text-xl font-bold text-ink">Sign in to workspace</h1>
            </div>
          </div>
          <p className="auth-intro text-xs text-muted">Use your project account to review requirements, test cases, and quality data.</p>
        </div>

        {notice && (
          <p className="success auth-notice rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs font-medium text-success" role="status">
            {notice}
          </p>
        )}

        <form className="auth-form space-y-4" onSubmit={handleSubmit} aria-busy={isSubmitting} aria-describedby="login-feedback">
          <div className="requirement-field space-y-1">
            <label htmlFor="login-email" className="block text-xs font-semibold text-ink">Email</label>
            <span id="login-email-hint" className="block text-[11px] text-muted">Format: you@example.com</span>
            <input
              id="login-email"
              className={inputClass}
              type="email"
              autoComplete="email"
              maxLength={254}
              required
              aria-invalid={emailInvalid ? 'true' : 'false'}
              aria-describedby={emailInvalid ? 'login-email-hint login-email-error' : 'login-email-hint'}
              disabled={isSubmitting}
              value={email}
              onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
              onChange={(event) => setEmail(event.target.value)}
            />
            {emailInvalid && (
              <p id="login-email-error" className="text-xs text-danger">
                Please enter a valid email address.
              </p>
            )}
          </div>

          <div className="requirement-field space-y-1">
            <div className="flex items-center justify-between gap-2">
              <label htmlFor="login-password" className="block text-xs font-semibold text-ink">Password</label>
              <a className="text-xs font-medium text-accent hover:underline" href="#forgot-password">Forgot password?</a>
            </div>
            <div className="password-input-row relative flex items-center">
              <input
                id="login-password"
                className={`${inputClass} pr-16`}
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                maxLength={1024}
                aria-invalid={passwordInvalid ? 'true' : 'false'}
                aria-describedby={passwordInvalid ? 'login-password-error' : undefined}
                disabled={isSubmitting}
                value={password}
                onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                className="password-toggle absolute right-1.5 inline-flex items-center gap-1 rounded-md border border-line bg-surface-alt px-2 py-1 text-[11px] font-medium text-muted hover:text-ink"
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((visible) => !visible)}
                disabled={isSubmitting}
              >
                {showPassword ? <EyeOff className="size-3.5" aria-hidden="true" /> : <Eye className="size-3.5" aria-hidden="true" />}
                <span>{showPassword ? 'Hide' : 'Show'}</span>
              </button>
            </div>
            {passwordInvalid && (
              <p id="login-password-error" className="text-xs text-danger">
                Please enter your password.
              </p>
            )}
          </div>

          <div className="login-feedback min-h-[2.25rem]" id="login-feedback" aria-live="polite" aria-atomic="true">
            {error ? (
              <p className="error rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs font-medium text-danger" role="alert">
                {error}
              </p>
            ) : (
              <p className="text-xs text-muted" role="status">
                {isSubmitting ? 'Signing in securely…' : '\u00a0'}
              </p>
            )}
          </div>

          <button className={`${buttonPrimaryClass} requirement-save-button w-full py-2.5`} type="submit" disabled={isSubmitting}>
            <Lock className="size-3.5" aria-hidden="true" />
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="border-t border-line pt-4 space-y-1.5 text-center text-xs text-muted">
          <p className="auth-switch">To create an account, ask your administrator for an invitation.</p>
          <p className="auth-switch"><a className="font-medium text-accent hover:underline" href="#home">Back to Home</a></p>
        </div>
      </section>
    </main>
  );
}
