import React, { useState } from 'react';

export default function PasswordRecovery({ reset, onReset }) {
  const [token] = useState(() => new URLSearchParams(window.location.hash.split('?')[1] || '').get('token') || '');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function submit(event) {
    event.preventDefault();
    setError('');
    if (reset && password !== confirmation) { setError('Passwords do not match.'); return; }
    setBusy(true);
    try {
      const response = await fetch(`/api/auth/${reset ? 'reset-password' : 'forgot-password'}`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reset ? { token, password } : { email: email.trim().toLowerCase() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to process your request.');
      if (reset) onReset(data.message);
      else setMessage(data.message);
    } catch (failure) { setError(failure.message || 'Unable to reach the authentication API.'); }
    finally { setBusy(false); }
  }

  return <main className="auth-shell"><section className="card auth-card" aria-labelledby="recovery-title">
    <p className="eyebrow">REQQUALITY AI</p>
    <h1 id="recovery-title">{reset ? 'Reset password' : 'Forgot password?'}</h1>
    <p className="auth-intro">{reset ? 'Choose a new password with 12 to 128 characters.' : 'Enter your account email to receive a password reset link.'}</p>
    {message ? <p className="success auth-notice" role="status">{message}</p> : <form className="auth-form" onSubmit={submit}>
      {reset ? <>
        <div className="requirement-field"><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy} value={password} onChange={event => setPassword(event.target.value)} /></div>
        <div className="requirement-field"><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy} value={confirmation} onChange={event => setConfirmation(event.target.value)} /></div>
      </> : <div className="requirement-field"><label htmlFor="recovery-email">Email</label><input id="recovery-email" type="email" autoComplete="email" maxLength={254} required disabled={busy} value={email} onChange={event => setEmail(event.target.value)} /></div>}
      {error && <p className="error" role="alert">{error}</p>}
      {reset && !token && <p className="error" role="alert">Missing reset link. Request a new one.</p>}
      <button className="requirement-save-button" type="submit" disabled={busy || (reset && !token)}>{busy ? 'Please wait...' : reset ? 'Reset password' : 'Send reset link'}</button>
    </form>}
    <p className="auth-switch"><a href="#login">Back to sign in</a></p>
    {reset && <p className="auth-switch"><a href="#forgot-password">Request a new reset link</a></p>}
  </section></main>;
}
