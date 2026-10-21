import QualityMetrics from '../components/QualityMetrics';
import { apiFetch as fetch } from '../api.js';
import React, { useEffect, useRef, useState } from 'react';
import PdfExportButton from '../components/PdfExportButton';
import LoadingSkeleton from '../components/LoadingSkeleton';

function RequirementRow({ requirement, attention = false }) {
  return (
    <article className={`dashboard-requirement-row${attention ? ' attention-row' : ''}`}>
      <div className="dashboard-requirement-copy">
        <h3>{requirement.title}</h3>
        <span>{requirement.requirement_type}</span>
      </div>
      <div className="dashboard-requirement-state">
        <span className={`risk-level risk-${(requirement.risk_level || 'unscored').toLowerCase()}`}>
          Risk: {requirement.risk_level || 'Not analyzed'}
        </span>
        <span className={`review-status review-${requirement.review_status.toLowerCase().replaceAll(' ', '-')}`}>
          {requirement.sqa_review_status || requirement.review_status}
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
  const dashboardSnapshot = useRef(null);
  const [dashboard, setDashboard] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [queueFilters, setQueueFilters] = useState({status:'',risk:'',priority:'',type:''});
  const [error, setError] = useState('');
  const [retry,setRetry]=useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);setError('');
    async function loadRequirements() {
      try {
        const [dashboardResponse, requirementsResponse] = await Promise.all([
          dashboardSnapshot.current?.userId === user?.id ? Promise.resolve(null) : fetch('/api/dashboard?view=workflow', { signal: controller.signal }),
          fetch(`/api/requirements?view=summary&page=${page}&${new URLSearchParams(queueFilters)}`, { signal: controller.signal }),
        ]);
        const [dashboardData, requirementsData] = await Promise.all([
          dashboardResponse ? dashboardResponse.json() : Promise.resolve(dashboardSnapshot.current.data),
          requirementsResponse.json(),
        ]);
        if (dashboardResponse && !dashboardResponse.ok) throw new Error(dashboardData.error || 'Unable to load dashboard statistics.');
        if (!requirementsResponse.ok) throw new Error(requirementsData.error || 'Unable to load requirements.');
        const dashboardNumbers = [
          'requirements_with_linked_cases', 'requirements_without_linked_cases', 'items_needing_review_count',
        ];
        if (
          !dashboardData
          || dashboardNumbers.some((field) => !Number.isFinite(dashboardData[field]))
          || !dashboardData.review_status_counts || !dashboardData.latest_execution_counts
          || !dashboardData.open_bugs_by_severity || !dashboardData.metric_definitions
          || !Array.isArray(dashboardData.items_needing_review)
          || !Array.isArray(requirementsData.requirements)
        ) {
          throw new Error('The dashboard response was incomplete. Refresh the page and try again.');
        }
        if (controller.signal.aborted) return;
        dashboardSnapshot.current = { userId:user?.id, data:dashboardData };
        setDashboard(dashboardData);
        setRequirements(requirementsData.requirements);
        setTotal(requirementsData.total);
      } catch (loadError) {
        if (controller.signal.aborted) return;
        const message = loadError instanceof SyntaxError
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
  }, [page, queueFilters, user?.id,retry]);

  const [search, setSearch] = useState('');
  const visibleRequirements = requirements.filter(requirement =>
    requirement.title.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <section className={`requirements-dashboard${isEngineer ? ' engineer-dashboard' : ''}`} aria-labelledby="dashboard-title">
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">QUALITY OVERVIEW</p>
          <h1 id="dashboard-title">{isEngineer ? 'SQE dashboard' : 'Analyst dashboard'}</h1>
          <p className="dashboard-intro">{isEngineer ? 'Open a requirement to review its criteria, test cases, executions and defects.' : 'Add a requirement or open a draft to refine it and submit it for review.'}</p>
        </div>
        <div className="dashboard-actions">
          {user?.permissions?.includes('create_requirements') && <a className="button" href="#requirements">Add requirement</a>}
          <PdfExportButton url="/api/reports/project.pdf" filename="project-quality-report.pdf">Export Project PDF</PdfExportButton>
          <PdfExportButton url="/api/exports/requirements.csv" filename="requirements.csv" format="CSV">Export CSV</PdfExportButton>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}<button disabled={isLoading} onClick={()=>{dashboardSnapshot.current=null;setRetry(v=>v+1);}}>Refresh dashboard / Retry</button>
      {isLoading ? (
        <LoadingSkeleton />
      ) : !dashboard ? (
        <p className="requirements-empty">Dashboard statistics are unavailable.</p>
      ) : (
        <>
          <QualityMetrics data={dashboard} />
          <section className="dashboard-section" aria-labelledby="all-requirements-title">
            <div className="dashboard-section-heading">
              <div><p className="eyebrow">REGISTER</p><h2 id="all-requirements-title">All Requirements</h2></div>
              <span>{total} items ? page {page}</span>
            </div>
            <div className="dashboard-filters">
              {Object.entries({status:['Pending','In Review','Approved','Needs Revision'],risk:['Low','Medium','High','Critical'],priority:['Low','Medium','High'],type:['Functional','Non-Functional','Business']}).map(([key,choices]) => <label key={key}>Filter {key}<select value={queueFilters[key]} onChange={e => {setQueueFilters({...queueFilters,[key]:e.target.value});setPage(1);}}><option value="">All</option>{choices.map(v => <option key={v}>{v}</option>)}</select></label>)}
              <button disabled={page===1 || isLoading} onClick={() => setPage(page-1)}>Previous page</button>
              <button disabled={page*50>=total || isLoading} onClick={() => setPage(page+1)}>Next page</button>
              <label>Search this page<input type="search" placeholder="Search by title" value={search} onChange={event => setSearch(event.target.value)} /></label>

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
