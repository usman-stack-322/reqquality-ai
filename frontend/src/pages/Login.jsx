import React, { useState } from 'react';

export default function Login({ onLogin, onRegister, initialEmail = '', notice = '' }) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to log in.');
      onLogin(data);
    } catch (loginError) {
      setError(loginError.message || 'Unable to reach the authentication API.');
    } finally {
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
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="requirement-field">
            <label htmlFor="login-email">Email</label>
            <input id="login-email" type="email" autoComplete="email" maxLength={254} required disabled={isSubmitting} value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="requirement-field">
            <label htmlFor="login-password">Password</label>
            <div className="password-input-row">
              <input id="login-password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required disabled={isSubmitting} value={password} onChange={(event) => setPassword(event.target.value)} />
              <button className="password-toggle" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)} disabled={isSubmitting}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="requirement-save-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="auth-switch">To create an account, ask your administrator for an invitation.</p>
        <p className="auth-switch"><a href="#home">Back to Home</a></p>
      </section>
    </main>
  );
}
