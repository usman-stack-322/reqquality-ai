import { apiFetch as fetch } from '../api.js';
import React, { useRef, useState } from 'react';

export default function PdfExportButton({ url, filename, children = 'Export PDF' }) {
  const locked = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function download() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError('');
    let objectUrl;
    let link;
    try {
      const response = await fetch(url, { credentials: 'include' });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Unable to export PDF. Please try again.');
      }
      if (!response.headers.get('content-type')?.includes('application/pdf')) {
        throw new Error('The server did not return a PDF. Please sign in and try again.');
      }
      const blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
    } catch (failure) {
      setError(failure.message || 'Unable to export PDF. Please try again.');
    } finally {
      link?.remove();
      if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      locked.current = false;
      setBusy(false);
    }
  }

  return <div className="pdf-export-control">
    <button className="button export-button" type="button" disabled={busy} aria-busy={busy} onClick={download}>
      {busy ? 'Exporting PDF...' : children}
    </button>
    {busy && <span className="pdf-export-status" role="status">Preparing your report...</span>}
    {error && <p className="error pdf-export-error" role="alert">{error}</p>}
  </div>;
}
