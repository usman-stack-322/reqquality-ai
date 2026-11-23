import React, { useEffect, useState } from 'react';
import {
  Activity,
  Bug,
  ClipboardCheck,
  FileBarChart2,
  FileText,
  FlaskConical,
  FolderKanban,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  Shield,
  Users,
  X,
} from 'lucide-react';
import BrandLogo from './BrandLogo';
import ThemeSelector from './ThemeSelector';
import { StatusBadge, roleLabel } from './ui';

const COLLAPSE_KEY = 'reqquality-sidebar-collapsed';

function defaultNavGroups(user, canCreate) {
  const workspace = [
    { key: 'projects', label: 'Projects', href: '#projects', Icon: FolderKanban },
    { key: 'dashboard', label: 'Requirements', href: '#dashboard', Icon: FileText },
    ...(canCreate ? [{ key: 'requirements', label: 'New Requirement', href: '#requirements', Icon: Plus }] : []),
    { key: 'review-queue', label: 'Review Queue', href: '#review-queue', Icon: ClipboardCheck },
    { key: 'test-cases', label: 'Test Cases', href: '#test-cases', Icon: FlaskConical },
    { key: 'bugs', label: 'Bugs', href: '#bugs', Icon: Bug },
    { key: 'reports', label: 'Reports', href: '#reports', Icon: FileBarChart2 },
  ];
  const groups = [{ title: 'Workspace', items: workspace }];
  if (['admin', 'Manager'].includes(user?.role)) {
    groups.push({
      title: 'Administration',
      items: [{ key: 'admin', label: 'Admin', href: '#admin', Icon: Shield }],
    });
  }
  return groups;
}

const DEFAULT_TITLES = {
  dashboard: 'Requirements',
  projects: 'Projects',
  requirements: 'New Requirement',
  'requirement-detail': 'Requirement Workspace',
  'review-queue': 'Review Queue',
  'test-cases': 'Test Cases',
  bugs: 'Bugs & Defects',
  reports: 'Reports & Exports',
  admin: 'Admin',
};

export const ADMIN_NAV_ICONS = {
  dashboard: LayoutDashboard,
  projects: FolderKanban,
  requirements: FileText,
  reviews: ClipboardCheck,
  traceability: FlaskConical,
  reports: FileBarChart2,
  team: Users,
  invitations: Mail,
  permissions: KeyRound,
  activity: Activity,
  settings: Settings,
};

export default function WorkspaceShell({
  user,
  canCreate = false,
  page,
  breadcrumb,
  navGroups,
  searchSlot,
  actionsSlot,
  onLogout,
  children,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return typeof window !== 'undefined' && window.localStorage?.getItem(COLLAPSE_KEY) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mobileOpen]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage?.setItem(COLLAPSE_KEY, next ? '1' : '0');
      } catch { /* Ignore denied storage */ }
      return next;
    });
  }

  const groups = navGroups || defaultNavGroups(user, canCreate);
  const activeCrumb = breadcrumb || DEFAULT_TITLES[page] || 'Workspace';
  const userRole = roleLabel(user?.role);

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px] lg:hidden"
          aria-label="Close navigation menu"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        aria-label="Workspace navigation"
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-line bg-surface transition-all duration-150 ${
          mobileOpen ? 'translate-x-0 w-64' : '-translate-x-full w-64 lg:translate-x-0'
        } ${collapsed ? 'lg:w-[68px]' : 'lg:w-64'}`}
      >
        <div className={`flex h-16 items-center border-b border-line px-3 ${collapsed ? 'lg:justify-center' : 'justify-between'}`}>
          <a
            className="flex items-center gap-2.5 text-ink no-underline min-w-0"
            href={['admin', 'Manager'].includes(user?.role) ? '#admin' : '#dashboard'}
            onClick={() => setMobileOpen(false)}
          >
            <BrandLogo size={32} />
            <span className={`truncate text-sm font-bold tracking-tight ${collapsed ? 'lg:hidden' : ''}`}>
              ReqQuality <span className="text-accent">AI</span>
            </span>
          </a>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-surface-alt hover:text-ink lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={toggleCollapsed}
            className={`hidden lg:inline-flex size-7 items-center justify-center rounded-md text-muted hover:bg-surface-alt hover:text-ink ${
              collapsed ? 'lg:hidden' : ''
            }`}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="size-4" aria-hidden="true" />
          </button>
        </div>

        {collapsed && (
          <div className="hidden lg:flex justify-center border-b border-line py-2">
            <button
              type="button"
              onClick={toggleCollapsed}
              className="inline-flex size-8 items-center justify-center rounded-md text-muted hover:bg-surface-alt hover:text-ink"
              aria-label="Expand sidebar"
              title="Expand sidebar"
            >
              <PanelLeftOpen className="size-4" aria-hidden="true" />
            </button>
          </div>
        )}

        <div className={`px-3 pt-4 pb-2 ${collapsed ? 'lg:hidden' : ''}`}>
          <div className="flex items-center gap-2.5 rounded-xl border border-line bg-surface-alt/70 px-2.5 py-2">
            <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent-tint text-xs font-bold text-accent">
              RQ
            </span>
            <div className="min-w-0">
              <strong className="block truncate text-xs font-semibold text-ink">ReqQuality AI</strong>
              <small className="block truncate text-[11px] text-muted">Project: current</small>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-5">
          {groups.map((group) => (
            <div key={group.title} className="space-y-1">
              <p className={`px-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted ${collapsed ? 'lg:hidden' : ''}`}>
                {group.title}
              </p>
              <div className="space-y-0.5">
                {group.items.map(({ key, label, href, Icon: ItemIcon, active, badge }) => {
                  const isActive = typeof active === 'boolean' ? active : page === key || (page === 'requirement-detail' && key === 'dashboard');
                  return (
                    <a
                      key={key}
                      href={href}
                      title={collapsed ? label : undefined}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => setMobileOpen(false)}
                      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-medium no-underline transition-colors ${
                        collapsed ? 'lg:justify-center lg:px-2' : ''
                      } ${
                        isActive
                          ? 'bg-accent-tint text-accent font-semibold'
                          : 'text-muted hover:bg-surface-alt hover:text-ink'
                      }`}
                    >
                      {ItemIcon && <ItemIcon className="size-4 shrink-0" aria-hidden="true" />}
                      <span className={`truncate ${collapsed ? 'lg:hidden' : ''}`}>{label}</span>
                      {badge > 0 && (
                        <span
                          className={`ml-auto rounded-md bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-accent border border-line tabular-nums ${
                            collapsed ? 'lg:hidden' : ''
                          }`}
                        >
                          {badge}
                        </span>
                      )}
                    </a>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-line p-2.5">
          <div className={`flex items-center gap-2.5 rounded-lg p-1.5 ${collapsed ? 'lg:flex-col' : ''}`}>
            <div className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-tint text-xs font-semibold text-accent">
              {user?.name?.slice(0, 2).toUpperCase() || 'RQ'}
            </div>
            <div className={`min-w-0 flex-1 ${collapsed ? 'lg:hidden' : ''}`}>
              <strong className="block truncate text-xs font-semibold text-ink">{user?.name}</strong>
              <span className="block truncate text-[11px] text-muted">{userRole}</span>
            </div>
            <button
              type="button"
              onClick={onLogout}
              aria-label="Log out"
              title="Log out"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-surface-alt hover:text-danger"
            >
              <LogOut className="size-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      <div className={`flex min-w-0 flex-1 flex-col transition-all duration-150 ${collapsed ? 'lg:pl-[68px]' : 'lg:pl-64'}`}>
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur-xs sm:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen((open) => !open)}
              aria-label="Toggle navigation"
              aria-expanded={mobileOpen}
              className="inline-flex size-9 items-center justify-center rounded-lg border border-line bg-surface text-ink hover:bg-surface-alt lg:hidden"
            >
              <Menu className="size-4" aria-hidden="true" />
            </button>
            <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-muted min-w-0">
              <span className="hidden sm:inline truncate">ReqQuality AI</span>
              <span className="hidden sm:inline text-line" aria-hidden="true">/</span>
              <strong className="truncate font-semibold text-ink">{activeCrumb}</strong>
            </nav>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {searchSlot}
            {actionsSlot}
            {user?.role && (
              <div className="hidden md:flex items-center">
                <StatusBadge value={userRole} />
              </div>
            )}
            <ThemeSelector />
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>

        <footer className="border-t border-line bg-surface px-4 py-3.5 text-xs text-muted sm:px-6">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2">
            <span>ReqQuality AI · Enterprise Requirements &amp; SQA Workspace</span>
            <span className="hidden sm:inline">Human-reviewed AI quality analysis</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
