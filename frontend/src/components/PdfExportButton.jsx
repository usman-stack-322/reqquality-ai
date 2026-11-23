import { apiFetch as fetch } from '../api.js';
import React, { useRef, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { buttonSecondaryClass } from './ui';

export default function PdfExportButton({ url, filename, children = 'Export PDF', format = 'PDF' }) {
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
        throw new Error(data.error || `Unable to export ${format}. Please try again.`);
      }
      const expectedType = format === 'CSV' ? 'text/csv' : 'application/pdf';
      if (!response.headers.get('content-type')?.includes(expectedType)) {
        throw new Error(`The server did not return ${format}. Please sign in and try again.`);
      }
      const blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
    } catch (failure) {
      setError(failure.message || `Unable to export ${format}. Please try again.`);
    } finally {
      link?.remove();
      if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      locked.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="pdf-export-control inline-flex flex-col items-start gap-1">
      <button
        className={`${buttonSecondaryClass} export-button`}
        type="button"
        disabled={busy}
        aria-busy={busy}
        onClick={download}
      >
        {busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <Download className="size-3.5" aria-hidden="true" />}
        {busy ? `Downloading ${format}…` : children}
      </button>
      {busy && (
        <span className="pdf-export-status text-[11px] text-muted" role="status">
          Preparing saved data…
        </span>
      )}
      {error && (
        <p className="error pdf-export-error text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
