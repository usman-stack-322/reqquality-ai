import React, { useEffect, useState } from 'react';
import Home from './pages/Home';
import RequirementInput from './pages/RequirementInput';
import Dashboard from './pages/Dashboard';
import RequirementDetails from './pages/RequirementDetails';
import Login from './pages/Login';
import Register from './pages/Register';
import ManagerDashboard from './pages/ManagerDashboard';
import AcceptInvitation from './pages/AcceptInvitation';
import PasswordRecovery from './pages/PasswordRecovery';

function currentPage() {
  const hash = window.location.hash.slice(1);
  if (hash.startsWith('reset-password?')) return 'reset-password';
  if (['forgot-password', 'reset-password'].includes(hash)) return hash;
  if (hash === 'accept-invitation' || (window.location.pathname === '/accept-invitation' && new URLSearchParams(window.location.search).has('token'))) return 'accept-invitation';
  if (window.location.pathname === '/admin' && !hash) return 'admin';
  if (/^admin(?:\/|\?|$)/.test(hash)) return 'admin';
  if (/^requirement\/\d+$/.test(hash)) return 'requirement-detail';
  return ['home', 'requirements', 'dashboard', 'login', 'register', 'admin'].includes(hash)
    ? hash
    : 'home';
}

function AppFooter({ user }) {
  return (
    <footer className="app-footer">
      <div className="footer-inner">
        <div className="footer-brand-block">
          <a className="footer-brand" href={user ? (['admin', 'Manager'].includes(user.role) ? '#admin' : '#dashboard') : '#home'}>ReqQuality <span>AI</span></a>
          <p>AI-Powered Requirements &amp; Software Quality Engineering Platform</p>
        </div>
        <nav className="footer-nav" aria-label="Footer navigation">
          {!user && <a href="#home">Home</a>}
          {user?.permissions?.includes('create_requirements') && <a href="#requirements">Add Requirement</a>}
          {user ? <a href="#dashboard">Dashboard</a> : <a href="#login">Sign in</a>}
        </nav>
        <div className="footer-meta"><span>Final Year Project</span><span>{new Date().getFullYear()}</span></div>
      </div>
    </footer>
  );
}

export default function App() {
  const [page, setPage] = useState(currentPage);
  const [user, setUser] = useState(null);
  const [csrfToken, setCsrfToken] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginNotice, setLoginNotice] = useState('');
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [logoutError, setLogoutError] = useState('');

  useEffect(() => {
    const onHashChange = () => setPage(currentPage());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    async function loadSession() {
      try {
        const response = await fetch('/api/auth/me', { credentials: 'include' });
        const data = await response.json();
        if (data.authenticated) {
          setUser(data.user);
          setCsrfToken(data.csrf_token || '');
        }
      } catch {
        setUser(null);
      } finally {
        setIsCheckingSession(false);
      }
    }
    loadSession();
  }, []);

  useEffect(() => {
    if (isCheckingSession) return;
    if (['accept-invitation', 'forgot-password', 'reset-password'].includes(page)) return;
    if (!user && !['home', 'login', 'register'].includes(page)) {
      window.location.hash = 'login';
    } else if (user && ['home', 'login', 'register'].includes(page)) {
      window.location.hash = ['admin', 'Manager'].includes(user?.role) ? 'admin' : 'dashboard';
    } else if (user && !user.permissions?.includes('create_requirements') && page === 'requirements') {
      window.location.hash = 'dashboard';
    }
  }, [isCheckingSession, page, user]);

  async function handleLogout() {
    setLogoutError('');
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to log out.');
      setUser(null);
      setCsrfToken('');
      window.location.hash = 'login';
    } catch (error) {
      setLogoutError(error.message || 'Unable to reach the authentication API.');
    }
  }

  if (isCheckingSession || (user && ['home', 'login', 'register'].includes(page))) {
    return (
      <div className="app-shell">
        <main><p className="requirements-empty">Checking your session...</p></main>
      </div>
    );
  }

  if (['forgot-password', 'reset-password'].includes(page)) {
    return <div className="app-shell"><PasswordRecovery key={page} reset={page === 'reset-password'} onReset={(message) => {
      setUser(null); setCsrfToken(''); setLoginNotice(message);
      window.history.replaceState(null, '', '/#login'); setPage('login');
    }} /></div>;
  }
  if (page === 'accept-invitation') {
    return <div className="app-shell"><AcceptInvitation onRegistered={(email) => {
      setUser(null);
      setCsrfToken('');
      setLoginEmail(email);
      setLoginNotice('Account created successfully. Sign in with your new credentials.');
      window.history.replaceState(null, '', '/#login');
      setPage('login');
    }} /></div>;
  }
  if (!user && page === 'register') {
    return <div className="app-shell"><Register onLogin={() => { window.location.hash = 'login'; }} /></div>;
  }
  if (!user && page !== 'home') {
    return <div className="app-shell"><Login initialEmail={loginEmail} notice={loginNotice} onLogin={(data) => {
      setUser(data.user); setCsrfToken(data.csrf_token); setLoginNotice('');
      window.location.hash = ['admin', 'Manager'].includes(data.user.role) ? 'admin' : 'dashboard';
    }} /></div>;
  }

  if (['admin', 'Manager'].includes(user?.role) && ['admin', 'dashboard', 'requirement-detail'].includes(page)) {
    return <ManagerDashboard user={user} csrfToken={csrfToken} onLogout={handleLogout} logoutError={logoutError} onSignedOut={(message) => {
      setUser(null); setCsrfToken(''); setLoginNotice(message); window.location.hash = 'login';
    }} />;
  }

  let content;
  if (page === 'admin') {
    content = <section className="card"><h1>Forbidden</h1><p className="error" role="alert">Your account does not have permission to access the Admin Panel.</p></section>;
  } else if (page === 'requirements' && user.permissions?.includes('create_requirements')) {
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
    content = <Dashboard user={user} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href={user ? (['admin', 'Manager'].includes(user.role) ? '#admin' : '#dashboard') : '#home'} aria-label={user ? 'ReqQuality AI workspace' : 'ReqQuality AI home'}>
          <span className="brand-mark" aria-hidden="true">RQ</span>
          <span>ReqQuality <span className="brand-ai">AI</span></span>
        </a>
        <nav aria-label="Main navigation">
          {['admin', 'Manager'].includes(user?.role) && <a href="#admin" aria-current={page === 'admin' ? 'page' : undefined}>Admin Panel</a>}
          {!user && <a href="#home" aria-current={page === 'home' ? 'page' : undefined}>Home</a>}
          {user?.permissions?.includes('create_requirements') && (
            <a href="#requirements" aria-current={page === 'requirements' ? 'page' : undefined}>Add Requirement</a>
          )}
          {user && <a href="#dashboard" aria-current={page === 'dashboard' || page === 'requirement-detail' ? 'page' : undefined}>Dashboard</a>}
        </nav>
        <div className="account-bar">
          {user ? <>
            <div className="account-identity"><strong>{user.name}</strong><span>{user.role}</span></div>
            <button className="logout-button" type="button" onClick={handleLogout}>Log out</button>
          </> : <a className="button" href="#login">Sign in</a>}
        </div>
      </header>
      <main className={page === 'home' ? 'home-main' : undefined}>{content}{logoutError && <p className="error" role="alert">{logoutError}</p>}</main>
      <AppFooter user={user} />
    </div>
  );
}
