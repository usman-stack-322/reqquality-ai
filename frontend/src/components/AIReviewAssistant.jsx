import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api.js';

const fields = ['title','category','test_type','priority','preconditions','test_data','test_steps','expected_result','criterion_codes','clarification_notes'];
const display = v => Array.isArray(v) ? v.join('\n') : v || 'None';

export function ProposalPreview({ turn }) {
  return <>{turn.proposal.changes.map((change,i) => {
    const saved=turn.base_snapshot.test_cases.find(c=>c.id===change.case_id);
    return <article className="ai-proposal" key={i}>
      <h4>{change.operation==='new' ? 'NEW proposed test case' : `${change.operation==='archive' ? 'Archive duplicate' : 'Revise'} TC-${change.case_id}`}</h4>
      <p>{change.summary}</p>{change.operation==='archive'&&<p>Acceptance archives this duplicate and preserves its history.</p>}
      <div className="ai-comparison"><section><h5>Saved version{saved ? ` · v${saved.case_revision}` : ''}</h5>{saved ? fields.map(k=><div key={k}><strong>{k.replaceAll('_',' ')}</strong><pre>{display(saved[k])}</pre></div>):<p>New case; no saved version.</p>}</section>
        <section><h5>Proposed version · {change.operation==='archive' ? 'Archived' : 'Pending Review on acceptance'}</h5>{fields.map(k=><div className={JSON.stringify(saved?.[k])!==JSON.stringify(change.content[k]) ? 'ai-changed' : ''} key={k}><strong>{k.replaceAll('_',' ')}{JSON.stringify(saved?.[k])!==JSON.stringify(change.content[k]) ? ' · changed' : ''}</strong><pre>{display(change.content[k])}</pre></div>)}</section></div>
    </article>;
  })}</>;
}

export default function AIReviewAssistant({ requirement, caseIds, user, onUpdate, onClose }) {
  const [session,setSession]=useState(null), [feedback,setFeedback]=useState(''), [error,setError]=useState(''), [busy,setBusy]=useState(false), [notice,setNotice]=useState(''), [retry,setRetry]=useState(0);
  const lock=useRef(false), submission=useRef(null), active=useRef(true), input=useRef(null);
  const base=`/api/requirements/${requirement.id}/ai-review`;
  useEffect(()=>{
    active.current=true; const controller=new AbortController();
    apiFetch(base,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_ids:caseIds}),signal:controller.signal}).then(async r=>{
      const data=await r.json();if(!r.ok) throw new Error(data.error||'Unable to open review context.');
      if(!controller.signal.aborted){setSession(data);setError('');const failed=data.turns.filter(t=>['failed','generating'].includes(t.status)).at(-1);if(failed){setFeedback(failed.feedback);submission.current={feedback:failed.feedback,key:failed.request_key};}}
    }).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return ()=>{active.current=false;controller.abort();};
  },[base,retry]);
  async function post(path,payload) {
    const r=await apiFetch(base+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await r.json(); if(!r.ok)throw new Error(data.error||'Unable to complete request.'); return data;
  }
  async function generate(e) {
    e.preventDefault();if(lock.current||!feedback.trim()||!session)return;
    lock.current=true;setBusy(true);setError('');setNotice('');
    if(submission.current?.feedback!==feedback)submission.current={feedback,key:crypto.randomUUID()};
    try{
      const data=await post(`/${session.id}/messages`,{feedback,request_key:submission.current.key});
      if(!active.current)return;
      setSession(s=>({...s,turns:[...s.turns.filter(t=>t.id!==data.turn.id).map(t=>t.status==='proposed'?{...t,status:'superseded'}:t),data.turn]}));
      setFeedback('');submission.current=null;setNotice(data.turn.proposal.kind==='proposal'?'Proposal ready. Saved cases are unchanged.':'Assistant response ready.');
    }catch(e){if(active.current)setError(e.message);}finally{lock.current=false;if(active.current)setBusy(false);}
  }
  async function decide(turn,action) {
    if(lock.current)return;lock.current=true;setBusy(true);setError('');
    try{
      const data=await post(`/${session.id}/proposals/${turn.id}`,{action});if(!active.current)return;
      setSession(s=>({...s,turns:s.turns.map(t=>t.id===turn.id?{...t,status:data.status}:t)}));
      if(action==='accept')onUpdate(data.requirement);
      setNotice(action==='accept'?'Changes saved as Pending Review. SQA Engineer approval is still required.':'Proposal rejected. Saved cases are unchanged.');
    }catch(e){if(active.current)setError(e.message);}finally{lock.current=false;if(active.current)setBusy(false);}
  }
  const canAccept=user.role==='SQA Engineer'&&user.id!==requirement.created_by_user_id&&user.permissions?.includes('review_requirements');
  return <aside className="ai-review-panel" role="dialog" aria-modal="false" aria-labelledby="ai-review-title" aria-busy={busy}>
    <div className="ai-review-context"><header><h2 id="ai-review-title">AI Review Assistant</h2><button type="button" onClick={onClose} aria-label="Close AI Review Assistant">Close</button></header>
    <p><strong>Project {requirement.project_id} · REQ-{requirement.id}: {requirement.title}</strong></p>
    <p>Selected: {caseIds.length ? caseIds.map(id=>`TC-${id}`).join(', ') : 'Requirement coverage discussion (no cases selected)'}. Changing the selection opens its own conversation.</p></div>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!session&&<><p>Loading authorized review context…</p>{error&&<button onClick={()=>setRetry(v=>v+1)}>Retry opening assistant</button>}</>}
    {session&&<><p>Source content version {session.context.requirement.content_revision}. AI proposals need human review.</p>
      {!session.turns.length&&<p>Describe what needs improving, or ask about requirement coverage. Unsupported behavior will need clarification.</p>}
      <div className="ai-conversation" aria-label="Review conversation">{session.turns.map(t=><section key={t.id} className="ai-turn"><h3>Reviewer feedback</h3><p className="ai-feedback">{t.feedback}</p><small>{new Date(t.created_at).toLocaleString()} · {t.status}{t.decision_actor_id ? ` · decision by user ${t.decision_actor_id}`:''}</small>
        {t.proposal&&<><h3>Assistant</h3><p className="ai-feedback">{t.proposal.message}</p>{t.status==='proposed'?<ProposalPreview turn={t}/>:t.proposal.changes.length>0&&<details><summary>View {t.status} proposal</summary><ProposalPreview turn={t}/></details>}{t.status==='proposed'&&<div className="ai-actions"><button disabled={busy||!canAccept} onClick={()=>decide(t,'accept')}>Accept Changes</button><button disabled={busy} onClick={()=>decide(t,'reject')}>Reject</button><button disabled={busy} onClick={()=>input.current?.focus()}>Request Another Revision</button>{!canAccept&&<p>An authorized SQA Engineer must accept revisions from their review context.</p>}</div>}</>}
        {t.status==='failed'&&<p>Generation failed. Your feedback was saved; retry below.</p>}{t.status==='generating'&&<p>A request is processing. Retry the same feedback if it was interrupted.</p>}
      </section>)}</div>
      <form onSubmit={generate}><label>Feedback or coverage question<textarea ref={input} value={feedback} onChange={e=>setFeedback(e.target.value)} required maxLength={8000} rows={4} disabled={busy}/></label><button disabled={busy||!feedback.trim()}>{busy?'Working…':error?'Retry / Send feedback':'Send feedback'}</button></form>
    </>}
  </aside>;
}
