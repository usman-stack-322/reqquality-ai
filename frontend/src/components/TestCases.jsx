import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api.js';
import ExecutionBugs from './ExecutionBugs';
import AIReviewAssistant from './AIReviewAssistant';

const blank = { title:'', category:'Positive', preconditions:[], test_data:'', test_steps:[], expected_result:'', test_type:'Unspecified', priority:'Medium', criterion_codes:[], clarification_notes:'' };
const split = value => value.split('\n').map(v => v.trim()).filter(Boolean);

function CaseForm({ value: initial, requirement, onSave, busy }) {
  const [value, setValue] = useState(initial);
  const [preconditions,setPreconditions] = useState(initial.preconditions.join('\n'));
  const [steps,setSteps] = useState(initial.test_steps.join('\n'));
  const set = (key, entry) => setValue(v => ({ ...v, [key]:entry }));
  return <form className="case-edit-form" onSubmit={e => {e.preventDefault(); onSave({...value,preconditions:split(preconditions),test_steps:split(steps)});}}><fieldset disabled={busy}><legend>{initial.id ? `Edit TC-${initial.id}` : 'Create detailed test case'}</legend>
    <label>Case title<input required maxLength={200} value={value.title} onChange={e => set('title',e.target.value)} /></label>
    <label>Case category<select value={value.category} onChange={e => set('category',e.target.value)}>{['Positive','Negative','Boundary','Edge-case'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Test type<select value={value.test_type} onChange={e => set('test_type',e.target.value)}>{['Unspecified','Functional','Security','Performance','Usability','Regression','Other'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Case priority<select value={value.priority} onChange={e => set('priority',e.target.value)}>{['Low','Medium','High'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Preconditions, one per line<textarea maxLength={50000} value={preconditions} onChange={e => setPreconditions(e.target.value)} /></label>
    <label>Test data<textarea maxLength={10000} value={value.test_data} onChange={e => set('test_data',e.target.value)} /></label>
    <label>Execution steps, one per line<textarea required rows={5} maxLength={50000} value={steps} onChange={e => setSteps(e.target.value)} /></label>
    <ol aria-label="Numbered execution steps">{split(steps).map((v,i) => <li key={i}>{v}</li>)}</ol>
    <label>Expected results<textarea required rows={3} maxLength={10000} value={value.expected_result} onChange={e => set('expected_result',e.target.value)} /></label>
    <label>Clarification needs<textarea maxLength={5000} value={value.clarification_notes} onChange={e => set('clarification_notes',e.target.value)} /></label>
    <fieldset><legend>Acceptance-criteria links for current requirement version</legend>{requirement.acceptance_criteria.map(c => <label key={c.criterion_code}><input type="checkbox" checked={value.criterion_codes.includes(c.criterion_code)} onChange={e => set('criterion_codes',e.target.checked ? [...value.criterion_codes,c.criterion_code] : value.criterion_codes.filter(v => v!==c.criterion_code))} />{c.criterion_code}: {c.description}</label>)}</fieldset>
    {value.criterion_codes.filter(code => !requirement.acceptance_criteria.some(c => c.criterion_code===code)).map(code => <label key={code}><input type="checkbox" checked onChange={() => set('criterion_codes',value.criterion_codes.filter(v => v!==code))} />{code}: historical link; remove or replace before rebasing</label>)}
    <p>Saving creates a new Draft case version linked to requirement content version {requirement.content_revision}. Unspecified behavior must remain flagged for clarification.</p>
    <button type="submit">Save test case as Draft</button>
  </fieldset></form>;
}

function CaseReview({ testCase:c, requirement, busy, send }) {
  const [target,setTarget] = useState(c.review_status==='In Review' ? 'Approved':'In Review');
  const [notes,setNotes] = useState(c.review_notes || '');
  if (c.review_status==='Approved') return <p>This case is approved. Editing it creates a new Draft version.</p>;
  return <form onSubmit={e => {e.preventDefault();send(`/${c.id}/review`,'PATCH',{revision:requirement.revision,case_revision:c.case_revision,review_status:target,review_notes:notes});}}><fieldset disabled={busy}><legend>Test case review</legend>
    <label>Case review decision<select value={target} onChange={e => setTarget(e.target.value)}>{(c.review_status==='In Review' ? ['Approved','Needs Revision','In Review']:['In Review']).map(v=><option key={v}>{v}</option>)}</select></label>
    <label>Case reviewer notes<textarea required={target==='Needs Revision'} maxLength={5000} value={notes} onChange={e=>setNotes(e.target.value)} /></label><button>Save case review</button>
  </fieldset></form>;
}

function ExecutionForm({ testCase, onSave, busy }) {
  const [value,setValue] = useState({ status:'Not Run',actual_result:'',blocked_reason:'',environment:'',build:'',notes:'',evidence_reference:'' });
  const submission = useRef(null);
  const set = (key,entry) => setValue(v => ({ ...v,[key]:entry }));
  return <form className="manual-execution-form" onSubmit={async e => {
    e.preventDefault();
    const payload = { ...value, case_revision:testCase.case_revision };
    const body = JSON.stringify(payload);
    if (submission.current?.body !== body) submission.current = {body,key:crypto.randomUUID()};
    if (await onSave(payload,submission.current.key)) {submission.current=null; setValue(v => ({...v,status:'Not Run',actual_result:'',blocked_reason:'',notes:'',evidence_reference:''}));}
  }}><fieldset disabled={busy}><legend>Manual execution</legend>
    <p>You run these steps against your application and record the observed result. Generating or saving this case does not test an external application.</p>
    <label>Execution status<select value={value.status} onChange={e => set('status',e.target.value)}>{['Not Run','Pass','Fail','Blocked'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Actual result<textarea required={['Pass','Fail'].includes(value.status)} maxLength={20000} value={value.actual_result} onChange={e => set('actual_result',e.target.value)} /></label>
    {value.status==='Blocked' && <label>Blocked reason<textarea required maxLength={5000} value={value.blocked_reason} onChange={e => set('blocked_reason',e.target.value)} /></label>}
    <label>Environment<input required maxLength={200} value={value.environment} onChange={e => set('environment',e.target.value)} /></label>
    <label>Build / version<input required maxLength={200} value={value.build} onChange={e => set('build',e.target.value)} /></label>
    <label>Execution notes<textarea maxLength={10000} value={value.notes} onChange={e => set('notes',e.target.value)} /></label>
    <label>Evidence reference (optional)<input maxLength={2000} value={value.evidence_reference} onChange={e => set('evidence_reference',e.target.value)} /></label>
    <p>Tester and timestamp are recorded by the server. Each save or retest adds a historical record; it does not replace earlier evidence.</p>
    <button type="submit">Record manual execution / retest</button>
  </fieldset></form>;
}

function History({ rid, testCase, refresh, user }) {
  const [bugExecution,setBugExecution]=useState(null);
  const [tab,setTab] = useState('executions');
  const [page,setPage] = useState(1);
  const [data,setData] = useState(null);
  const [error,setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setError(''); setData(null);
    apiFetch(`/api/requirements/${rid}/test-cases/${testCase.id}/${tab}?page=${page}`,{signal:controller.signal}).then(async response => {
      const result=await response.json(); if (!response.ok) throw new Error(result.error || 'Unable to load history.');
      if (!controller.signal.aborted) setData(result);
    }).catch(e => {if (!controller.signal.aborted) setError(e.message);});
    return () => controller.abort();
  },[rid,testCase.id,tab,page,refresh]);
  return <section><h4>Historical records</h4><button type="button" onClick={() => {setTab('executions');setPage(1);}}>Manual execution history</button><button type="button" onClick={() => {setTab('versions');setPage(1);}}>Case version history</button>
    {error && <p role="alert">{error}</p>}
    {data && <><p>{data.total} {tab} recorded</p>{data[tab].map(item => <details key={item.id} id={tab==='executions' ? `execution-${item.id}` : undefined}><summary>{tab==='executions' ? `Execution #${item.id}: ${item.status} — ${item.tester_name}, ${new Date(item.executed_at).toLocaleString()}` : `Case version ${item.case_revision} — ${new Date(item.recorded_at).toLocaleString()}`}</summary>
      {tab==='executions' && <><p>Environment: {item.environment}; Build: {item.build}</p><p>Actual result: {item.actual_result || 'Not recorded'}</p>{item.blocked_reason && <p>Blocked: {item.blocked_reason}</p>}<p>Notes: {item.notes || 'None'}</p><p>Evidence reference: {item.evidence_reference || 'None'}</p></>}
      {tab==='executions'&&item.status==='Fail'&&<><button type="button" onClick={()=>setBugExecution(bugExecution===item.id?null:item.id)}>Bugs for execution #{item.id}</button>{bugExecution===item.id&&<ExecutionBugs execution={item} user={user} refresh={refresh} />}</>}
      <p>Project {item.snapshot.project_id} · Requirement content version {item.snapshot.requirement_revision} · Case version {item.snapshot.case_revision}</p>
      <p>Requirement: {item.snapshot.requirement_snapshot.description}</p><p>Case: {item.snapshot.title}</p><p>Test data: {item.snapshot.test_data || 'Not specified'}</p><ol>{item.snapshot.test_steps.map((v,i) => <li key={i}>{v}</li>)}</ol><p>Expected: {item.snapshot.expected_result}</p><p>Criterion links: {item.snapshot.criterion_codes.join(', ') || 'None'}</p><ul>{item.snapshot.requirement_snapshot.acceptance_criteria.map(c => <li key={c.criterion_code}>{c.criterion_code}: {c.description}</li>)}</ul>
    </details>)}<button disabled={page===1} onClick={() => setPage(v=>v-1)}>Previous history page</button><button disabled={page*data.page_size>=data.total} onClick={() => setPage(v=>v+1)}>Next history page</button></>}
  </section>;
}

export default function TestCases({ requirement:r, user, onUpdate }) {
  const [selected,setSelected]=useState([]);
  const [reviewContext,setReviewContext]=useState(null);
  const canRequest=(user?.role==='Analyst'&&user.permissions?.includes('create_requirements'))||(user?.role==='SQA Engineer'&&user.permissions?.includes('review_requirements'));
  const [data,setData] = useState(null);
  const [page,setPage] = useState(1);
  const [refresh,setRefresh] = useState(0);
  const [editing,setEditing] = useState(null);
  const [opened,setOpened] = useState(null);
  const [busy,setBusy] = useState(false);
  const lock = useRef(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const canEdit = user?.role==='SQA Engineer' && user.id!==r.created_by_user_id && user.permissions?.includes('review_requirements');
  const canExecute = user?.role==='SQA Engineer' && user.permissions?.includes('execute_test_cases');
  useEffect(() => {
    const controller = new AbortController(); setError('');
    apiFetch(`/api/requirements/${r.id}/test-cases?page=${page}`,{signal:controller.signal}).then(async response => {
      const result=await response.json(); if (!response.ok) throw new Error(result.error || 'Unable to load test cases.');
      if (!controller.signal.aborted) setData(result);
    }).catch(e => {if (!controller.signal.aborted) setError(e.message);});
    return () => controller.abort();
  },[r.id,r.revision,page,refresh]);
  async function send(path,method,payload,key) {
    if (lock.current) return false;
    lock.current=true; setBusy(true); setError(''); setNotice('');
    try {
      const headers={'Content-Type':'application/json'}; if (key) headers['Idempotency-Key']=key;
      const response=await apiFetch(`/api/requirements/${r.id}/test-cases${path}`,{method,headers,body:JSON.stringify(payload)});
      const result=await response.json(); if (!response.ok) throw new Error(result.error || 'Unable to save.');
      if (result.requirement) {
        // A successful edit changed the case revision. Do not leave the old
        // executable row interactive while its refreshed list is in flight.
        setData(null);onUpdate(result.requirement);
      }
      setEditing(null); setRefresh(v=>v+1);
      setNotice(result.execution ? 'Manual execution recorded. Earlier evidence is preserved.' : 'Case version saved.');
      return true;
    } catch(e) {setError(e.message);return false;}
    finally {lock.current=false;setBusy(false);}
  }
  return <section className="detail-section detailed-test-cases" aria-busy={busy}><h2>Detailed test cases and Manual execution</h2>
    {canRequest&&<div className="ai-actions"><button onClick={()=>setReviewContext([])}>Discuss requirement coverage</button><button disabled={!selected.length} onClick={()=>setReviewContext([...selected])}>Request AI Revision for selected ({selected.length})</button></div>}
    {reviewContext&&<AIReviewAssistant key={`${r.id}-${reviewContext.join(',')}`} requirement={r} caseIds={reviewContext} user={user} onUpdate={updated=>{setData(null);onUpdate(updated);}} onClose={()=>setReviewContext(null)}/>}
    <p>Project {r.project_id} · Requirement content version {r.content_revision}. AI-generated cases start as editable drafts. Positive, negative and boundary behavior must be supported by the requirement; unspecified outcomes need clarification.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {!data&&!error&&<p role="status">Loading current test-case revisions…</p>}
    {error&&<button type="button" disabled={busy} onClick={()=>setRefresh(v=>v+1)}>Retry test cases</button>}
    {canEdit && <button type="button" disabled={busy} onClick={() => setEditing({...blank,priority:r.user_priority || 'Medium'})}>Create test case</button>}
    {editing && <CaseForm key={`${editing.id || 'new'}-${editing.case_revision || 0}`} value={editing} requirement={r} busy={busy} onSave={value => send(value.id ? `/${value.id}` : '',value.id ? 'PATCH':'POST',{...value,revision:r.revision})} />}
    {data?.test_cases.map(c => <article className="card" key={c.id} id={`test-case-${c.id}`}><h3>{c.stable_id}: {c.title}</h3><p>{c.scenario_code} · {c.category} · {c.test_type} · Priority {c.priority} · {c.review_status}</p><p>Case version {c.case_revision} · Requirement content version {c.requirement_revision} · Latest manual result for this case version: {c.latest_execution_status}</p>
      {canRequest&&!c.archived&&!c.stale&&<div className="ai-actions"><label><input type="checkbox" checked={selected.includes(c.id)} onChange={e=>setSelected(v=>e.target.checked?[...v,c.id]:v.filter(id=>id!==c.id))}/> Select {c.stable_id} for shared feedback</label><button onClick={()=>setReviewContext([c.id])}>Request AI Revision</button></div>}
      {c.archived && <p>Archived after reanalysis. Original links and execution evidence remain available below.</p>}{c.stale && !c.archived && <p>Earlier requirement version. Edit and verify the links to rebase this case before new execution.</p>}
      {c.needs_confirmation && <p>Draft/review needed; generated expected behavior is unconfirmed.</p>}{c.clarification_notes && <p>Requires clarification: {c.clarification_notes}</p>}
      <p>Criterion links: {c.criterion_codes.join(', ') || 'None'}</p><p>Preconditions: {c.preconditions.join('; ') || 'None'}</p><p>Test data: {c.test_data || 'Not specified'}</p><ol>{c.test_steps.map((v,i)=><li key={i}>{v}</li>)}</ol><p>Expected results: {c.expected_result}</p>
      {canEdit && !c.archived && <><button disabled={busy} onClick={() => setEditing(c)}>Edit {c.stable_id}</button><CaseReview key={c.case_revision} testCase={c} requirement={r} busy={busy} send={send} /></>}
      <button type="button" onClick={() => setOpened(opened===c.id ? null:c.id)}>{opened===c.id ? 'Close':'Open'} Manual execution and history for {c.stable_id}</button>
      {opened===c.id && <>{canExecute && !c.archived && !c.stale && <ExecutionForm testCase={c} busy={busy} onSave={(payload,key) => send(`/${c.id}/executions`,'POST',payload,key)} />}<History rid={r.id} testCase={c} refresh={refresh} user={user} /></>}
    </article>)}
    {data && <nav aria-label="Test case pages"><button disabled={page===1} onClick={()=>setPage(v=>v-1)}>Previous cases</button><span> Page {page}; {data.total} cases including archived </span><button disabled={page*data.page_size>=data.total} onClick={()=>setPage(v=>v+1)}>Next cases</button></nav>}
  </section>;
}
