import React from 'react';
import { ArrowRight, CheckCircle2, FileSearch, GitBranch, ShieldCheck } from 'lucide-react';

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
  ['01', 'Find the unclear parts', 'Gemini identifies ambiguity, missing information and testability concerns. If AI cannot complete, your input stays available for a safe retry.', FileSearch],
  ['02', 'Review suggestions in context', 'Compare the original requirement with proposed refinement, acceptance criteria and labeled assumptions. Keep human judgment at the center of each decision.', CheckCircle2],
  ['03', 'Connect review artifacts', 'Keep generated scenarios and acceptance criteria linked to their requirement. Traceability coverage measures these links, not executed-test coverage.', GitBranch],
  ['04', 'Make review progress visible', 'Use dashboards, reviewer notes, review status, requirement PDF reports, project summary PDFs and requirement CSV exports.', ShieldCheck],
];

export default function Home({ user }) {
  return (
    <div className="landing-page space-y-14">
      <section className="landing-hero grid grid-cols-1 items-center gap-10 py-6 lg:grid-cols-12" aria-labelledby="landing-title">
        <div className="hero-copy space-y-5 lg:col-span-7">
          <p className="hero-kicker inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent-tint px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-accent">
            Requirements, with a clear review path
          </p>
          <h1 id="landing-title" className="text-3xl font-bold tracking-tight text-ink sm:text-5xl sm:leading-[1.08]">
            Bring clarity to requirements. Keep review connected.
          </h1>
          <p className="hero-description max-w-2xl text-base leading-relaxed text-muted">
            Unclear requirements leave teams guessing. Disconnected review notes, acceptance criteria and testing artifacts make decisions hard to follow. ReqQuality AI brings requirement analysis, generated scenarios and SQA review into one shared project workspace.
          </p>
          <div className="hero-actions flex flex-wrap items-center gap-3 pt-1">
            <a
              className="button hero-primary inline-flex items-center gap-2 rounded-lg bg-accent-strong px-5 py-2.5 text-sm font-semibold text-on-accent no-underline shadow-xs hover:brightness-110"
              href={user ? '#dashboard' : '#login'}
            >
              {user ? 'Open dashboard' : 'Sign in to get started'}
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
            <a
              className="button hero-secondary inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-5 py-2.5 text-sm font-semibold text-ink no-underline hover:bg-surface-alt"
              href="#workflow"
            >
              Explore workflow
            </a>
          </div>
          <p className="hero-proof text-xs font-medium text-muted">Requirement suggestions · Linked artifacts · Human review</p>
        </div>

        <div className="hero-visual lg:col-span-5">
          <div className="workflow-preview rounded-2xl border border-line bg-surface p-5 shadow-sm space-y-4" aria-label="Illustrative requirement review">
            <div className="preview-heading flex items-center justify-between text-xs">
              <span className="font-mono font-semibold text-muted">REQ-001 / EXAMPLE</span>
              <span className="preview-badge rounded-md border border-warning/30 bg-warning-tint px-2 py-0.5 text-[11px] font-medium text-warning">Pending review</span>
            </div>
            <h2 className="text-base font-semibold text-ink">From uncertainty to a reviewable record</h2>
            <div className="preview-original rounded-lg border border-line bg-surface-alt/60 p-3">
              <span className="block text-[11px] font-semibold uppercase tracking-wider text-muted">Original requirement</span>
              <p className="mt-1 text-sm text-ink">“The system should respond quickly.”</p>
            </div>
            <div className="preview-finding rounded-lg border border-accent/25 bg-accent-tint p-3">
              <span className="block text-[11px] font-semibold uppercase tracking-wider text-accent">Quality finding</span>
              <p className="mt-1 text-sm text-ink">What response time, operation and load should the team agree on?</p>
            </div>
            <div className="preview-artifacts flex flex-wrap gap-1.5 text-[11px] font-medium text-muted">
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5">Suggested refinement</span>
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5">Acceptance criteria</span>
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5">Generated scenarios</span>
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5">Reviewer notes</span>
            </div>
            <p className="preview-note text-[11px] text-muted">Illustrative only. Stakeholders must confirm measurable limits before approval.</p>
          </div>
          <p className="visual-caption mt-2.5 text-center text-xs text-muted">A connected path from stakeholder need to documented SQA review</p>
        </div>
      </section>

      <section className="landing-features space-y-6" aria-labelledby="features-title">
        <div className="landing-section-heading max-w-2xl space-y-1.5">
          <p className="landing-eyebrow text-xs font-semibold uppercase tracking-wider text-accent">One connected workspace</p>
          <h2 id="features-title" className="text-2xl font-bold text-ink">Better inputs for your quality decisions</h2>
          <p className="text-sm text-muted">Analyze, review and trace requirement artifacts without losing the original need.</p>
        </div>
        <div className="feature-grid grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(([index, title, description, FeatureIcon]) => (
            <article className="feature-card rounded-xl border border-line bg-surface p-5 shadow-xs space-y-2.5" key={index}>
              <div className="flex items-center justify-between">
                <span className="feature-index font-mono text-xs font-semibold text-accent">{index}</span>
                <FeatureIcon className="size-4 text-muted" aria-hidden="true" />
              </div>
              <h3 className="text-sm font-semibold text-ink">{title}</h3>
              <p className="text-xs leading-relaxed text-muted">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-workflow space-y-6" id="workflow" aria-labelledby="workflow-title">
        <div className="landing-section-heading max-w-2xl space-y-1.5">
          <p className="landing-eyebrow text-xs font-semibold uppercase tracking-wider text-accent">A clear review path</p>
          <h2 id="workflow-title" className="text-2xl font-bold text-ink">From requirement input to dashboard and reports</h2>
          <p className="text-sm text-muted">Analysis returns refinement, criteria, risk and scenarios together. Review them in this order, then save their links and record the SQA decision.</p>
        </div>
        <ol className="workflow-steps">
          {WORKFLOW.map(([step, detail], index) => (
            <li key={step} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-4 shadow-xs">
              <span className="workflow-number inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent-tint font-mono text-xs font-semibold text-accent">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div className="space-y-1 text-sm font-semibold text-ink">
                <span className="workflow-step-label">{step}</span>
                <p className="text-xs font-normal leading-relaxed text-muted">{detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-roles grid grid-cols-1 gap-4 lg:grid-cols-4" aria-labelledby="roles-title">
        <div className="roles-intro space-y-2 lg:pr-4">
          <p className="landing-eyebrow text-xs font-semibold uppercase tracking-wider text-accent">Clear responsibilities</p>
          <h2 id="roles-title" className="text-2xl font-bold text-ink">Three roles. One review record.</h2>
          <p className="text-xs leading-relaxed text-muted">Default responsibilities below. Administrators can configure role permissions. Signed-in members share the current project's requirement records.</p>
        </div>
        <article className="role-panel rounded-xl border border-line bg-surface p-5 shadow-xs space-y-2.5">
          <span className="role-panel-label font-mono text-[11px] font-semibold text-accent">01 / ADMINISTER</span>
          <h3 className="text-base font-semibold text-ink">SQA Admin</h3>
          <ul className="space-y-1.5 text-xs text-muted list-disc pl-4">
            <li>Manages users, invitations and role permissions</li>
            <li>Assigns reviewers and manages organization settings</li>
            <li>Inspects shared requirements, dashboards and reports</li>
          </ul>
        </article>
        <article className="role-panel rounded-xl border border-line bg-surface p-5 shadow-xs space-y-2.5">
          <span className="role-panel-label font-mono text-[11px] font-semibold text-accent">02 / AUTHOR</span>
          <h3 className="text-base font-semibold text-ink">Analyst</h3>
          <ul className="space-y-1.5 text-xs text-muted list-disc pl-4">
            <li>Inputs, analyzes and saves requirements</li>
            <li>Reviews suggested refinement, criteria and scenarios</li>
            <li>Tracks shared requirements and exports reports</li>
          </ul>
        </article>
        <article className="role-panel rounded-xl border border-line bg-surface p-5 shadow-xs space-y-2.5">
          <span className="role-panel-label font-mono text-[11px] font-semibold text-accent">03 / REVIEW</span>
          <h3 className="text-base font-semibold text-ink">SQA Engineer</h3>
          <ul className="space-y-1.5 text-xs text-muted list-disc pl-4">
            <li>Reviews shared requirements and generated artifacts</li>
            <li>Adds reviewer notes and changes review status</li>
            <li>Approves or requests revision; views dashboards and exports reports</li>
          </ul>
        </article>
      </section>

      <section className="card review-guidance rounded-xl border border-line bg-surface p-6 shadow-xs space-y-3" aria-labelledby="review-guidance-title">
        <h2 id="review-guidance-title" className="text-base font-semibold text-ink">Suggestions need human review</h2>
        <p className="text-xs leading-relaxed text-muted">
          AI outputs are suggestions, including any proposed facts, limits and assumptions. Qualitative requirement-risk suggestions indicate where refinement or review may be needed; they do not prove software defects or guarantee correctness.
        </p>
        <p className="text-xs leading-relaxed text-muted">
          Generating a test case does not execute tests against an external application. SQA Engineers perform Manual execution and record their observations, including separate retest evidence. SQA approval records a human review decision.
        </p>
        <p className="text-xs leading-relaxed text-muted">
          The implemented workflow covers one shared project with context supplied by the SQA Admin. Multi-project isolation is not currently implemented.
        </p>
      </section>
    </div>
  );
}
