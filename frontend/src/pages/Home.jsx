import React from 'react';

const WORKFLOW = [
  ['Requirement Input', 'Capture the stakeholder need, type and user priority.'],
  ['AI Analysis', 'Gemini analyzes meaning, uncertainty and testability in one structured review.'],
  ['Refinement', 'Review a suggested improved requirement and any introduced assumptions.'],
  ['Acceptance Criteria', 'Review proposed criteria for observable outcomes.'],
  ['Risk / Priority', 'Use requirement-quality risk and suggested priority to guide attention.'],
  ['Test Scenarios', 'Generate positive, negative, boundary and edge-case scenarios.'],
  ['Traceability', 'Save criteria and scenarios linked to their requirement record.'],
  ['SQA Review', 'Record reviewer notes and approve or request revision.'],
  ['Dashboard / Reports', 'Track review status, quality risk and artifact links; export PDF or CSV.'],
];
const FEATURES = [
  ['01', 'Find the unclear parts', 'Gemini identifies ambiguity, missing information and testability concerns. If AI cannot complete, your input stays available for a safe retry.'],
  ['02', 'Review suggestions in context', 'Compare the original requirement with proposed refinement, acceptance criteria and labeled assumptions. Keep human judgment at the center of each decision.'],
  ['03', 'Connect review artifacts', 'Keep generated scenarios and acceptance criteria linked to their requirement. Traceability coverage measures these links, not executed-test coverage.'],
  ['04', 'Make review progress visible', 'Use dashboards, reviewer notes, review status, requirement PDF reports, project summary PDFs and requirement CSV exports.'],
];

export default function Home({ user }) {
  return <div className="landing-page">
    <section className="landing-hero" aria-labelledby="landing-title">
      <div className="hero-copy">
        <p className="hero-kicker">REQUIREMENTS, WITH A CLEAR REVIEW PATH</p>
        <h1 id="landing-title">Bring clarity to requirements. Keep review connected.</h1>
        <p className="hero-description">Unclear requirements leave teams guessing. Disconnected review notes, acceptance criteria and testing artifacts make decisions hard to follow. ReqQuality AI brings requirement analysis, generated scenarios and SQA review into one shared project workspace.</p>
        <div className="hero-actions">
          <a className="button hero-primary" href={user ? '#dashboard' : '#login'}>{user ? 'Open dashboard' : 'Sign in to get started'}<span aria-hidden="true">→</span></a>
          <a className="button hero-secondary" href="#workflow">Explore workflow</a>
        </div>
        <p className="hero-proof">Requirement suggestions · Linked artifacts · Human review</p>
      </div>
      <div className="hero-visual">
        <div className="workflow-preview" aria-label="Illustrative requirement review">
          <div className="preview-heading"><span>REQ-001 / EXAMPLE</span><span className="preview-badge">Pending review</span></div>
          <h2>From uncertainty to a reviewable record</h2>
          <div className="preview-original"><span>Original requirement</span><p>“The system should respond quickly.”</p></div>
          <div className="preview-finding"><span>Quality finding</span><p>What response time, operation and load should the team agree on?</p></div>
          <div className="preview-artifacts"><span>Suggested refinement</span><span>Acceptance criteria</span><span>Generated scenarios</span><span>Reviewer notes</span></div>
          <p className="preview-note">Illustrative only. Stakeholders must confirm measurable limits before approval.</p>
        </div>
        <p className="visual-caption">A connected path from stakeholder need to documented SQA review</p>
      </div>
    </section>
    <section className="landing-features" aria-labelledby="features-title">
      <div className="landing-section-heading"><p className="landing-eyebrow">ONE CONNECTED WORKSPACE</p><h2 id="features-title">Better inputs for your quality decisions</h2><p>Analyze, review and trace requirement artifacts without losing the original need.</p></div>
      <div className="feature-grid">{FEATURES.map(([index, title, description]) => <article className="feature-card" key={index}><span className="feature-index">{index}</span><h3>{title}</h3><p>{description}</p></article>)}</div>
    </section>
    <section className="landing-workflow" id="workflow" aria-labelledby="workflow-title">
      <div className="landing-section-heading"><p className="landing-eyebrow">A CLEAR REVIEW PATH</p><h2 id="workflow-title">From requirement input to dashboard and reports</h2><p>Analysis returns refinement, criteria, risk and scenarios together. Review them in this order, then save their links and record the SQA decision.</p></div>
      <ol className="workflow-steps">{WORKFLOW.map(([step, detail], index) => <li key={step}><span className="workflow-number">{String(index + 1).padStart(2, '0')}</span><div><span className="workflow-step-label">{step}</span><p>{detail}</p></div></li>)}</ol>
    </section>
    <section className="landing-roles" aria-labelledby="roles-title">
      <div className="roles-intro"><p className="landing-eyebrow">CLEAR RESPONSIBILITIES</p><h2 id="roles-title">Three roles. One review record.</h2><p>Default responsibilities below. Administrators can configure role permissions. Signed-in members share the current project's requirement records.</p></div>
      <article className="role-panel"><span className="role-panel-label">01 / ADMINISTER</span><h3>SQA Admin</h3><ul><li>Manages users, invitations and role permissions</li><li>Assigns reviewers and manages organization settings</li><li>Inspects shared requirements, dashboards and reports</li></ul></article>
      <article className="role-panel"><span className="role-panel-label">02 / AUTHOR</span><h3>Analyst</h3><ul><li>Inputs, analyzes and saves requirements</li><li>Reviews suggested refinement, criteria and scenarios</li><li>Tracks shared requirements and exports reports</li></ul></article>
      <article className="role-panel"><span className="role-panel-label">03 / REVIEW</span><h3>SQA Engineer</h3><ul><li>Reviews shared requirements and generated artifacts</li><li>Adds reviewer notes and changes review status</li><li>Approves or requests revision; views dashboards and exports reports</li></ul></article>
    </section>
    <section className="card review-guidance" aria-labelledby="review-guidance-title"><h2 id="review-guidance-title">Suggestions need human review</h2><p>AI outputs are suggestions, including any proposed facts, limits and assumptions. Requirement-quality risk scores indicate where refinement or review may be needed; they do not prove software defects or guarantee correctness.</p><p>Generated test scenarios are proposed testing artifacts. This application does not execute tests or record execution results. SQA approval records a human requirement-review decision.</p><p>The implemented workflow covers one shared project. Project Context input, test execution and multi-project isolation are not currently implemented.</p></section>
  </div>;
}
