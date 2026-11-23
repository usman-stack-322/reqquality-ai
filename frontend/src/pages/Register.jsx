import React from 'react';
import BrandLogo from '../components/BrandLogo';
import { buttonPrimaryClass } from '../components/ui';

export default function Register({ onLogin }) {
  return (
    <main className="auth-shell w-full max-w-md">
      <section className="card auth-card rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8 space-y-4">
        <div className="auth-brand flex items-center gap-2.5">
          <BrandLogo size={40} />
          <div>
            <span className="eyebrow block text-[11px] font-semibold uppercase tracking-wider text-accent">ReqQuality AI</span>
            <h1 className="text-xl font-bold text-ink">Invitation required</h1>
          </div>
        </div>
        <p className="text-sm leading-relaxed text-muted">
          Ask your administrator for an invitation to create your account. Your email and role are assigned by that invitation.
        </p>
        <button type="button" className={`${buttonPrimaryClass} requirement-save-button w-full py-2.5`} onClick={onLogin}>
          Return to Sign In
        </button>
      </section>
    </main>
  );
}
