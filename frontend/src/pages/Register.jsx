import React from 'react';

export default function Register({ onLogin }) {
  return <main className="auth-shell"><section className="card auth-card"><p className="eyebrow">REQQUALITY AI</p><h1>Invitation required</h1><p>Ask your administrator for an invitation to create your account. Your email and role are assigned by that invitation.</p><button className="requirement-save-button" onClick={onLogin}>Return to Sign In</button></section></main>;
}
