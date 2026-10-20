"""Cross-worker leases and short-lived per-user result receipts, never shared users."""
import hashlib
import json
import time
from flask import g
from app import get_connection
from analyzers.llm_analyzer import ANALYSIS_VERSION
from analyzers.llm_analyzer import generation_configuration


def _now():
    return int(time.time())


def run_analysis(data, generate):
    key = hashlib.sha256(json.dumps({'version': ANALYSIS_VERSION, 'configuration': generation_configuration(), 'input': data}, sort_keys=True).encode()).hexdigest()
    uid, now = g.current_user['id'], _now()
    c = get_connection()
    try:
        with c:
            c.execute('DELETE FROM analysis_requests WHERE expires_at<?', (now,))
            cursor = c.execute('INSERT INTO analysis_requests(user_id,input_hash,expires_at) VALUES(?,?,?) ON CONFLICT(user_id,input_hash) DO NOTHING', (uid,key,now+90))
            claimed = cursor.rowcount == 1
            if not claimed:
                row = c.execute('SELECT result FROM analysis_requests WHERE user_id=? AND input_hash=?',(uid,key)).fetchone()
                if row and row['result']:
                    return json.loads(row['result'])
                return {'status':'failed','code':'analysis_in_progress','retryable':True,'error':'This analysis is already running. Wait a moment before retrying.'}
    finally:
        c.close()
    result = None
    try:
        result = generate()
        return result
    finally:
        c = get_connection()
        try:
            with c:
                if result and result.get('status') == 'completed':
                    c.execute('UPDATE analysis_requests SET result=?,expires_at=? WHERE user_id=? AND input_hash=? AND expires_at=? AND result IS NULL',(json.dumps(result),_now()+120,uid,key,now+90))
                else:
                    c.execute('DELETE FROM analysis_requests WHERE user_id=? AND input_hash=? AND expires_at=? AND result IS NULL',(uid,key,now+90))
        finally:
            c.close()
