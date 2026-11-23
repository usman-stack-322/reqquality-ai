import { apiFetch as fetch } from '../api.js';
import React, { useEffect, useState } from 'react';
import BrandLogo from '../components/BrandLogo';
import { buttonPrimaryClass, inputClass } from '../components/ui';

export default function AcceptInvitation({ onRegistered }) {
  const [token] = useState(() => new URLSearchParams(window.location.search).get('token') || '');
  const [stage, setStage] = useState('loading');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [touched, setTouched] = useState({ email: false, password: false, confirm: false });
  const [csrf, setCsrf] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function post(endpoint, body, csrfToken = '') {
    const response = await fetch(`/api/invitations/${endpoint}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) },
      body: JSON.stringify({ token, ...body }),
    });
    const data = await response.json();
    if (!response.ok) {
      const err = new Error(data.error || 'Unable to process this invitation.');
      err.status = response.status;
      throw err;
    }
    return data;
  }

  useEffect(() => {
    let active = true;
    // Keep initializer pure under React StrictMode; remove bearer token after mounting.
    window.history.replaceState(null, '', `${window.location.pathname}#accept-invitation`);
    post('validate', {})
      .then(() => { if (active) setStage('email'); })
      .catch((err) => { if (active) { setStage('invalid'); setError(err.message); } });
    return () => { active = false; };
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (stage === 'email') {
        setTouched((prev) => ({ ...prev, email: true }));
        const result = await post('verify-email', { email: email.trim().toLowerCase() });
        setCsrf(result.csrf_token);
        setStage('password');
      } else {
        setTouched({ email: true, password: true, confirm: true });
        if (password !== confirmPassword) throw new Error('Passwords must match.');
        await post('accept', { password }, csrf);
        setStage('complete');
      }
    } catch (err) {
      setError(err.message);
      if (err.status === 410) setStage('invalid');
    } finally {
      setBusy(false);
    }
  }

  const emailInvalid = touched.email && (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()));
  const passwordInvalid = touched.password && (password.length < 12 || password.length > 128);
  const confirmInvalid = touched.confirm && password !== confirmPassword;

  return (
    <main className="auth-shell w-full max-w-md">
      <section className="card auth-card rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8 space-y-4">
        <div className="auth-brand flex items-center gap-2.5">
          <BrandLogo size={40} />
          <div>
            <span className="eyebrow block text-[11px] font-semibold uppercase tracking-wider text-accent">ReqQuality AI</span>
            <h1 className="text-xl font-bold text-ink">Accept invitation</h1>
          </div>
        </div>

        {stage === 'loading' && <p className="text-xs text-muted" role="status">Validating invitation…</p>}
        {error && (
          <p className="error rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">
            {error}
          </p>
        )}
        {stage === 'email' && <p className="text-xs text-muted">Enter the email address that received this invitation.</p>}
        {stage === 'password' && (
          <p className="success rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">
            Email verified. Set your password to create your account. Your email and role are assigned by the invitation.
          </p>
        )}

        {['email', 'password'].includes(stage) && (
          <form className="auth-form space-y-4" onSubmit={submit}>
            {stage === 'email' ? (
              <div className="requirement-field space-y-1">
                <label htmlFor="invitation-email" className="block text-xs font-semibold text-ink">Email Address</label>
                <span id="invitation-email-hint" className="block text-[11px] text-muted">Use the exact invited email address</span>
                <input
                  id="invitation-email"
                  className={inputClass}
                  type="email"
                  autoComplete="email"
                  maxLength={254}
                  required
                  aria-invalid={emailInvalid ? 'true' : 'false'}
                  aria-describedby={emailInvalid ? 'invitation-email-hint invitation-email-error' : 'invitation-email-hint'}
                  value={email}
                  disabled={busy}
                  onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
                  onChange={(e) => setEmail(e.target.value)}
                />
                {emailInvalid && <p id="invitation-email-error" className="text-xs text-danger">Enter a valid email address.</p>}
              </div>
            ) : (
              <>
                <div className="requirement-field space-y-1">
                  <label htmlFor="invitation-password" className="block text-xs font-semibold text-ink">Password</label>
                  <span id="invitation-password-hint" className="field-hint block text-[11px] text-muted">Use 12–128 characters.</span>
                  <input
                    id="invitation-password"
                    className={inputClass}
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={128}
                    required
                    aria-invalid={passwordInvalid ? 'true' : 'false'}
                    aria-describedby={passwordInvalid ? 'invitation-password-hint invitation-password-error' : 'invitation-password-hint'}
                    value={password}
                    disabled={busy}
                    onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  {passwordInvalid && <p id="invitation-password-error" className="text-xs text-danger">Password must be between 12 and 128 characters.</p>}
                </div>
                <div className="requirement-field space-y-1">
                  <label htmlFor="invitation-confirm" className="block text-xs font-semibold text-ink">Confirm Password</label>
                  <input
                    id="invitation-confirm"
                    className={inputClass}
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={128}
                    required
                    aria-invalid={confirmInvalid ? 'true' : 'false'}
                    aria-describedby={confirmInvalid ? 'invitation-confirm-error' : undefined}
                    value={confirmPassword}
                    disabled={busy}
                    onBlur={() => setTouched((prev) => ({ ...prev, confirm: true }))}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                  {confirmInvalid && <p id="invitation-confirm-error" className="text-xs text-danger">Passwords must match.</p>}
                </div>
              </>
            )}
            <button type="submit" className={`${buttonPrimaryClass} requirement-save-button w-full py-2.5`} disabled={busy}>
              {busy ? 'Please wait...' : stage === 'email' ? 'Verify Email' : 'Create Account'}
            </button>
          </form>
        )}

        {stage === 'complete' && (
          <div className="space-y-3">
            <p className="success rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">
              Account created successfully.
            </p>
            <button type="button" className={`${buttonPrimaryClass} requirement-save-button w-full py-2.5`} onClick={() => onRegistered(email)}>
              Continue to Sign In
            </button>
          </div>
        )}

        {stage === 'invalid' && (
          <p className="text-center text-xs">
            <a className="font-medium text-accent hover:underline" href="/#login">Return to Sign In</a>
          </p>
        )}
      </section>
    </main>
  );
}
