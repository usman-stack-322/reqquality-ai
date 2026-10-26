import React, { useState } from 'react';
import BrandLogo from './BrandLogo';
import ThemeSelector from './ThemeSelector';
import { Icon } from './ManagerUI';

export default function WorkspaceShell({ user, canCreate, page, onLogout, children }) {
  const [open, setOpen] = useState(false);
  const title = page === 'requirements' ? 'Add requirement' : page === 'requirement-detail' ? 'Requirement workspace' : 'Dashboard';
  return <div className="workspace-shell">
    {open && <button className="workspace-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`workspace-sidebar ${open ? 'is-open' : ''}`} aria-label="Workspace navigation">
      <a className="workspace-brand" href="#dashboard" onClick={() => setOpen(false)}><BrandLogo /><span>ReqQuality <b>AI</b><small>QUALITY WORKSPACE</small></span></a>
      <div className="workspace-context"><span className="workspace-context-mark">RQ</span><div><strong>Requirements &amp; quality</strong><small>Shared project workspace</small></div></div>
      <p className="workspace-nav-label">WORKSPACE</p>
      <nav>
        <a href="#dashboard" aria-current={page === 'dashboard' ? 'page' : undefined} onClick={() => setOpen(false)}><Icon name="dashboard" size={18} />Dashboard</a>
        {canCreate && <a href="#requirements" aria-current={page === 'requirements' ? 'page' : undefined} onClick={() => setOpen(false)}><Icon name="requirements" size={18} />Add Requirement</a>}
      </nav>
      <div className="workspace-profile"><div className="workspace-avatar">{user.name.slice(0, 1).toUpperCase()}</div><div><strong>{user.name}</strong><small>{user.role}</small></div><button aria-label="Log out" onClick={onLogout}><Icon name="logout" size={18} /></button></div>
    </aside>
    <div className="workspace-main">
      <header className="workspace-topbar"><button className="workspace-mobile-toggle" aria-label="Toggle navigation" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name="dashboard" size={20} /></button><div className="workspace-breadcrumb">Workspace <span>/</span> <strong>{title}</strong></div><ThemeSelector /></header>
      <main>{children}</main>
      <footer className="workspace-footer">ReqQuality AI <span>Requirements, with a clear review path</span></footer>
    </div>
  </div>;
}
