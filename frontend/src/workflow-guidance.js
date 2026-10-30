// Authoring state and SQA decision are different stages; keep both visible.
export function nextStep(requirement, isEngineer) {
  const status = requirement.review_status;
  if (isEngineer) {
    if (status === 'Draft') return 'Awaiting Analyst submission';
    if (status === 'Needs Revision') return 'Awaiting Analyst updates';
    if (status === 'Approved') return 'Inspect case approvals and execution evidence';
    return 'Review criteria and test cases; request AI revisions if needed';
  }
  if (status === 'Draft') return 'Analyze or refine the draft, then submit for SQA review';
  if (status === 'Needs Revision') return 'Address reviewer notes and resubmit';
  if (status === 'Approved') return 'View approved requirement and report';
  return 'Submitted: follow the SQA review and respond to feedback';
}
