import React, { useEffect, useState } from 'react';

export default function ThemeSelector() {
  const [value, setValue] = useState(() => typeof window !== 'undefined' ? window.reqQualityAppearance?.get() || 'system' : 'system');
  useEffect(() => {
    const update = () => setValue(window.reqQualityAppearance?.get() || 'system');
    window.addEventListener('appearancechange', update);
    return () => window.removeEventListener('appearancechange', update);
  }, []);
  return <label className="appearance-selector"><span>Theme</span><select aria-label="Appearance" value={value} onChange={event => window.reqQualityAppearance?.set(event.target.value)}>
    <option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option>
  </select></label>;
}
