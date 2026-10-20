import React, { useEffect, useState } from 'react';
import { apiFetch } from '../api.js';

export default function ProjectContext({ editable = false }) {
  const [project, setProject] = useState(null);
  const [context, setContext] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch('/api/project', { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Project unavailable');
      if (!controller.signal.aborted) { setProject(data.project); setContext(data.project.context); }
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);
  async function save() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const response = await apiFetch('/api/project', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ context, revision: project.revision }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save context.');
      setProject(data.project); setContext(data.project.context);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <section className="card"><h2>Project context</h2>
    {project && <><p>{project.name} · Context revision {project.revision}</p>{editable ? <><label>Supplied facts, actors, scope and unresolved decisions<textarea rows={5} maxLength={20000} value={context} disabled={busy} onChange={e => setContext(e.target.value)} /></label><button type="button" disabled={busy} onClick={save}>Save project context</button></> : <p>{project.context || 'No context supplied. Unknown business values require clarification.'}</p>}</>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
