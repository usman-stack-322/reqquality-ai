import React, { useEffect, useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';

const OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
];

export default function ThemeSelector() {
  const [value, setValue] = useState(() => (typeof window !== 'undefined' ? window.reqQualityAppearance?.get() || 'system' : 'system'));
  const [resolved, setResolved] = useState(() => (typeof document !== 'undefined' ? document.documentElement?.dataset?.theme || 'light' : 'light'));

  useEffect(() => {
    const update = () => {
      setValue(window.reqQualityAppearance?.get() || 'system');
      setResolved(document.documentElement?.dataset?.theme || 'light');
    };
    window.addEventListener('appearancechange', update);
    return () => window.removeEventListener('appearancechange', update);
  }, []);

  return (
    <div
      className="appearance-selector inline-flex items-center rounded-lg border border-line bg-surface-alt p-0.5"
      role="group"
      aria-label="Appearance theme"
    >
      {OPTIONS.map(({ value: optionValue, label, Icon }) => {
        const active = value === optionValue;
        const accessibleLabel = optionValue === 'system' ? `${label} (${resolved})` : label;
        return (
          <button
            key={optionValue}
            type="button"
            aria-pressed={active}
            aria-label={accessibleLabel}
            title={accessibleLabel}
            onClick={() => window.reqQualityAppearance?.set(optionValue)}
            className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
              active
                ? 'bg-surface text-ink shadow-xs border border-line'
                : 'text-muted hover:text-ink border border-transparent'
            }`}
          >
            <Icon className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
