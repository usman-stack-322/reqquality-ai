"""Persistent, owner-scoped conversations and atomic, optimistic proposal acceptance."""
import json
import re
import time
import uuid
from flask import abort, g
from services.case_service import serialize_case, validate_case, ensure_version, requirement_snapshot
from services.requirement_helpers import _utc_timestamp
from services.project_service import current_project


def initialize_review_assistant_schema(c):
    c.execute("CREATE TABLE IF NOT EXISTS ai_review_conversations (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), requirement_id BIGINT NOT NULL REFERENCES requirements(id), actor_id BIGINT NOT NULL REFERENCES users(id), case_ids TEXT NOT NULL, created_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS ai_review_turns (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES ai_review_conversations(id), request_key TEXT NOT NULL, feedback TEXT NOT NULL, actor_id BIGINT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, started_at BIGINT NOT NULL, status TEXT NOT NULL, base_snapshot TEXT NOT NULL, proposal TEXT, decision_actor_id BIGINT REFERENCES users(id), decided_at TEXT, UNIQUE(conversation_id,request_key))")
    c.execute('CREATE INDEX IF NOT EXISTS idx_review_turns ON ai_review_turns(conversation_id,created_at,id)')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_review_context ON ai_review_conversations(requirement_id,actor_id,case_ids)')
    c.commit()


def permission(c, accept=False):
    role = g.current_user['role']
    key = {'Analyst':'create_requirements','SQA Engineer':'review_requirements'}.get(role)
    row = c.execute('SELECT enabled FROM role_permissions WHERE role=? AND permission=?',(role,key)).fetchone() if key else None
    if not row or not row['enabled'] or (accept and role != 'SQA Engineer'):
        abort(403,description='Authorized SQA Engineer required to accept revisions.' if accept else 'Review assistant permission is required.')


def source(c,rid,ids):
    req = c.execute("SELECT * FROM requirements WHERE id=? AND project_id='current'",(rid,)).fetchone()
    if not req: abort(404)
    cases=[]
    for sid in ids:
        row=c.execute("SELECT * FROM test_scenarios WHERE id=? AND requirement_id=? AND project_id='current' AND archived=0",(sid,rid)).fetchone()
        if not row: abort(409,description='Selected test case is missing or archived. Reopen the assistant with current cases.')
        if row['requirement_revision'] != req['content_revision']:
            abort(409,description='Selected case belongs to an earlier requirement version. Rebase it before requesting a revision.')
        cases.append(serialize_case(row))
    coverage=[]
    if not ids:
        coverage=[serialize_case(row) for row in c.execute('SELECT * FROM test_scenarios WHERE requirement_id=? AND archived=0 ORDER BY id LIMIT 100',(rid,))]
    total=c.execute('SELECT COUNT(*) FROM test_scenarios WHERE requirement_id=? AND archived=0',(rid,)).fetchone()[0]
    return {'project':current_project(c),'requirement':{**requirement_snapshot(c,rid),'revision':req['revision']},'test_cases':cases,
            'coverage_cases':coverage,'coverage_total':total,'coverage_limit':100 if not ids and total>100 else None}


def conversation(c,rid,cid):
    permission(c)
    row=c.execute("SELECT * FROM ai_review_conversations WHERE id=? AND requirement_id=? AND actor_id=? AND project_id='current'",(cid,rid,g.current_user['id'])).fetchone()
    if not row: abort(404)
    return dict(row)


def turns(c,cid):
    result=[]
    for row in c.execute('SELECT * FROM ai_review_turns WHERE conversation_id=? ORDER BY created_at,id',(cid,)):
        value=dict(row)
        value['base_snapshot']=json.loads(value['base_snapshot'])
        value['proposal']=json.loads(value['proposal']) if value['proposal'] else None
        result.append(value)
    return result


def open_conversation(rid,data):
    from app import get_connection
    if not isinstance(data,dict): abort(400)
    ids=data.get('case_ids',[])
    if not isinstance(ids,list) or len(ids)>30 or any(type(i)!=int or i<=0 for i in ids) or len(set(ids))!=len(ids): abort(400)
    c=get_connection()
    try:
        with c:
            permission(c)
            lock_context(c,rid)
            context=source(c,rid,sorted(ids))
            # Reopening the same selection resumes its conversation, including failed feedback.
            row=c.execute("SELECT id FROM ai_review_conversations WHERE requirement_id=? AND actor_id=? AND case_ids=? AND project_id='current' ORDER BY created_at DESC LIMIT 1",(rid,g.current_user['id'],json.dumps(sorted(ids)))).fetchone()
            cid=row['id'] if row else str(uuid.uuid4())
            if not row:
                c.execute("INSERT INTO ai_review_conversations VALUES(?,'current',?,?,?,?)",(cid,rid,g.current_user['id'],json.dumps(sorted(ids)),_utc_timestamp()))
            return {'id':cid,'context':context,'turns':turns(c,cid)}
    finally: c.close()


def validate_proposal(c,rid,result,base):
    if not isinstance(result,dict) or set(result)!={'kind','message','changes'}: raise ValueError()
    kind=result['kind']; message=result['message']; changes=result['changes']
    if kind not in ('proposal','clarification','discussion') or not isinstance(message,str) or not message.strip() or len(message)>10000: raise ValueError()
    if not isinstance(changes,list) or len(changes)>40 or (kind=='proposal') != bool(changes): raise ValueError()
    ids={v['id']:v for v in base['test_cases']}; seen=set(); normalized=[]
    for item in changes:
        if not isinstance(item,dict) or set(item)!={'operation','case_id','summary','content'}: raise ValueError()
        op,sid=item['operation'],item['case_id']
        if type(sid)!=int or op not in ('revise','new','archive') or (op=='new' and sid!=0) or (op!='new' and (sid not in ids or sid in seen)): raise ValueError()
        if op!='new': seen.add(sid)
        if not isinstance(item['summary'],str) or not item['summary'].strip() or len(item['summary'])>2000: raise ValueError()
        from analyzers.review_assistant import FIELDS
        if not isinstance(item['content'],dict) or set(item['content'])!=set(FIELDS): raise ValueError()
        content=validate_case(c,rid,item['content'])
        if op=='archive' and any(content[k]!=ids[sid][k] for k in FIELDS): raise ValueError()
        if op=='archive' and not any(v['id']!=sid and v['id'] not in {x['case_id'] for x in changes if x['operation']=='archive'} for v in base['test_cases']): raise ValueError()
        normalized.append({**item,'content':content})
    return {'kind':kind,'message':message.strip(),'changes':normalized}


def lock_context(c,rid):
    from services.workflow_service import locked_requirement
    row=c.execute('SELECT revision FROM requirements WHERE id=?',(rid,)).fetchone()
    if not row: abort(404)
    return locked_requirement(c,rid,{'revision':row['revision']})


def generate(rid,cid,data):
    from app import get_connection
    from analyzers.review_assistant import generate_review
    if not isinstance(data,dict): abort(400)
    feedback=data.get('feedback'); key=data.get('request_key')
    if not isinstance(feedback,str) or not feedback.strip() or len(feedback)>8000 or not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',key): abort(400)
    c=get_connection()
    try:
        with c:
            session=conversation(c,rid,cid); lock_context(c,rid)
            history=turns(c,cid)
            prior=next((t for t in history if t['request_key']==key),None)
            if prior and prior['feedback']!=feedback.strip(): abort(409,description='Submission key belongs to different feedback.')
            if prior and prior['status'] not in ('failed','generating'): return {'turn':prior}
            active=next((t for t in history if t['status']=='generating' and t['started_at']>time.time()-60),None)
            if active: abort(409,description='A revision is still generating. Retry shortly with the same feedback.')
            c.execute("UPDATE ai_review_turns SET status='failed' WHERE conversation_id=? AND status='generating' AND started_at<=?",(cid,int(time.time())-60))
            base=source(c,rid,json.loads(session['case_ids']))
            tid=prior['id'] if prior else str(uuid.uuid4())
            if prior:
                c.execute("UPDATE ai_review_turns SET status='generating',started_at=?,base_snapshot=? WHERE id=?",(int(time.time()),json.dumps(base),tid))
            else:
                c.execute("INSERT INTO ai_review_turns(id,conversation_id,request_key,feedback,actor_id,created_at,started_at,status,base_snapshot) VALUES(?,?,?,?,?,?,?,'generating',?)",(tid,cid,key,feedback.strip(),g.current_user['id'],_utc_timestamp(),int(time.time()),json.dumps(base)))
            latest=next((t['proposal'] for t in reversed(history) if t['proposal'] and t['proposal']['kind']=='proposal' and t['status']!='accepted'),None)
            context={**base,'feedback':feedback.strip(),'latest_proposal':latest,
                'history':[{'feedback':t['feedback'],'response':t['proposal'],'status':t['status']} for t in history[-12:] if t['id']!=tid]}
        # Release transaction and pool handle before the bounded network call.
    finally: c.close()
    try:
        result=generate_review(context)
        c=get_connection()
        try:
            with c:
                conversation(c,rid,cid); lock_context(c,rid)
                result=validate_proposal(c,rid,result,base)
                c.execute("UPDATE ai_review_turns SET status='superseded' WHERE conversation_id=? AND status='proposed'",(cid,))
                c.execute("UPDATE ai_review_turns SET status=?,proposal=? WHERE id=?",('proposed' if result['kind']=='proposal' else result['kind'],json.dumps(result),tid))
                return {'turn':next(t for t in turns(c,cid) if t['id']==tid)}
        finally: c.close()
    except Exception:
        # No SDK exception strings, feedback, connection strings or prompts in logs.
        c=get_connection()
        try:
            with c: c.execute("UPDATE ai_review_turns SET status='failed' WHERE id=? AND status='generating'",(tid,))
        finally: c.close()
        abort(502,description='AI revision could not be generated or validated. Feedback is saved. Retry with the same feedback; saved test cases are unchanged.')


def decide(rid,cid,tid,data):
    from app import get_connection
    from services.workflow_service import snapshot
    from services.requirement_helpers import _get_requirement_detail
    if not isinstance(data,dict) or data.get('action') not in ('accept','reject'): abort(400)
    action=data['action']; c=get_connection()
    try:
        with c:
            session=conversation(c,rid,cid); req=lock_context(c,rid)
            if action=='accept':
                permission(c,accept=True)
                if req['created_by_user_id']==g.current_user['id']: abort(403,description='Authors cannot accept verification cases for their own requirement.')
            row=c.execute('SELECT * FROM ai_review_turns WHERE id=? AND conversation_id=?',(tid,cid)).fetchone()
            if not row: abort(404)
            target='accepted' if action=='accept' else 'rejected'
            if row['status']==target: return {'status':target,'requirement':_get_requirement_detail(c,rid)}
            if row['status']!='proposed': abort(409,description='Only the latest undecided proposal can be accepted or rejected.')
            if c.execute("SELECT 1 FROM ai_review_turns WHERE conversation_id=? AND status='generating' AND started_at>?",(cid,int(time.time())-60)).fetchone():
                abort(409,description='Wait for the current revision request to finish before deciding a proposal.')
            if action=='accept':
                base=json.loads(row['base_snapshot'])
                current=source(c,rid,json.loads(session['case_ids']))
                if current!=base: abort(409,description='Saved requirement or test cases changed after generation. Request another revision before accepting.')
                proposal=validate_proposal(c,rid,json.loads(row['proposal']),base)
                snapshot(c,rid,'before_ai_revision_acceptance')
                for change in proposal['changes']:
                    v=change['content']; sid=change['case_id']; archive=change['operation']=='archive'
                    values=(v['title'],v['category'],json.dumps(v['preconditions']),v['test_data'],json.dumps(v['test_steps']),v['expected_result'],v['test_type'],v['priority'],json.dumps(v['criterion_codes']),v['clarification_notes'],req['content_revision'])
                    if change['operation']=='new':
                        sql="INSERT INTO test_scenarios(title,category,preconditions,test_data,test_steps,expected_result,test_type,priority,criterion_codes,clarification_notes,requirement_revision,requirement_id,scenario_code,created_by_user_id,review_status,source,needs_confirmation) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Pending Review','ai_suggestion',1)"
                        if c.dialect=='postgres': sql+=' RETURNING id'
                        cursor=c.execute(sql,(*values,rid,'TC-'+uuid.uuid4().hex,g.current_user['id']))
                        sid=cursor.fetchone()[0] if c.dialect=='postgres' else cursor.lastrowid
                    else:
                        old=c.execute('SELECT * FROM test_scenarios WHERE id=?',(sid,)).fetchone(); ensure_version(c,old)
                        c.execute("UPDATE test_scenarios SET title=?,category=?,preconditions=?,test_data=?,test_steps=?,expected_result=?,test_type=?,priority=?,criterion_codes=?,clarification_notes=?,requirement_revision=?,case_revision=case_revision+1,review_status='Pending Review',review_notes='',needs_confirmation=1,source='ai_suggestion',archived=? WHERE id=?",(*values,int(archive),sid))
                    ensure_version(c,c.execute('SELECT * FROM test_scenarios WHERE id=?',(sid,)).fetchone(),g.current_user['id'])
                    change['saved_case_id']=sid
                c.execute('UPDATE ai_review_turns SET proposal=? WHERE id=?',(json.dumps(proposal),tid))
                c.execute("UPDATE requirements SET revision=revision+1,updated_at=?,review_status=CASE WHEN review_status IN ('Ready for Review','Pending','Approved') THEN 'In Review' ELSE review_status END WHERE id=?",(_utc_timestamp(),rid))
                snapshot(c,rid,'ai_revision_accepted_pending_review')
            c.execute('UPDATE ai_review_turns SET status=?,decision_actor_id=?,decided_at=? WHERE id=?',(target,g.current_user['id'],_utc_timestamp(),tid))
            return {'status':target,'requirement':_get_requirement_detail(c,rid)}
    finally: c.close()
