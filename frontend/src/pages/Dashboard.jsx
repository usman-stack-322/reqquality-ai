import React, { useEffect, useState } from 'react';
import PdfExportButton from '../components/PdfExportButton';

const REVIEW_DISTRIBUTION = [
  ['Pending', 'pending_count', 'pending'],
  ['In Review', 'in_review_count', 'in-review'],
  ['Approved', 'approved_count', 'approved'],
  ['Needs Revision', 'needs_revision_count', 'needs-revision'],
];
const RISK_DISTRIBUTION = [
  ['Low', 'low_risk_count', 'low'],
  ['Medium', 'medium_risk_count', 'medium'],
  ['High', 'high_risk_count', 'high'],
  ['Critical', 'critical_risk_count', 'critical'],
];
const TYPE_DISTRIBUTION = [
  ['Functional', 'functional_count', 'functional'],
  ['Non-Functional', 'non_functional_count', 'non-functional'],
  ['Business', 'business_count', 'business'],
];

function MetricCard({ label, value, detail, tone = '', helpText = '' }) {
  return (
    <article className={`metric-card ${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      {detail && <span>{detail}</span>}
      {helpText && <span className="metric-help" title={helpText}>{helpText}</span>}
    </article>
  );
}

function Distribution({ title, items, data, total }) {
  return (
    <section className="distribution-panel" aria-label={title}>
      <h3>{title}</h3>
      <div className="distribution-list">
        {items.map(([label, key, tone]) => {
          const count = data[key] || 0;
          const percentage = total ? count * 100 / total : 0;
          return (
            <div className="distribution-item" key={key}>
              <div className="distribution-label-row">
                <span>{label}</span><strong>{count}</strong>
              </div>
              <div className="distribution-track" role="progressbar" aria-label={`${label} ${title.toLowerCase()}`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(percentage)}>
                <span className={`distribution-fill fill-${tone}`} style={{ width: `${percentage}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function RequirementRow({ requirement, attention = false }) {
  return (
    <article className={`dashboard-requirement-row${attention ? ' attention-row' : ''}`}>
      <div className="dashboard-requirement-copy">
        <h3>{requirement.title}</h3>
        <span>{requirement.requirement_type}</span>
      </div>
      <div className="dashboard-requirement-state">
        <span className={`risk-level risk-${(requirement.risk_level || 'unscored').toLowerCase()}`}>
          {requirement.risk_score === null ? 'Not scored' : `${requirement.risk_score}/100`} · {requirement.risk_level || 'No risk data'}
        </span>
        <span className={`review-status review-${requirement.review_status.toLowerCase().replaceAll(' ', '-')}`}>
          {requirement.review_status}
        </span>
        <span className={`priority-label priority-${(requirement.suggested_priority || requirement.user_priority || requirement.priority).toLowerCase()}`}>
          {requirement.suggested_priority || 'No suggestion'}
        </span>
      </div>
      <a className="button details-button" href={`#requirement/${requirement.id}`}>View Details</a>
    </article>
  );
}

export default function Dashboard({ user }) {
  const isEngineer = user?.role === 'SQA Engineer';
  const [dashboard, setDashboard] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadRequirements() {
      try {
        const [dashboardResponse, requirementsResponse] = await Promise.all([
          fetch('/api/dashboard', { credentials: 'include' }),
          fetch('/api/requirements', { credentials: 'include' }),
        ]);
        const [dashboardData, requirementsData] = await Promise.all([
          dashboardResponse.json(),
          requirementsResponse.json(),
        ]);
        if (!dashboardResponse.ok) throw new Error(dashboardData.error || 'Unable to load dashboard statistics.');
        if (!requirementsResponse.ok) throw new Error(requirementsData.error || 'Unable to load requirements.');
        const dashboardNumbers = [
          'total_requirements', 'pending_count', 'in_review_count', 'approved_count',
          'needs_revision_count', 'average_risk_score', 'total_test_scenarios',
          'traceability_coverage_percent',
        ];
        if (
          !dashboardData
          || dashboardNumbers.some((field) => !Number.isFinite(dashboardData[field]))
          || !Array.isArray(dashboardData.high_attention_requirements)
          || !Array.isArray(dashboardData.recent_requirements)
          || !Array.isArray(requirementsData.requirements)
        ) {
          throw new Error('The dashboard response was incomplete. Refresh the page and try again.');
        }
        setDashboard(dashboardData);
        setRequirements(requirementsData.requirements);
      } catch (loadError) {
        const message = loadError instanceof SyntaxError
          ? 'The dashboard API returned an invalid response. Refresh the page or contact support.'
          : loadError instanceof TypeError
            ? 'Unable to reach the dashboard API. Check that the backend is running.'
            : loadError.message || 'Unable to load dashboard data.';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }
    loadRequirements();
  }, []);

  const [search, setSearch] = useState('');
  const [reviewFilter, setReviewFilter] = useState('');
  const visibleRequirements = requirements.filter(requirement =>
    (!reviewFilter || requirement.review_status === reviewFilter)
    && requirement.title.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <section className={`requirements-dashboard${isEngineer ? ' engineer-dashboard' : ''}`} aria-labelledby="dashboard-title">
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">QUALITY OVERVIEW</p>
          <h1 id="dashboard-title">{isEngineer ? 'SQA Engineer Dashboard' : 'SQA Dashboard'}</h1>
          {isEngineer && <p className="dashboard-intro">Review requirement quality, prioritize risks, and track test coverage.</p>}
        </div>
        <div className="dashboard-actions">
          {user?.permissions?.includes('create_requirements') && <a className="button" href="#requirements">Add requirement</a>}
          <PdfExportButton url="/api/reports/project.pdf" filename="project-quality-report.pdf">Export Project PDF</PdfExportButton>
          <a className="button export-button" href="/api/exports/requirements.csv" download>Export CSV</a>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {isLoading ? (
        <p className="requirements-empty" role="status">Loading dashboard...</p>
      ) : !dashboard ? (
        <p className="requirements-empty">Dashboard statistics are unavailable.</p>
      ) : (
        <>
          <section className="metric-grid" aria-label="Key quality metrics">
            <MetricCard label="Total Requirements" value={dashboard.total_requirements} />
            <MetricCard label="Approved Requirements" value={dashboard.approved_count} tone="metric-approved" />
            <MetricCard label="Pending Requirements" value={dashboard.pending_count} tone="metric-review" />
            <MetricCard label="In Review Requirements" value={dashboard.in_review_count} tone="metric-review" />
            <MetricCard label="Needs Revision Requirements" value={dashboard.needs_revision_count} tone="metric-revision" />
            <MetricCard
              label="Average Quality Risk Score"
              value={`${dashboard.average_risk_score}/100`}
              detail="0–29 Low · 30–59 Medium · 60–79 High · 80–100 Critical"
              helpText="Quality Risk Score indicates how much refinement and QA attention a requirement may need before implementation."
              tone="metric-risk"
            />
            <MetricCard label="Total Generated Test Scenarios" value={dashboard.total_test_scenarios} tone="metric-scenarios" />
            <MetricCard label="Traceability Coverage" value={`${dashboard.traceability_coverage_percent}%`} detail={`${dashboard.traceable_requirement_count} of ${dashboard.total_requirements} requirements`} tone="metric-coverage" />
          </section>

          {!isEngineer && <section className="analytics-section" aria-labelledby="distribution-title">
            <div className="dashboard-section-heading">
              <div><p className="eyebrow">DISTRIBUTION</p><h2 id="distribution-title">Portfolio composition</h2></div>
              <span>{dashboard.total_requirements} requirements</span>
            </div>
            <div className="distribution-grid">
              <Distribution title="Review Status" items={REVIEW_DISTRIBUTION} data={dashboard} total={dashboard.total_requirements} />
              <Distribution title="Risk Level" items={RISK_DISTRIBUTION} data={dashboard} total={dashboard.total_requirements} />
              <Distribution title="Requirement Type" items={TYPE_DISTRIBUTION} data={dashboard} total={dashboard.total_requirements} />
            </div>
          </section>}

          <section className="coverage-section" aria-labelledby="coverage-title">
            <div className="coverage-heading">
              <div><p className="eyebrow">TRACEABILITY</p><h2 id="coverage-title">Traceability Coverage</h2></div>
              <strong>{dashboard.traceability_coverage_percent}%</strong>
            </div>
            <p>{dashboard.traceable_requirement_count} of {dashboard.total_requirements} requirements have at least one acceptance criterion and one linked test scenario.</p>
            <div className="coverage-track" role="progressbar" aria-label="Traceability coverage" aria-valuemin="0" aria-valuemax="100" aria-valuenow={dashboard.traceability_coverage_percent}>
              <span style={{ width: `${dashboard.traceability_coverage_percent}%` }} />
            </div>
          </section>

          <section className="dashboard-section" aria-labelledby="attention-title">
            <div className="dashboard-section-heading">
              <div><p className="eyebrow">PRIORITY QUEUE</p><h2 id="attention-title">{isEngineer ? 'Review priorities' : 'High Attention Requirements'}</h2></div>
              <span>{dashboard.high_attention_requirements.length} items</span>
            </div>
            {dashboard.high_attention_requirements.length ? (
              <div className="dashboard-requirement-list">
                {dashboard.high_attention_requirements.map((requirement) => (
                  <RequirementRow requirement={requirement} attention key={requirement.id} />
                ))}
              </div>
            ) : <p className="dashboard-empty">No high-risk or revision-required items.</p>}
          </section>

          <section className="dashboard-section" aria-labelledby="recent-title">
            <div className="dashboard-section-heading">
              <div><p className="eyebrow">LATEST ACTIVITY</p><h2 id="recent-title">Recent Requirements</h2></div>
              <span>Latest 5</span>
            </div>
            {dashboard.recent_requirements.length ? (
              <div className="dashboard-requirement-list">
                {dashboard.recent_requirements.map((requirement) => (
                  <RequirementRow requirement={requirement} key={requirement.id} />
                ))}
              </div>
            ) : <p className="dashboard-empty">No saved requirements yet.{user?.permissions?.includes('create_requirements') && <> <a href="#requirements">Add a requirement</a> to begin.</>}</p>}
          </section>

          <section className="dashboard-section" aria-labelledby="all-requirements-title">
            <div className="dashboard-section-heading">
              <div><p className="eyebrow">REGISTER</p><h2 id="all-requirements-title">All Requirements</h2></div>
              <span>{visibleRequirements.length} of {requirements.length} items</span>
            </div>
            <div className="dashboard-filters">
              <label>Search requirements<input type="search" placeholder="Search by title" value={search} onChange={event => setSearch(event.target.value)} /></label>
              <label>Review status<select value={reviewFilter} onChange={event => setReviewFilter(event.target.value)}><option value="">All statuses</option>{REVIEW_DISTRIBUTION.map(([label]) => <option key={label}>{label}</option>)}</select></label>
            </div>
            {visibleRequirements.length ? (
              <div className="dashboard-requirement-list">
                {visibleRequirements.map((requirement) => (
                  <RequirementRow requirement={requirement} key={requirement.id} />
                ))}
              </div>
            ) : <p className="dashboard-empty">{requirements.length ? 'No requirements match these filters.' : 'No saved requirements yet.'}</p>}
          </section>
        </>
      )}
    </section>
  );
}
