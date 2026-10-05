import React, { useEffect, useState } from 'react';

export default function AcceptInvitation({ onRegistered }) {
  const [token] = useState(() => new URLSearchParams(window.location.search).get('token') || '');
  const [stage, setStage] = useState('loading');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [csrf, setCsrf] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function post(endpoint, body, csrfToken = '') {
    const response = await fetch(`/api/invitations/${endpoint}`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) }, body: JSON.stringify({ token, ...body }) });
    const data = await response.json();
    if (!response.ok) { const err = new Error(data.error || 'Unable to process this invitation.'); err.status = response.status; throw err; }
    return data;
  }
  useEffect(() => {
    let active = true;
    // Keep initializer pure under React StrictMode; remove bearer token after mounting.
    window.history.replaceState(null, '', `${window.location.pathname}#accept-invitation`);
    post('validate', {}).then(() => { if (active) setStage('email'); }).catch((err) => { if (active) { setStage('invalid'); setError(err.message); } });
    return () => { active = false; };
  }, []);
  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      if (stage === 'email') {
        const result = await post('verify-email', { email: email.trim().toLowerCase() });
        setCsrf(result.csrf_token); setStage('password');
      } else {
        if (password !== confirmPassword) throw new Error('Passwords must match.');
        await post('accept', { password }, csrf);
        setStage('complete');
      }
    } catch (err) { setError(err.message); if (err.status === 410) setStage('invalid'); }
    finally { setBusy(false); }
  }
  return <main className="auth-shell"><section className="card auth-card"><p className="eyebrow">REQQUALITY AI</p><h1>Accept invitation</h1>
    {stage === 'loading' && <p role="status">Validating invitation...</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {stage === 'email' && <p>Enter the email address that received this invitation.</p>}
    {stage === 'password' && <p className="success" role="status">Email verified. Set your password to create your account. Your email and role are assigned by the invitation.</p>}
    {['email', 'password'].includes(stage) && <form className="auth-form" onSubmit={submit}>
      {stage === 'email' ? <div className="requirement-field"><label htmlFor="invitation-email">Email Address</label><input id="invitation-email" type="email" autoComplete="email" maxLength={254} required value={email} disabled={busy} onChange={(e) => setEmail(e.target.value)} /></div> : <>
        <div className="requirement-field"><label htmlFor="invitation-password">Password</label><input id="invitation-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} disabled={busy} onChange={(e) => setPassword(e.target.value)} /><span className="field-hint">Use 12–128 characters.</span></div>
        <div className="requirement-field"><label htmlFor="invitation-confirm">Confirm Password</label><input id="invitation-confirm" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmPassword} disabled={busy} onChange={(e) => setConfirmPassword(e.target.value)} /></div>
      </>}
      <button className="requirement-save-button" disabled={busy}>{busy ? 'Please wait...' : stage === 'email' ? 'Verify Email' : 'Create Account'}</button>
    </form>}
    {stage === 'complete' && <><p className="success" role="status">Account created successfully.</p><button className="requirement-save-button" onClick={() => onRegistered(email)}>Continue to Sign In</button></>}
    {stage === 'invalid' && <a href="/#login">Return to Sign In</a>}
  </section></main>;
}
