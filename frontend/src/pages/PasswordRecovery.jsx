import { apiFetch as fetch } from '../api.js';
import React, { useState } from 'react';
import BrandLogo from '../components/BrandLogo';
import { buttonPrimaryClass, inputClass } from '../components/ui';

const RECOVERY_UNAVAILABLE = 'The password reset service is temporarily unavailable. Please try again later.';

export default function PasswordRecovery({ reset, onReset }) {
  const [token] = useState(() => new URLSearchParams(window.location.hash.split('?')[1] || '').get('token') || '');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [touched, setTouched] = useState({ email: false, password: false, confirm: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function submit(event) {
    event.preventDefault();
    setTouched({ email: true, password: true, confirm: true });
    setError('');
    if (reset && password !== confirmation) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/auth/${reset ? 'reset-password' : 'forgot-password'}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reset ? { token, password } : { email: email.trim().toLowerCase() }),
      });
      const data = await response.json().catch(() => null);
      if (response.status >= 500 || !data || typeof data !== 'object' || Array.isArray(data)) {
        throw new Error(RECOVERY_UNAVAILABLE);
      }
      if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : 'Unable to process your request.');
      if (typeof data.message !== 'string' || !data.message.trim()) throw new Error(RECOVERY_UNAVAILABLE);
      if (reset) onReset(data.message);
      else setMessage(data.message);
    } catch (failure) {
      setError(failure instanceof TypeError ? RECOVERY_UNAVAILABLE : failure.message || RECOVERY_UNAVAILABLE);
    } finally {
      setBusy(false);
    }
  }

  const emailInvalid = !reset && touched.email && (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()));
  const passwordInvalid = reset && touched.password && (password.length < 12 || password.length > 128);
  const confirmInvalid = reset && touched.confirm && password !== confirmation;

  return (
    <main className="auth-shell w-full max-w-md">
      <section className="card auth-card rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8 space-y-4" aria-labelledby="recovery-title">
        <div className="auth-brand flex items-center gap-2.5">
          <BrandLogo size={40} />
          <div>
            <span className="eyebrow block text-[11px] font-semibold uppercase tracking-wider text-accent">ReqQuality AI</span>
            <h1 id="recovery-title" className="text-xl font-bold text-ink">{reset ? 'Reset password' : 'Forgot password?'}</h1>
          </div>
        </div>
        <p className="auth-intro text-xs text-muted">
          {reset ? 'Choose a new password with 12 to 128 characters.' : 'Enter your account email to receive a password reset link.'}
        </p>

        {message ? (
          <p className="rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">
            {message}
          </p>
        ) : (
          <form className="auth-form space-y-4" onSubmit={submit}>
            {reset ? (
              <>
                <div className="requirement-field space-y-1">
                  <label htmlFor="new-password" className="block text-xs font-semibold text-ink">New password</label>
                  <span id="new-password-hint" className="block text-[11px] text-muted">12 to 128 characters</span>
                  <input
                    id="new-password"
                    className={inputClass}
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={12}
                    maxLength={128}
                    aria-invalid={passwordInvalid ? 'true' : 'false'}
                    aria-describedby={passwordInvalid ? 'new-password-hint new-password-error' : 'new-password-hint'}
                    disabled={busy}
                    value={password}
                    onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  {passwordInvalid && <p id="new-password-error" className="text-xs text-danger">Use 12 to 128 characters.</p>}
                </div>
                <div className="requirement-field space-y-1">
                  <label htmlFor="confirm-password" className="block text-xs font-semibold text-ink">Confirm password</label>
                  <input
                    id="confirm-password"
                    className={inputClass}
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={12}
                    maxLength={128}
                    aria-invalid={confirmInvalid ? 'true' : 'false'}
                    aria-describedby={confirmInvalid ? 'confirm-password-error' : undefined}
                    disabled={busy}
                    value={confirmation}
                    onBlur={() => setTouched((prev) => ({ ...prev, confirm: true }))}
                    onChange={(event) => setConfirmation(event.target.value)}
                  />
                  {confirmInvalid && <p id="confirm-password-error" className="text-xs text-danger">Passwords do not match.</p>}
                </div>
              </>
            ) : (
              <div className="requirement-field space-y-1">
                <label htmlFor="recovery-email" className="block text-xs font-semibold text-ink">Email</label>
                <span id="recovery-email-hint" className="block text-[11px] text-muted">Format: you@example.com</span>
                <input
                  id="recovery-email"
                  className={inputClass}
                  type="email"
                  autoComplete="email"
                  maxLength={254}
                  required
                  aria-invalid={emailInvalid ? 'true' : 'false'}
                  aria-describedby={emailInvalid ? 'recovery-email-hint recovery-email-error' : 'recovery-email-hint'}
                  disabled={busy}
                  value={email}
                  onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
                  onChange={(event) => setEmail(event.target.value)}
                />
                {emailInvalid && <p id="recovery-email-error" className="text-xs text-danger">Please enter a valid email address.</p>}
              </div>
            )}

            {error && (
              <p className="error rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">
                {error}
              </p>
            )}
            {reset && !token && (
              <p className="error rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">
                Missing reset link. Request a new one.
              </p>
            )}
            <button className={`${buttonPrimaryClass} requirement-save-button w-full py-2.5`} type="submit" disabled={busy || (reset && !token)}>
              {busy ? 'Please wait...' : reset ? 'Reset password' : 'Send reset link'}
            </button>
          </form>
        )}

        <div className="border-t border-line pt-3 space-y-1 text-center text-xs">
          <p className="auth-switch"><a className="font-medium text-accent hover:underline" href="#login">Back to sign in</a></p>
          {reset && <p className="auth-switch"><a className="font-medium text-accent hover:underline" href="#forgot-password">Request a new reset link</a></p>}
        </div>
      </section>
    </main>
  );
}
