import React from 'react';
import BrandLogo from '../components/BrandLogo';

export default function Register({ onLogin }) {
  return <main className="auth-shell"><section className="card auth-card"><div className="auth-brand"><BrandLogo size={48} /><span className="eyebrow">REQQUALITY AI</span></div><h1>Invitation required</h1><p>Ask your administrator for an invitation to create your account. Your email and role are assigned by that invitation.</p><button className="requirement-save-button" onClick={onLogin}>Return to Sign In</button></section></main>;
}
