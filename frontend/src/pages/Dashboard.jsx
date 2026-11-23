import React, { useEffect, useRef, useState } from 'react';
import { RefreshCw, FileText, FolderKanban, ClipboardCheck, FlaskConical, Bug, FileBarChart2, Plus } from 'lucide-react';
import { apiFetch as fetch } from '../api.js';
import QualityMetrics from '../components/QualityMetrics';
import DashboardCharts from '../components/DashboardCharts';
import PdfExportButton from '../components/PdfExportButton';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ProjectContext from '../components/ProjectContext';
import { EmptyState, PageHeader, StatusBadge, buttonPrimaryClass, buttonSecondaryClass, inputClass } from '../components/ui';
import { nextStep } from '../workflow-guidance.js';

const SECTION_META = {
  dashboard: {
    eyebrow: 'Workspace · Requirements',
    title: (isEngineer) => (isEngineer ? 'SQA Reviewer Dashboard' : 'Analyst Requirements Dashboard'),
    description: (isEngineer) =>
      isEngineer
        ? 'Review submitted requirements, acceptance criteria, test cases, executions, and failure-linked defects.'
        : 'Create requirements, analyze quality with Gemini, refine proposals, and submit drafts for SQA review.',
  },
  projects: {
    eyebrow: 'Workspace · Projects',
    title: () => 'Projects',
    description: () => 'Active project scope, supplied context, and requirement traceability progress.',
  },
  'review-queue': {
    eyebrow: 'Workspace · Review Queue',
    title: () => 'SQA Review Queue',
    description: () => 'Requirements awaiting SQA review, revision, or confirmation.',
  },
  'test-cases': {
    eyebrow: 'Workspace · Test Cases',
    title: () => 'Test Cases & Execution Overview',
    description: () => 'Current-version test case linkage and latest manual execution results across requirements.',
  },
  bugs: {
    eyebrow: 'Workspace · Bugs',
    title: () => 'Open Defects & Quality Attention',
    description: () => 'Non-closed bugs linked to failed executions and requirements needing review attention.',
  },
  reports: {
    eyebrow: 'Workspace · Reports',
    title: () => 'Quality Reports & Exports',
    description: () => 'Generate project-wide PDF summaries and full requirement CSV registers.',
  },
};

export default function Dashboard({ user, section = 'dashboard' }) {
  const isEngineer = user?.role === 'SQA Engineer';
  const dashboardSnapshot = useRef(null);
  const [dashboard, setDashboard] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [queueFilters, setQueueFilters] = useState({
    status: section === 'review-queue' ? 'Pending' : '',
    risk: '',
    priority: '',
    type: '',
  });
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    setQueueFilters((prev) => ({
      ...prev,
      status: section === 'review-queue' ? 'Pending' : section === 'dashboard' ? '' : prev.status,
    }));
    setPage(1);
  }, [section]);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError('');
    async function loadRequirements() {
      try {
        const [dashboardResponse, requirementsResponse] = await Promise.all([
          dashboardSnapshot.current?.userId === user?.id
            ? Promise.resolve(null)
            : fetch('/api/dashboard', { signal: controller.signal }),
          fetch(`/api/requirements?view=summary&page=${page}&${new URLSearchParams(queueFilters)}`, { signal: controller.signal }),
        ]);
        const [dashboardData, requirementsData] = await Promise.all([
          dashboardResponse ? dashboardResponse.json() : Promise.resolve(dashboardSnapshot.current.data),
          requirementsResponse.json(),
        ]);
        if (dashboardResponse && !dashboardResponse.ok) throw new Error(dashboardData.error || 'Unable to load dashboard statistics.');
        if (!requirementsResponse.ok) throw new Error(requirementsData.error || 'Unable to load requirements.');
        const dashboardNumbers = [
          'requirements_with_linked_cases',
          'requirements_without_linked_cases',
          'items_needing_review_count',
        ];
        if (
          !dashboardData ||
          dashboardNumbers.some((field) => !Number.isFinite(dashboardData[field])) ||
          !dashboardData.review_status_counts ||
          !dashboardData.latest_execution_counts ||
          !dashboardData.open_bugs_by_severity ||
          !dashboardData.metric_definitions ||
          !Array.isArray(dashboardData.items_needing_review) ||
          !Array.isArray(requirementsData.requirements)
        ) {
          throw new Error('The dashboard response was incomplete. Refresh the page and try again.');
        }
        if (controller.signal.aborted) return;
        dashboardSnapshot.current = { userId: user?.id, data: dashboardData };
        setDashboard(dashboardData);
        setRequirements(requirementsData.requirements);
        setTotal(requirementsData.total);
      } catch (loadError) {
        if (controller.signal.aborted) return;
        const message =
          loadError instanceof SyntaxError
            ? 'The dashboard API returned an invalid response. Refresh the page or contact support.'
            : loadError instanceof TypeError
              ? 'Unable to reach the dashboard API. Check that the backend is running.'
              : loadError.message || 'Unable to load dashboard data.';
        setError(message);
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }
    loadRequirements();
    return () => controller.abort();
  }, [page, queueFilters, user?.id, retry]);

  const visibleRequirements = requirements.filter((requirement) =>
    requirement.title.toLowerCase().includes(search.trim().toLowerCase()),
  );

  const meta = SECTION_META[section] || SECTION_META.dashboard;
  const totalRequirements =
    dashboard?.total_requirements ??
    ((dashboard?.requirements_with_linked_cases || 0) + (dashboard?.requirements_without_linked_cases || 0));
  const scoredRisk =
    (dashboard?.low_risk_count || 0) +
    (dashboard?.medium_risk_count || 0) +
    (dashboard?.high_risk_count || 0) +
    (dashboard?.critical_risk_count || 0);
  const riskData = dashboard
    ? [
        { name: 'Low', count: dashboard.low_risk_count || 0 },
        { name: 'Medium', count: dashboard.medium_risk_count || 0 },
        { name: 'High', count: dashboard.high_risk_count || 0 },
        { name: 'Critical', count: dashboard.critical_risk_count || 0 },
        { name: 'Unscored', count: Math.max(0, totalRequirements - scoredRisk) },
      ]
    : [];

  return (
    <section className={`requirements-dashboard space-y-6${isEngineer ? ' engineer-dashboard' : ''}`} aria-labelledby="dashboard-title">
      <PageHeader
        eyebrow={meta.eyebrow}
        title={<span id="dashboard-title">{meta.title(isEngineer)}</span>}
        description={meta.description(isEngineer)}
        actions={
          <>
            <button
              type="button"
              className={`${buttonSecondaryClass} dashboard-refresh`}
              disabled={isLoading}
              onClick={() => {
                dashboardSnapshot.current = null;
                setRetry((v) => v + 1);
              }}
            >
              <RefreshCw className={`size-3.5 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
              Refresh dashboard / Retry
            </button>
            {user?.permissions?.includes('create_requirements') && (
              <a className={`${buttonPrimaryClass} no-underline`} href="#requirements">
                <Plus className="size-3.5" aria-hidden="true" />
                Add requirement
              </a>
            )}
            <PdfExportButton url="/api/reports/project.pdf" filename="project-quality-report.pdf">
              Export Project PDF
            </PdfExportButton>
            <PdfExportButton url="/api/exports/requirements.csv" filename="requirements.csv" format="CSV">
              Export CSV
            </PdfExportButton>
          </>
        }
      />

      {error && (
        <p className="error rounded-xl border border-danger/35 bg-danger-tint px-4 py-3 text-xs font-medium text-danger" role="alert">
          {error}
        </p>
      )}

      {isLoading ? (
        <LoadingSkeleton />
      ) : !dashboard ? (
        <EmptyState
          icon={FileText}
          title="Dashboard statistics are unavailable"
          description="Use Refresh dashboard / Retry above to reconnect to the API."
        />
      ) : (
        <>
          {section === 'projects' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              <div className="lg:col-span-7">
                <ProjectContext />
              </div>
              <section className="lg:col-span-5 rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex size-8 items-center justify-center rounded-lg bg-accent-tint text-accent">
                    <FolderKanban className="size-4" aria-hidden="true" />
                  </span>
                  <div>
                    <h2 className="text-sm font-semibold text-ink">Project summary</h2>
                    <p className="text-xs text-muted">Single shared workspace (`current`)</p>
                  </div>
                </div>
                <dl className="grid grid-cols-2 gap-3 pt-1 text-xs">
                  <div className="rounded-lg border border-line bg-surface-alt/50 p-3">
                    <dt className="text-muted">Total requirements</dt>
                    <dd className="mt-1 text-xl font-semibold text-ink tabular-nums">{totalRequirements}</dd>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-alt/50 p-3">
                    <dt className="text-muted">Traceability coverage</dt>
                    <dd className="mt-1 text-xl font-semibold text-ink tabular-nums">{dashboard.traceability_coverage_percent ?? 0}%</dd>
                  </div>
                </dl>
              </section>
            </div>
          )}

          {section === 'reports' && (
            <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <article className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
                <div className="inline-flex size-9 items-center justify-center rounded-lg bg-accent-tint text-accent">
                  <FileBarChart2 className="size-4" aria-hidden="true" />
                </div>
                <h2 className="text-base font-semibold text-ink">Project Quality Summary (PDF)</h2>
                <p className="text-xs text-muted">
                  Includes review counts, risk breakdown, test case versions, manual executions, bugs, and traceability evidence.
                </p>
                <PdfExportButton url="/api/reports/project.pdf" filename="project-quality-report.pdf">
                  Download Project PDF
                </PdfExportButton>
              </article>
              <article className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
                <div className="inline-flex size-9 items-center justify-center rounded-lg bg-success-tint text-success">
                  <FileText className="size-4" aria-hidden="true" />
                </div>
                <h2 className="text-base font-semibold text-ink">Requirements Register (CSV)</h2>
                <p className="text-xs text-muted">
                  Formula-safe CSV export containing saved requirement records, versions, acceptance criteria, and execution histories.
                </p>
                <PdfExportButton url="/api/exports/requirements.csv" filename="requirements.csv" format="CSV">
                  Download Requirements CSV
                </PdfExportButton>
              </article>
            </section>
          )}

          {['dashboard', 'review-queue', 'test-cases', 'bugs'].includes(section) && (
            <>
              <QualityMetrics data={dashboard} />
              <DashboardCharts
                riskData={riskData}
                executionCounts={dashboard.latest_execution_counts}
                bugSeverityCounts={dashboard.open_bugs_by_severity}
              />
            </>
          )}

          {section === 'dashboard' && (
            <section className="dashboard-workflow rounded-xl border border-line bg-surface p-5 shadow-xs space-y-2" aria-label="Your workflow">
              <div className="flex items-center gap-2">
                {isEngineer ? (
                  <ClipboardCheck className="size-4 text-accent" aria-hidden="true" />
                ) : (
                  <FlaskConical className="size-4 text-accent" aria-hidden="true" />
                )}
                <h2 className="text-sm font-semibold text-ink">{isEngineer ? 'Review workflow' : 'Authoring workflow'}</h2>
              </div>
              <p className="text-xs text-muted leading-relaxed">
                {isEngineer
                  ? '1. Open a submitted requirement → 2. Review criteria and scenarios → 3. Use AI Review Assistant if changes are needed → 4. Accept proposals as Pending Review → 5. Review cases and approve separately → 6. Export saved evidence.'
                  : '1. Add a requirement → 2. Analyze with AI → 3. Review and save the suggestions → 4. Submit for SQA review → 5. Address feedback → 6. Export the saved report.'}
              </p>
              <p className="text-[11px] text-muted">
                Requirement approval, test case approval, and manual execution results are separate. Linked cases show traceability, not proof of complete behavioral coverage or a passing test.
              </p>
            </section>
          )}

          <section className="dashboard-section rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4" aria-labelledby="all-requirements-title">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">Register</p>
                <h2 id="all-requirements-title" className="text-base font-semibold text-ink">
                  {section === 'review-queue'
                    ? 'Requirements in Review Queue'
                    : section === 'bugs'
                      ? 'Requirements & Linked Defect Context'
                      : section === 'test-cases'
                        ? 'Requirements & Test Case Links'
                        : 'All Requirements'}
                </h2>
              </div>
              <span className="rounded-md border border-line bg-surface-alt px-2.5 py-1 text-xs font-medium text-muted tabular-nums">
                {total} items · page {page}
              </span>
            </div>

            <div className="dashboard-filters grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {Object.entries({
                status: ['Draft', 'Ready for Review', 'Pending', 'In Review', 'Approved', 'Needs Revision'],
                risk: ['Low', 'Medium', 'High', 'Critical'],
                priority: ['Low', 'Medium', 'High'],
                type: ['Functional', 'Non-Functional', 'Business'],
              }).map(([key, choices]) => (
                <label key={key} className="block space-y-1 text-xs font-medium text-muted">
                  <span>
                    {{
                      status: 'Requirement status',
                      risk: 'AI risk level',
                      priority: 'User priority',
                      type: 'Requirement type',
                    }[key]}
                  </span>
                  <select
                    className={inputClass}
                    value={queueFilters[key]}
                    onChange={(e) => {
                      setQueueFilters({ ...queueFilters, [key]: e.target.value });
                      setPage(1);
                    }}
                  >
                    <option value="">All</option>
                    {choices.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
              ))}
              <label className="block space-y-1 text-xs font-medium text-muted">
                <span>Search this page</span>
                <input
                  className={inputClass}
                  type="search"
                  placeholder="Search by title…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>
            </div>

            {visibleRequirements.length ? (
              <div className="table-wrapper" tabIndex={0} role="region" aria-labelledby="all-requirements-title">
                <table className="min-w-[780px] text-left text-xs">
                  <caption className="visually-hidden">Saved requirements list</caption>
                  <thead>
                    <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wider text-muted">
                      <th scope="col" className="px-4 py-3">Requirement</th>
                      <th scope="col" className="px-4 py-3">Type</th>
                      <th scope="col" className="px-4 py-3">AI Risk</th>
                      <th scope="col" className="px-4 py-3">Authoring / SQA</th>
                      <th scope="col" className="px-4 py-3">Priority</th>
                      <th scope="col" className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {visibleRequirements.map((requirement) => {
                      const effectivePriority = requirement.suggested_priority || requirement.user_priority || requirement.priority;
                      return (
                        <tr key={requirement.id} className="hover:bg-surface-alt/50 transition-colors">
                          <td className="px-4 py-3.5 max-w-md">
                            <a className="block font-semibold text-ink hover:text-accent hover:underline" href={`#requirement/${requirement.id}`}>
                              <span className="mr-1.5 font-mono text-[11px] text-muted">REQ-{requirement.id}</span>
                              {requirement.title}
                            </a>
                            <p className="mt-1 text-[11px] text-muted">Next: {nextStep(requirement, isEngineer)}</p>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap text-muted">{requirement.requirement_type}</td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <StatusBadge value={requirement.risk_level || 'Not analyzed'} />
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <div className="flex flex-col gap-1 items-start">
                              <StatusBadge value={requirement.review_status} />
                              <span className="text-[11px] text-muted">
                                SQA: {requirement.sqa_review_status || 'Pending'}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <div className="flex flex-col gap-1 items-start">
                              <StatusBadge value={effectivePriority} />
                              <span className="text-[11px] text-muted">
                                User: {requirement.user_priority || requirement.priority}
                                {requirement.suggested_priority ? ` · AI: ${requirement.suggested_priority}` : ''}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap text-right">
                            <a
                              className="inline-flex items-center rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-ink hover:border-accent/50 hover:text-accent no-underline"
                              href={`#requirement/${requirement.id}`}
                            >
                              View Details
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={section === 'bugs' ? Bug : FileText}
                title={requirements.length ? 'No requirements match these filters' : 'No saved requirements yet'}
                description={requirements.length ? 'Try adjusting the filters or clearing your search query.' : 'Create a requirement draft to begin AI quality analysis and SQA traceability.'}
              />
            )}

            <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
              <button
                type="button"
                className={buttonSecondaryClass}
                disabled={page === 1 || isLoading}
                onClick={() => setPage(page - 1)}
              >
                Previous page
              </button>
              <span className="text-xs text-muted tabular-nums">
                Page {page} of {Math.max(1, Math.ceil(total / 50))}
              </span>
              <button
                type="button"
                className={buttonSecondaryClass}
                disabled={page * 50 >= total || isLoading}
                onClick={() => setPage(page + 1)}
              >
                Next page
              </button>
            </div>
          </section>
        </>
      )}
    </section>
  );
}
