import React, { useState } from 'react';

export default function Register({ onLogin, onRegistered }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState('Analyst');
  const [reviewerCode, setReviewerCode] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          email: email.trim().toLowerCase(),
          password,
          role,
          ...(role === 'SQA Reviewer' ? { reviewer_code: reviewerCode } : {}),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to create the account.');
      onRegistered(email.trim().toLowerCase());
    } catch (registrationError) {
      setError(registrationError.message || 'Unable to reach the authentication API.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="card auth-card" aria-labelledby="register-title">
        <p className="eyebrow">REQQUALITY AI</p>
        <h1 id="register-title">Create account</h1>
        <p className="auth-intro">Register as an Analyst or an SQA Reviewer.</p>
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="requirement-field">
            <label htmlFor="register-name">Name</label>
            <input id="register-name" type="text" autoComplete="name" minLength={2} maxLength={80} required disabled={isSubmitting} value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="requirement-field">
            <label htmlFor="register-email">Email</label>
            <input id="register-email" type="email" autoComplete="email" maxLength={254} required disabled={isSubmitting} value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="requirement-field">
            <label htmlFor="register-password">Password</label>
            <div className="password-input-row">
              <input id="register-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" minLength={12} maxLength={128} required disabled={isSubmitting} value={password} onChange={(event) => setPassword(event.target.value)} />
              <button className="password-toggle" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)} disabled={isSubmitting}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            <span className="field-hint">Use at least 12 characters.</span>
          </div>
          <div className="requirement-field">
            <label htmlFor="register-role">Role</label>
            <select id="register-role" value={role} disabled={isSubmitting} onChange={(event) => setRole(event.target.value)}>
              <option>Analyst</option>
              <option>SQA Reviewer</option>
            </select>
          </div>
          {role === 'SQA Reviewer' && (
            <div className="requirement-field">
              <label htmlFor="reviewer-code">SQA Reviewer registration code</label>
              <input id="reviewer-code" type="password" autoComplete="off" required disabled={isSubmitting} value={reviewerCode} onChange={(event) => setReviewerCode(event.target.value)} />
              <span className="field-hint">The project administrator provides this code.</span>
            </div>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <button className="requirement-save-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account...' : 'Create account'}
          </button>
        </form>
        <p className="auth-switch">Already registered? <button type="button" className="text-button" onClick={onLogin}>Sign in</button></p>
      </section>
    </main>
  );
}