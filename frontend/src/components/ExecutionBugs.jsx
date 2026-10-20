import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api.js';

const fields = ['title','preconditions','steps_to_reproduce','expected_result','actual_result','severity','priority','environment','build','evidence_reference'];
const editable = bug => Object.fromEntries(fields.map(key=>[key,bug[key]]));
const lines = value => value.split('\n').map(v=>v.trim()).filter(Boolean);
function showSource(event, id) {
  const element=document.getElementById(id);
  if (!element) return;
  event.preventDefault();
  if (element.tagName==='DETAILS') element.open=true;
  element.scrollIntoView({block:'center'});
}

function BugForm({ initial, busy, save, label }) {
  const [value,setValue] = useState(editable(initial));
  const [preconditions,setPreconditions]=useState(initial.preconditions.join('\n'));
  const [steps,setSteps]=useState(initial.steps_to_reproduce.join('\n'));
  const set=(key,v)=>setValue(old=>({...old,[key]:v}));
  return <form onSubmit={e=>{e.preventDefault();save({...value,preconditions:lines(preconditions),steps_to_reproduce:lines(steps)});}}><fieldset disabled={busy}><legend>{label}</legend>
    <p>Review and edit the supplied execution details before saving. Severity and priority are separate decisions.</p>
    <label>Bug title<input required maxLength={200} value={value.title} onChange={e=>set('title',e.target.value)} /></label>
    <label>Bug preconditions<textarea maxLength={50000} value={preconditions} onChange={e=>setPreconditions(e.target.value)} /></label>
    <label>Steps to reproduce, one per line<textarea required rows={4} maxLength={50000} value={steps} onChange={e=>setSteps(e.target.value)} /></label>
    <ol>{lines(steps).map((v,i)=><li key={i}>{v}</li>)}</ol>
    <label>Bug expected result<textarea required maxLength={20000} value={value.expected_result} onChange={e=>set('expected_result',e.target.value)} /></label>
    <label>Bug actual result<textarea required maxLength={20000} value={value.actual_result} onChange={e=>set('actual_result',e.target.value)} /></label>
    <label>Severity<select value={value.severity} onChange={e=>set('severity',e.target.value)}>{['Critical','High','Medium','Low'].map(v=><option key={v}>{v}</option>)}</select></label>
    <label>Bug priority<select value={value.priority} onChange={e=>set('priority',e.target.value)}>{['High','Medium','Low'].map(v=><option key={v}>{v}</option>)}</select></label>
    <label>Bug environment<input required maxLength={200} value={value.environment} onChange={e=>set('environment',e.target.value)} /></label>
    <label>Bug build / version<input required maxLength={200} value={value.build} onChange={e=>set('build',e.target.value)} /></label>
    <label>Bug evidence reference (optional)<input maxLength={2000} value={value.evidence_reference} onChange={e=>set('evidence_reference',e.target.value)} /></label>
    <button type="submit">Save bug</button>
  </fieldset></form>;
}

function BugDetail({ initial, canManage, changed, refresh }) {
  const [data,setData]=useState(null);
  const [events,setEvents]=useState(null);
  const [page,setPage]=useState(1);
  const [editing,setEditing]=useState(false);
  const [target,setTarget]=useState('');
  const [retest,setRetest]=useState('');
  const [reason,setReason]=useState('');
  const [note,setNote]=useState('');
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const lock=useRef(false);
  const [error,setError]=useState('');
  const [version,setVersion]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();setError('');setLoading(true);
    Promise.all([apiFetch(`/api/bugs/${initial.id}`,{signal:controller.signal}),apiFetch(`/api/bugs/${initial.id}/history?page=${page}`,{signal:controller.signal})]).then(async responses=>{
      const results=await Promise.all(responses.map(r=>r.json()));
      if (responses.some(r=>!r.ok)) throw new Error(results.find(r=>r.error)?.error || 'Unable to load bug.');
      if (!controller.signal.aborted) {setData(results[0]);setEvents(results[1]);setTarget(({Open:'In Progress','In Progress':'Ready for Retest','Ready for Retest':'Closed',Closed:'Open'})[results[0].bug.status]);}
    }).catch(e=>{if (!controller.signal.aborted) setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[initial.id,initial.revision,page,version,refresh]);
  async function save(payload,status=false) {
    if(lock.current || loading || !data) return;
    lock.current=true;setBusy(true);setError('');
    try {
      const response=await apiFetch(`/api/bugs/${initial.id}${status?'/status':''}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,revision:data.bug.revision})});
      const result=await response.json();if(!response.ok)throw new Error(result.error || 'Unable to save bug.');
      setData(old=>({...old,bug:result.bug}));
      setEditing(false);setRetest('');setReason('');setNote('');setVersion(v=>v+1);changed();
    } catch(e){setError(e.message);} finally{lock.current=false;setBusy(false);}
  }
  if(!data)return error?<p role="alert">{error}</p>:<p>Loading bug details…</p>;
  const b=data.bug;
  const targets=({Open:['In Progress'],'In Progress':['Ready for Retest'],'Ready for Retest':['Closed','Open'],Closed:['Open']})[b.status];
  return <section className="bug-detail"><p>Project {b.project_id} · <a href={`#requirement/${b.requirement_id}`}>REQ-{b.requirement_id}</a> · <a href={`#requirement/${b.requirement_id}`} onClick={e=>showSource(e,`test-case-${b.scenario_id}`)}>TC-{b.scenario_id}</a> · <a href={`#requirement/${b.requirement_id}`} onClick={e=>showSource(e,`execution-${b.failed_execution_id}`)}>Failed execution #{b.failed_execution_id}</a></p>
    <p>Reported by {b.reporter_name} (User {b.reporter_id}), {new Date(b.created_at).toLocaleString()}. Updated {new Date(b.updated_at).toLocaleString()}.</p>
    <p>Preconditions: {b.preconditions.join('; ') || 'None'}</p><ol>{b.steps_to_reproduce.map((v,i)=><li key={i}>{v}</li>)}</ol><p>Expected: {b.expected_result}</p><p>Actual: {b.actual_result}</p><p>Environment: {b.environment}; Build: {b.build}</p><p>Evidence reference: {b.evidence_reference || 'None'}</p>
    {b.last_retest_execution_id && <p>Linked retest execution #{b.last_retest_execution_id}</p>}{b.resolution_reason && <p>Documented resolution: {b.resolution_reason}</p>}
    {error&&<p role="alert">{error}</p>}
    {loading&&<p role="status">Refreshing current bug revision…</p>}
    {canManage&&<><button disabled={busy||loading} onClick={()=>setEditing(v=>!v)}>Edit bug</button>{editing&&<BugForm key={b.revision} initial={b} busy={busy||loading} save={value=>save(value)} label={`Edit ${b.stable_id}`} />}
      <form onSubmit={e=>{e.preventDefault();save({status:target,retest_execution_id:retest?Number(retest):null,resolution_reason:reason,note},true);}}><fieldset disabled={busy||loading}><legend>Bug status</legend>
        <p>Open → In Progress → Ready for Retest → Closed. Reopen with a new failed retest. A documented resolution can close without passing evidence; it does not claim a test passed.</p>
        <label>Next bug status<select value={target} onChange={e=>setTarget(e.target.value)}>{targets.map(v=><option key={v}>{v}</option>)}</select></label>
        {['Closed','Open'].includes(target)&&<><label>Retest execution ID<input type="number" min={1} list={`bug-retests-${b.id}`} required={target==='Open'} value={retest} onChange={e=>setRetest(e.target.value)} /></label><datalist id={`bug-retests-${b.id}`}>{data.retests.map(v=><option key={v.id} value={v.id}>{v.status} · {v.environment} · {v.build}</option>)}</datalist><p>Recent retests: {data.retests.map(v=>`#${v.id} ${v.status} (${v.build})`).join('; ') || 'None. Record a separate Manual execution first.'}</p>{target==='Closed'&&<label>Resolution reason (required without a passing retest)<textarea required={!retest} maxLength={5000} value={reason} onChange={e=>setReason(e.target.value)} /></label>}</>}
        <label>Status-change note<textarea maxLength={5000} value={note} onChange={e=>setNote(e.target.value)} /></label><button>Save bug status</button>
      </fieldset></form>
    </>}
    {events&&<section><h5>Status and change history</h5><ol>{events.history.map(event=><li key={event.id}>{event.action}: {event.from_status||'Created'} → {event.to_status} · {event.actor_name} · {new Date(event.recorded_at).toLocaleString()}{event.note&&<p>{event.note}</p>}{event.retest_execution_id&&<p>Retest execution #{event.retest_execution_id}</p>}<details><summary>Recorded bug revision {event.snapshot.revision}</summary><p>{event.snapshot.title} · Severity {event.snapshot.severity} · Priority {event.snapshot.priority}</p><p>{event.snapshot.resolution_reason}</p></details></li>)}</ol><button disabled={page===1} onClick={()=>setPage(v=>v-1)}>Previous bug history</button><button disabled={page*events.page_size>=events.total} onClick={()=>setPage(v=>v+1)}>Next bug history</button></section>}
  </section>;
}

export default function ExecutionBugs({ execution, user, refresh }) {
  const [data,setData]=useState(null);
  const [creating,setCreating]=useState(false);
  const [opened,setOpened]=useState(null);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [busy,setBusy]=useState(false);
  const [version,setVersion]=useState(0);
  const lock=useRef(false), submission=useRef(null);
  const canManage=user?.role==='admin'||(user?.role==='SQA Engineer'&&user.permissions?.includes('manage_bugs'));
  useEffect(()=>{
    const controller=new AbortController();setError('');
    apiFetch(`/api/executions/${execution.id}/bugs`,{signal:controller.signal}).then(async response=>{
      const value=await response.json();if(!response.ok)throw new Error(value.error || 'Unable to load linked bugs.');
      if(!controller.signal.aborted)setData(value);
    }).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return()=>controller.abort();
  },[execution.id,refresh,version]);
  async function create(value){
    if(lock.current)return;
    const body=JSON.stringify(value);if(submission.current?.body!==body)submission.current={body,key:crypto.randomUUID()};
    lock.current=true;setBusy(true);setError('');setNotice('');
    try{
      const response=await apiFetch(`/api/executions/${execution.id}/bugs`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':submission.current.key},body});
      const result=await response.json();if(!response.ok)throw new Error(result.error || 'Unable to save bug.');
      setCreating(false);setOpened(result.bug.id);setVersion(v=>v+1);setNotice(result.created?'Bug saved.':'An identical linked bug already exists; no duplicate was created.');
    }catch(e){setError(e.message);}finally{lock.current=false;setBusy(false);}
  }
  return <section className="execution-bugs"><h4>Bugs linked to failed execution #{execution.id}</h4>{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {data&&<><p>{data.bugs.length} linked bugs. Review existing bugs before reporting another.</p>{data.bugs.map(b=><article className="card" key={b.id}><h5>{b.stable_id}: {b.title}</h5><p>{b.status} · Severity {b.severity} · Priority {b.priority}</p><button onClick={()=>setOpened(opened===b.id?null:b.id)}>{opened===b.id?'Close':'Open'} {b.stable_id}</button>{opened===b.id&&<BugDetail initial={b} canManage={canManage} refresh={refresh} changed={()=>setVersion(v=>v+1)} />}</article>)}
      {canManage&&data.prefill&&<><button type="button" disabled={busy} onClick={()=>setCreating(true)}>Create bug from failed execution</button>{creating&&<BugForm initial={data.prefill} busy={busy} save={create} label="Review failure details before creating bug" />}</>}
      {!canManage&&<p>Read-only bug access. SQA Engineers and SQA Admins manage bug reports.</p>}
    </>}
  </section>;
}
