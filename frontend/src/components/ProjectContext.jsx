import React, { useEffect, useState } from 'react';
import { apiFetch } from '../api.js';
import { FolderKanban } from 'lucide-react';
import { buttonPrimaryClass, inputClass } from './ui';

export default function ProjectContext({ editable = false }) {
  const [project, setProject] = useState(null);
  const [context, setContext] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch('/api/project', { signal: controller.signal })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Project unavailable');
        if (!controller.signal.aborted) {
          setProject(data.project);
          setContext(data.project.context);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, []);

  async function save() {
    if (busy || !project) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const response = await apiFetch('/api/project', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context, revision: project.revision }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save context.');
      setProject(data.project);
      setContext(data.project.context);
      setNotice('Project context saved.');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex size-8 items-center justify-center rounded-lg bg-accent-tint text-accent">
            <FolderKanban className="size-4" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-ink">Project context</h2>
            {project && (
              <p className="text-xs text-muted">
                {project.name} · Context revision {project.revision}
              </p>
            )}
          </div>
        </div>
      </div>

      {project &&
        (editable ? (
          <div className="space-y-3">
            <label className="block space-y-1.5 text-xs font-medium text-muted">
              <span>Supplied facts, actors, scope and unresolved decisions</span>
              <textarea
                className={inputClass}
                rows={4}
                maxLength={20000}
                value={context}
                disabled={busy}
                onChange={(e) => setContext(e.target.value)}
              />
            </label>
            <div className="flex items-center gap-3">
              <button type="button" className={buttonPrimaryClass} disabled={busy} onClick={save}>
                {busy ? 'Saving…' : 'Save project context'}
              </button>
              {notice && <span className="text-xs text-success" role="status">{notice}</span>}
            </div>
          </div>
        ) : (
          <p className="rounded-lg border border-line bg-surface-alt/60 p-3 text-xs leading-relaxed text-ink">
            {project.context || 'No context supplied. Unknown business values require clarification.'}
          </p>
        ))}

      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
