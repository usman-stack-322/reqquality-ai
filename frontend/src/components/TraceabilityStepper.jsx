import React from 'react';
import { Bug, Check, CheckCircle2, FileCheck2, FlaskConical } from 'lucide-react';

const STEPS = [
  { key: 'draft', label: 'Draft' },
  { key: 'analyzed', label: 'AI Analyzed' },
  { key: 'pending_sqa', label: 'Pending SQA' },
  { key: 'approved', label: 'Approved' },
  { key: 'executed', label: 'Executed' },
];

export function computeStepIndex({
  reviewStatus = 'Draft',
  sqaReviewStatus = 'Pending',
  hasAnalysis = false,
  hasExecutions = false,
}) {
  if (hasExecutions && (sqaReviewStatus === 'Approved' || reviewStatus === 'Approved')) return 4;
  if (sqaReviewStatus === 'Approved' || reviewStatus === 'Approved') return 3;
  if (['Ready for Review', 'In Review', 'Pending', 'Needs Revision'].includes(reviewStatus) || ['In Review', 'Needs Revision'].includes(sqaReviewStatus)) return 2;
  if (hasAnalysis) return 1;
  return 0;
}

export default function TraceabilityStepper({
  reviewStatus = 'Draft',
  sqaReviewStatus = 'Pending',
  hasAnalysis = false,
  hasExecutions = false,
  criteriaCount = 0,
  caseCount = 0,
  bugCount = 0,
  onJump,
}) {
  const activeIndex = computeStepIndex({ reviewStatus, sqaReviewStatus, hasAnalysis, hasExecutions });

  return (
    <section
      className="rounded-xl border border-line bg-surface p-4 shadow-xs"
      aria-label="Requirement traceability progress"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5 sm:gap-0 flex-1">
          {STEPS.map((step, index) => {
            const complete = index < activeIndex || (index === 4 && activeIndex === 4);
            const current = index === activeIndex && !(index === 4 && activeIndex === 4);
            const needsRevision = index === 2 && (reviewStatus === 'Needs Revision' || sqaReviewStatus === 'Needs Revision');
            return (
              <li key={step.key} className="relative flex items-center gap-2.5 sm:flex-col sm:items-start sm:gap-1.5 sm:pr-4">
                {index < STEPS.length - 1 && (
                  <span
                    className={`hidden sm:block absolute top-3.5 left-8 right-2 h-0.5 ${index < activeIndex ? 'bg-success' : 'bg-line'}`}
                    aria-hidden="true"
                  />
                )}
                <span
                  className={`relative z-1 inline-flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                    needsRevision
                      ? 'border-danger bg-danger-tint text-danger'
                      : complete
                        ? 'border-success bg-success-tint text-success'
                        : current
                          ? 'border-accent bg-accent-tint text-accent ring-2 ring-accent/20'
                          : 'border-line bg-surface-alt text-muted'
                  }`}
                >
                  {complete ? <Check className="size-3.5" aria-hidden="true" /> : index + 1}
                </span>
                <div className="min-w-0">
                  <span className={`block text-xs font-semibold truncate ${current || complete ? 'text-ink' : 'text-muted'}`}>
                    {step.label}
                  </span>
                  {needsRevision && (
                    <span className="block text-[10px] font-medium text-danger">Needs revision</span>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3 lg:border-t-0 lg:border-l lg:pl-4 lg:pt-0 shrink-0">
          <button
            type="button"
            onClick={() => onJump?.('criteria-section')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface-alt px-2.5 py-1.5 text-xs font-medium text-ink hover:border-accent/40"
          >
            <FileCheck2 className="size-3.5 text-accent" aria-hidden="true" />
            <span>Criteria</span>
            <strong className="tabular-nums">{criteriaCount}</strong>
          </button>
          <button
            type="button"
            onClick={() => onJump?.('cases-section')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface-alt px-2.5 py-1.5 text-xs font-medium text-ink hover:border-accent/40"
          >
            <FlaskConical className="size-3.5 text-success" aria-hidden="true" />
            <span>Test Cases</span>
            <strong className="tabular-nums">{caseCount}</strong>
          </button>
          <button
            type="button"
            onClick={() => onJump?.('cases-section')}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium hover:border-accent/40 ${
              bugCount > 0 ? 'border-danger/30 bg-danger-tint text-danger' : 'border-line bg-surface-alt text-ink'
            }`}
          >
            <Bug className="size-3.5" aria-hidden="true" />
            <span>Bugs</span>
            <strong className="tabular-nums">{bugCount}</strong>
          </button>
          {sqaReviewStatus === 'Approved' && (
            <span className="inline-flex items-center gap-1 rounded-lg bg-success-tint px-2 py-1 text-xs font-semibold text-success">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              SQA Approved
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
