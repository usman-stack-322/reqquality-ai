// Run synchronously before CSS and React so System/Dark never paint light first.
(() => {
  const key = 'reqquality-appearance';
  const valid = value => ['light', 'dark', 'system'].includes(value);
  const media = window.matchMedia?.('(prefers-color-scheme: dark)');
  let preference = 'system';
  try { const saved = localStorage.getItem(key); if (valid(saved)) preference = saved; } catch {}
  function apply() {
    const theme = preference === 'system' ? (media?.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.appearance = preference;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#111624' : '#f5f6fa');
    window.dispatchEvent(new Event('appearancechange'));
  }
  window.reqQualityAppearance = {
    get: () => preference,
    set(value) {
      if (!valid(value)) return;
      preference = value;
      try { localStorage.setItem(key, value); } catch {}
      apply();
    },
  };
  media?.addEventListener?.('change', () => { if (preference === 'system') apply(); });
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : 'system';
    apply();
  });
  apply();
})();
