import test from 'node:test';
import assert from 'node:assert/strict';
import { nextStep } from './workflow-guidance.js';
test('role guidance distinguishes submission, revision and approval from execution',()=>{
  assert.match(nextStep({review_status:'Draft'},false),/submit/);
  assert.match(nextStep({review_status:'Draft'},true),/Awaiting Analyst/);
  assert.match(nextStep({review_status:'Ready for Review'},true),/Review criteria/);
  assert.match(nextStep({review_status:'Needs Revision'},false),/resubmit/);
  assert.match(nextStep({review_status:'Approved'},true),/case approvals and execution/);
});
