import React, { useEffect, useState } from 'react';
import Home from './pages/Home';
import RequirementInput from './pages/RequirementInput';
import Dashboard from './pages/Dashboard';
import RequirementDetails from './pages/RequirementDetails';
import Login from './pages/Login';
import Register from './pages/Register';

function currentPage() {
  const hash = window.location.hash.slice(1);
  if (/^requirement\/\d+$/.test(hash)) return 'requirement-detail';
  return ['home', 'requirements', 'dashboard', 'login', 'register'].includes(hash)
    ? hash
    : 'home';
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
    if (!user && !['login', 'register'].includes(page)) {
      window.location.hash = 'login';
    } else if (user && ['login', 'register'].includes(page)) {
      window.location.hash = 'dashboard';
    } else if (user?.role === 'SQA Reviewer' && page === 'requirements') {
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

  if (isCheckingSession) {
    return <main><p className="requirements-empty">Checking your session...</p></main>;
  }

  if (!user) {
    return page === 'register'
      ? <Register
        onLogin={() => { window.location.hash = 'login'; }}
        onRegistered={(email) => {
          setLoginEmail(email);
          setLoginNotice('Account created successfully. Sign in with your new credentials.');
          window.location.hash = 'login';
        }}
      />
      : <Login initialEmail={loginEmail} notice={loginNotice} onLogin={(data) => {
        setUser(data.user);
        setCsrfToken(data.csrf_token);
        setLoginNotice('');
        window.location.hash = 'dashboard';
      }} onRegister={() => { window.location.hash = 'register'; }} />;
  }

  let content;
  if (page === 'requirements' && user.role === 'Analyst') {
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
    <>
      <header className="app-header">
        <a className="brand" href="#dashboard" aria-label="ReqQuality AI dashboard">
          <span className="brand-mark" aria-hidden="true">RQ</span>
          <span>ReqQuality <span className="brand-ai">AI</span></span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#home" aria-current={page === 'home' ? 'page' : undefined}>Home</a>
          {user.role === 'Analyst' && (
            <a href="#requirements" aria-current={page === 'requirements' ? 'page' : undefined}>Add Requirement</a>
          )}
          <a href="#dashboard" aria-current={page === 'dashboard' || page === 'requirement-detail' ? 'page' : undefined}>Dashboard</a>
        </nav>
        <div className="account-bar">
          <div className="account-identity"><strong>{user.name}</strong><span>{user.role}</span></div>
          <button className="logout-button" type="button" onClick={handleLogout}>Log out</button>
        </div>
      </header>
      <main className={page === 'home' ? 'home-main' : undefined}>{content}{logoutError && <p className="error" role="alert">{logoutError}</p>}</main>
      <footer className="app-footer">
        <div className="footer-inner">
          <div className="footer-brand-block">
            <a className="footer-brand" href="#home">ReqQuality <span>AI</span></a>
            <p>AI-Powered Requirements &amp; Software Quality Engineering Platform</p>
          </div>
          <nav className="footer-nav" aria-label="Footer navigation">
            <a href="#home">Home</a>
            {user.role === 'Analyst' && <a href="#requirements">Add Requirement</a>}
            <a href="#dashboard">Dashboard</a>
          </nav>
          <div className="footer-meta"><span>Final Year Project</span><span>{new Date().getFullYear()}</span></div>
        </div>
      </footer>
    </>
  );
}
