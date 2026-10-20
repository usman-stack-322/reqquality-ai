import React, { useEffect, useState } from 'react';
import { apiFetch } from '../api.js';
import ExecutionBugs from './ExecutionBugs';

export default function IntegratedReview({ requirement:r, user }) {
  const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
  const [retry,setRetry]=useState(0),[selected,setSelected]=useState(null),[bugsFor,setBugsFor]=useState(null);
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setError('');
    apiFetch(`/api/requirements/${r.id}/traceability`,{signal:controller.signal}).then(async response=>{
      const value=await response.json();if(!response.ok)throw new Error(value.error||'Unable to load versioned evidence.');
      if(!controller.signal.aborted){setData(value);setSelected(old=>old??value.current_content_revision);}
    }).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[r.id,r.revision,retry]);
  const version=data?.versions.find(v=>v.content_revision===selected);
  // Retain the last snapshot of each case within the selected source version.
  const cases=new Map();
  for(const v of data?.case_versions||[])if(v.requirement_revision===selected)cases.set(v.scenario_id,v);
  const runs=(data?.executions||[]).filter(e=>e.requirement_revision===selected);
  const reviews=(data?.reviews||[]).filter(v=>v.content_revision===selected);
  return <section className="detail-section integrated-review" aria-busy={loading}><h2>Requirement versions, traceability and SQA review</h2>
    <p>Requirement version → acceptance criteria → case snapshot → Manual execution → bug → version-bound review. Recorded links do not prove complete coverage or successful execution.</p>
    <button type="button" disabled={loading} onClick={()=>setRetry(v=>v+1)}>Refresh evidence / Retry</button>
    {loading&&<p role="status">Loading versioned evidence…</p>}{error&&<p className="error" role="alert">{error}</p>}
    {!loading&&!error&&data&&<><p>Current SQA review: <strong>{data.sqa_review_status}</strong>. Authoring state: {data.authoring_status}. Current requirement content version: {data.current_content_revision}.</p>
      <label>Requirement version<select value={selected??''} onChange={e=>{setSelected(Number(e.target.value));setBugsFor(null);}}>{data.versions.map(v=><option key={v.id} value={v.content_revision}>{v.content_revision}{v.current?' (current)':' (historical)'}</option>)}</select></label>
      {version?<><p>{version.current?'Current source version.':'Historical evidence: this does not validate the current requirement.'} Recorded {new Date(version.recorded_at).toLocaleString()}. {version.origin}.</p><p>{version.snapshot.description}</p>
        <h3>Acceptance criteria for version {selected}</h3>{version.snapshot.acceptance_criteria?.length?<ul>{version.snapshot.acceptance_criteria.map(a=><li key={a.criterion_code}>{a.criterion_code}: {a.description}{version.current&&r.criteria_review_required?' — Needs review':''}<ul>{[...cases.values()].filter(v=>v.snapshot.criterion_codes.includes(a.criterion_code)).map(v=><li key={v.id}>TC-{v.scenario_id}, case revision {v.case_revision}, snapshot #{v.id}</li>)}</ul></li>)}</ul>:<p>No acceptance criteria recorded for this version.</p>}
      </>:<p>No source snapshot recorded. Earlier legacy versions may be unavailable.</p>}
      <h3>Cases and immutable execution evidence</h3>{!cases.size&&<p>No test-case snapshots for this version.</p>}
      {[...cases.values()].map(v=><details key={v.id}><summary>TC-{v.scenario_id}: {v.snapshot.title} — case revision {v.case_revision}, {v.snapshot.review_status}</summary><p>Criteria: {v.snapshot.criterion_codes.join(', ')||'Unlinked'}. Case snapshot #{v.id}.</p><ol>{v.snapshot.test_steps.map((s,i)=><li key={i}>{s}</li>)}</ol><p>Expected: {v.snapshot.expected_result}</p>
        {runs.filter(e=>e.scenario_id===v.scenario_id).length===0&&<p>Not Run. No execution recorded for this source version.</p>}
        {runs.filter(e=>e.scenario_id===v.scenario_id).map(e=><article key={e.id}><h4>Manual execution #{e.id}: {e.status}</h4><p>Executed case snapshot #{e.case_version_id}; {e.tester_name}, {new Date(e.executed_at).toLocaleString()}. {e.environment} / {e.build}</p><p>Actual: {e.actual_result||'Not recorded'}. Blocked reason: {e.blocked_reason||'None'}</p><p>Evidence reference: {e.evidence_reference||'None'}</p><ul>{data.bugs.filter(b=>b.failed_execution_id===e.id).map(b=><li key={b.id}>{b.stable_id}: {b.title} — {b.status}, Severity {b.severity}, Priority {b.priority}</li>)}</ul>{e.status==='Fail'&&<><button type="button" onClick={()=>setBugsFor(old=>old===e.id?null:e.id)}>Inspect / manage bugs for execution #{e.id}</button>{bugsFor===e.id&&<ExecutionBugs execution={e} user={user} refresh={retry} />}</>}</article>)}
      </details>)}
      <h3>SQA review of version {selected}</h3>{reviews.length?<ol>{reviews.map(v=><li key={v.id}>{v.status}: {v.reviewer_name} (User {v.reviewer_id}), {new Date(v.reviewed_at).toLocaleString()}<p>{v.notes||'No notes recorded.'}</p><p>Reviewed requirement version {v.content_revision}; case snapshots {v.snapshot.case_version_ids.join(', ')||'none'}; executions {v.snapshot.execution_ids.join(', ')||'none'}; bugs {v.snapshot.bug_ids.join(', ')||'none'}.</p></li>)}</ol>:<p>No version-verified SQA review. Legacy review metadata has an unknown reviewed version.</p>}
    </>}
  </section>;
}
