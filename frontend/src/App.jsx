import { apiFetch as fetch } from './api.js';
import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import Home from './pages/Home';
import Login from './pages/Login';
import LoadingSkeleton from './components/LoadingSkeleton';
import BrandLogo from './components/BrandLogo';
import ThemeSelector from './components/ThemeSelector';
import WorkspaceShell from './components/WorkspaceShell';

const RequirementInput = lazy(() => import('./pages/RequirementInput'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const RequirementDetails = lazy(() => import('./pages/RequirementDetails'));
const Register = lazy(() => import('./pages/Register'));
const ManagerDashboard = lazy(() => import('./pages/ManagerDashboard'));
const AcceptInvitation = lazy(() => import('./pages/AcceptInvitation'));
const PasswordRecovery = lazy(() => import('./pages/PasswordRecovery'));

class PageBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? (
        <main className="mx-auto my-12 max-w-md rounded-xl border border-line bg-surface p-6 shadow-xs space-y-3">
          <h1 className="text-lg font-bold text-ink">Unable to load this page</h1>
          <p className="text-sm text-danger" role="alert">Check your connection and reload to try again.</p>
          <button type="button" className="rounded-lg bg-accent-strong px-4 py-2 text-xs font-semibold text-on-accent" onClick={() => window.location.reload()}>
            Reload
          </button>
        </main>
      )
      : this.props.children;
  }
}

export default function App() {
  return <PageBoundary><Suspense fallback={<LoadingSkeleton label="Loading workspace" />}><AppContent /></Suspense></PageBoundary>;
}

const PUBLIC_PAGES = ['home', 'login', 'register', 'accept-invitation', 'forgot-password', 'reset-password'];
const WORKSPACE_PAGES = ['dashboard', 'projects', 'review-queue', 'test-cases', 'bugs', 'reports'];

function currentPage() {
  const hash = window.location.hash.slice(1);
  if (hash.startsWith('reset-password?')) return 'reset-password';
  if (['forgot-password', 'reset-password'].includes(hash)) return hash;
  if (hash === 'accept-invitation' || (window.location.pathname === '/accept-invitation' && new URLSearchParams(window.location.search).has('token'))) return 'accept-invitation';
  if (window.location.pathname === '/admin' && !hash) return 'admin';
  if (/^admin(?:\/|\?|$)/.test(hash)) return 'admin';
  if (/^requirement\/\d+$/.test(hash)) return 'requirement-detail';
  return ['home', 'requirements', 'login', 'register', 'admin', ...WORKSPACE_PAGES].includes(hash)
    ? hash
    : 'home';
}

function AppFooter({ user }) {
  return (
    <footer className="app-footer border-t border-line bg-surface px-4 py-8 text-muted sm:px-6">
      <div className="footer-inner mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="footer-brand-block space-y-1.5">
          <a className="footer-brand inline-flex items-center gap-2.5 text-sm font-bold text-ink no-underline" href={user ? (['admin', 'Manager'].includes(user.role) ? '#admin' : '#dashboard') : '#home'}>
            <BrandLogo size={32} />
            <span className="footer-brand-name">ReqQuality <span className="text-accent">AI</span></span>
          </a>
          <p className="text-xs text-muted">AI-Powered Requirements &amp; Software Quality Engineering Platform</p>
        </div>
        <nav className="footer-nav flex flex-wrap gap-4 text-xs" aria-label="Footer navigation">
          {!user && <a className="text-muted hover:text-ink no-underline" href="#home">Home</a>}
          {user?.role !== 'admin' && user?.permissions?.includes('create_requirements') && <a className="text-muted hover:text-ink no-underline" href="#requirements">Add Requirement</a>}
          {user ? <a className="text-muted hover:text-ink no-underline" href="#dashboard">Dashboard</a> : <a className="text-muted hover:text-ink no-underline" href="#login">Sign in</a>}
        </nav>
        <div className="footer-meta flex items-center gap-2 text-xs text-muted">
          <span>Final Year Project</span>
          <span>·</span>
          <span>{new Date().getFullYear()}</span>
        </div>
      </div>
    </footer>
  );
}

function AccountShell({ children }) {
  return (
    <div className="app-shell public-account-shell flex min-h-screen flex-col bg-canvas text-ink">
      <header className="public-auth-header mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-5 sm:px-6">
        <a className="inline-flex items-center gap-2.5 text-sm font-semibold text-ink no-underline hover:text-accent" href="#home">
          <BrandLogo size={28} />
          <span>ReqQuality <span className="text-accent">AI</span></span>
        </a>
        <ThemeSelector />
      </header>
      <div className="flex flex-1 items-center justify-center px-4 pb-12 sm:px-6">{children}</div>
    </div>
  );
}

function AppContent() {
  const [page, setPage] = useState(currentPage);
  const [user, setUser] = useState(null);
  const [csrfToken, setCsrfToken] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginNotice, setLoginNotice] = useState('');
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [logoutError, setLogoutError] = useState('');
  const [sessionError, setSessionError] = useState('');
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const logoutLock = useRef(false);
  const canCreate = user?.project_access !== false && user?.role !== 'admin' && user?.permissions?.includes('create_requirements');
  const sessionRequest = useRef(null);
  const authRevision = useRef(0);

  useEffect(() => {
    const titles = {
      home: 'Requirements & Quality Engineering',
      login: 'Sign in',
      register: 'Invitation required',
      'forgot-password': 'Password recovery',
      'reset-password': 'Reset password',
      dashboard: 'Requirements',
      projects: 'Projects',
      'review-queue': 'Review Queue',
      'test-cases': 'Test Cases',
      bugs: 'Bugs & Defects',
      reports: 'Reports',
      requirements: 'New requirement',
      'requirement-detail': 'Requirement workspace',
      admin: 'Quality management',
      'accept-invitation': 'Accept invitation',
    };
    document.title = `ReqQuality AI | ${titles[page] || 'Workspace'}`;
  }, [page]);

  useEffect(() => {
    const onHashChange = () => {
      const next = currentPage();
      if (!user && !PUBLIC_PAGES.includes(next)) setIsCheckingSession(true);
      setPage(next);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [user]);

  useEffect(() => {
    let active = true;
    const revision = authRevision.current;
    // Public pages must not compete with an explicit login for refresh cookies,
    // database connections or cold-start capacity. Restore only at a protected route.
    if (user || PUBLIC_PAGES.includes(page)) {
      setIsCheckingSession(false);
      return;
    }
    setIsCheckingSession(true);
    async function loadSession() {
      try {
        // Share the bootstrap across StrictMode's effect replay, without caching auth.
        sessionRequest.current ||= fetch('/api/auth/me', { credentials: 'include' }).then((response) => {
          if (!response.ok) throw new Error('Session lookup failed');
          return response.json();
        });
        const data = await sessionRequest.current;
        if (!active || revision !== authRevision.current) return;
        if (data.authenticated) {
          setUser(data.user);
          setCsrfToken(data.csrf_token || '');
        }
      } catch {
        if (active && revision === authRevision.current) {
          setUser(null);
          setSessionError('Unable to restore your session. Check your connection and retry.');
        }
      } finally {
        if (active && revision === authRevision.current) setIsCheckingSession(false);
      }
    }
    loadSession();
    return () => { active = false; };
  }, [sessionAttempt, page]);

  useEffect(() => {
    if (isCheckingSession || sessionError) return;
    if (['accept-invitation', 'forgot-password', 'reset-password'].includes(page)) return;
    // Let a protected navigation finish its session check before redirecting.
    if (!user && !['home', 'login', 'register'].includes(page) && sessionRequest.current) {
      window.location.hash = 'login';
    } else if (user && ['home', 'login', 'register'].includes(page)) {
      window.location.hash = ['admin', 'Manager'].includes(user?.role) ? 'admin' : 'dashboard';
    } else if (user && !canCreate && page === 'requirements') {
      window.location.hash = 'dashboard';
    }
  }, [isCheckingSession, sessionError, page, user, canCreate]);

  async function handleLogout() {
    if (logoutLock.current) return;
    logoutLock.current = true;
    setLogoutError('');
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to log out.');
      authRevision.current++;
      sessionRequest.current = null;
      setUser(null);
      setCsrfToken('');
      window.location.hash = 'login';
    } catch (error) {
      setLogoutError(error.message || 'Unable to reach the authentication API.');
    } finally {
      logoutLock.current = false;
    }
  }

  const publicPage = PUBLIC_PAGES.includes(page);
  if (sessionError && !publicPage) {
    return (
      <div className="app-shell flex min-h-screen items-center justify-center bg-canvas p-6">
        <main className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-xs space-y-4">
          <h1 className="text-lg font-bold text-ink">Session unavailable</h1>
          <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{sessionError}</p>
          <div className="flex flex-wrap gap-2.5">
            <button
              type="button"
              className="rounded-lg bg-accent-strong px-4 py-2 text-xs font-semibold text-on-accent"
              onClick={() => {
                sessionRequest.current = null;
                setSessionError('');
                setIsCheckingSession(true);
                setSessionAttempt((v) => v + 1);
              }}
            >
              Retry session
            </button>
            <button
              type="button"
              className="rounded-lg border border-line bg-surface px-4 py-2 text-xs font-semibold text-ink hover:bg-surface-alt"
              onClick={() => {
                setSessionError('');
                window.location.hash = 'login';
              }}
            >
              Sign in
            </button>
          </div>
        </main>
      </div>
    );
  }

  if ((isCheckingSession && !publicPage) || (user && ['home', 'login', 'register'].includes(page))) {
    return (
      <div className="app-shell min-h-screen bg-canvas p-6">
        <main className="mx-auto max-w-6xl"><LoadingSkeleton label="Loading your secure workspace" /></main>
      </div>
    );
  }

  if (['forgot-password', 'reset-password'].includes(page)) {
    return (
      <AccountShell>
        <PasswordRecovery
          key={page}
          reset={page === 'reset-password'}
          onReset={(message) => {
            authRevision.current++;
            setIsCheckingSession(false);
            setUser(null);
            setCsrfToken('');
            setLoginNotice(message);
            window.history.replaceState(null, '', '/#login');
            setPage('login');
          }}
        />
      </AccountShell>
    );
  }

  if (page === 'accept-invitation') {
    return (
      <AccountShell>
        <AcceptInvitation
          onRegistered={(email) => {
            authRevision.current++;
            setIsCheckingSession(false);
            setUser(null);
            setCsrfToken('');
            setLoginEmail(email);
            setLoginNotice('Account created successfully. Sign in with your new credentials.');
            window.history.replaceState(null, '', '/#login');
            setPage('login');
          }}
        />
      </AccountShell>
    );
  }

  if (!user && page === 'register') {
    return <AccountShell><Register onLogin={() => { window.location.hash = 'login'; }} /></AccountShell>;
  }

  if (!user && page !== 'home') {
    return (
      <AccountShell>
        <Login
          initialEmail={loginEmail}
          notice={loginNotice}
          onLogin={(data) => {
            authRevision.current++;
            setIsCheckingSession(false);
            setUser(data.user);
            setCsrfToken(data.csrf_token);
            setLoginNotice('');
            setSessionError('');
            window.location.hash = ['admin', 'Manager'].includes(data.user.role) ? 'admin' : 'dashboard';
          }}
        />
      </AccountShell>
    );
  }

  if (['admin', 'Manager'].includes(user?.role) && ['admin', 'requirement-detail', ...WORKSPACE_PAGES].includes(page)) {
    return (
      <ManagerDashboard
        user={user}
        csrfToken={csrfToken}
        onLogout={handleLogout}
        logoutError={logoutError}
        onSignedOut={(message) => {
          setUser(null);
          setCsrfToken('');
          setLoginNotice(message);
          window.location.hash = 'login';
        }}
      />
    );
  }

  let content;
  if (page === 'admin') {
    content = (
      <section className="rounded-xl border border-line bg-surface p-6 shadow-xs space-y-2">
        <h1 className="text-lg font-bold text-ink">Forbidden</h1>
        <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">
          Your account does not have permission to access the Admin Panel.
        </p>
      </section>
    );
  } else if (page === 'requirements' && canCreate) {
    content = <RequirementInput csrfToken={csrfToken} />;
  } else if (page === 'requirement-detail') {
    content = (
      <RequirementDetails
        requirementId={Number(window.location.hash.slice('#requirement/'.length))}
        user={user}
        csrfToken={csrfToken}
      />
    );
  } else if (page === 'home') {
    content = <Home user={user} />;
  } else {
    content = <Dashboard user={user} section={page} />;
  }

  if (user) {
    return (
      <WorkspaceShell user={user} canCreate={canCreate} page={page} onLogout={handleLogout}>
        {logoutError && (
          <p className="mb-4 rounded-xl border border-danger/30 bg-danger-tint px-4 py-2.5 text-xs text-danger" role="alert">
            {logoutError}
          </p>
        )}
        {content}
      </WorkspaceShell>
    );
  }

  return (
    <div className="app-shell flex min-h-screen flex-col bg-canvas text-ink">
      <header className="app-header sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur-xs">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <a className="brand inline-flex items-center gap-2.5 text-base font-bold text-ink no-underline" href="#home" aria-label="ReqQuality AI home">
            <BrandLogo size={32} />
            <span>ReqQuality <span className="brand-ai text-accent">AI</span></span>
          </a>
          <nav className="hidden sm:flex items-center gap-2" aria-label="Main navigation">
            <a className="rounded-lg px-3 py-1.5 text-xs font-medium text-ink bg-surface-alt no-underline" href="#home" aria-current={page === 'home' ? 'page' : undefined}>Home</a>
            <a className="rounded-lg px-3 py-1.5 text-xs font-medium text-muted hover:text-ink no-underline" href="#workflow">Workflow</a>
          </nav>
          <div className="account-bar flex items-center gap-3">
            <ThemeSelector />
            <a className="inline-flex items-center justify-center rounded-lg bg-accent-strong px-3.5 py-2 text-xs font-semibold text-on-accent no-underline hover:brightness-110" href="#login">
              Sign in
            </a>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
        {content}
        {logoutError && <p className="error mt-4 text-xs text-danger" role="alert">{logoutError}</p>}
      </main>
      <AppFooter user={user} />
    </div>
  );
}
