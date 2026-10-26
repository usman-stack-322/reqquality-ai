import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/appearance.js', import.meta.url), 'utf8');
function browser({ saved, dark = false, storageDenied = false } = {}) {
  const events = new Map(), mediaEvents = new Map();
  const media = { matches: dark, addEventListener: (name, fn) => mediaEvents.set(name, fn) };
  const root = { dataset: {}, style: {} };
  let stored = saved;
  const storage = { getItem: () => { if (storageDenied) throw Error('blocked'); return stored; }, setItem: (_, value) => { if (storageDenied) throw Error('blocked'); stored = value; } };
  const window = { matchMedia: () => media, addEventListener: (name, fn) => events.set(name, fn), dispatchEvent() {} };
  vm.runInNewContext(source, { window, document: { documentElement: root, querySelector: () => null }, localStorage: storage, Event: class {} });
  return { root, window, stored: () => stored, os(value) { media.matches = value; mediaEvents.get('change')(); }, storage(value, key = 'reqquality-appearance') { events.get('storage')({ key, newValue: value }); } };
}

test('first paint defaults to System; OS changes follow only System', () => {
  const b = browser({ dark: true });
  assert.equal(b.root.dataset.theme, 'dark');
  assert.equal(b.root.dataset.appearance, 'system');
  b.os(false); assert.equal(b.root.dataset.theme, 'light');
  b.window.reqQualityAppearance.set('dark');
  b.os(false); assert.equal(b.root.dataset.theme, 'dark');
  assert.equal(b.stored(), 'dark');
  assert.equal(browser({ saved: b.stored() }).root.dataset.theme, 'dark');
});

test('invalid storage and denied storage remain usable; changing theme needs no reload', () => {
  for (const settings of [{ saved: 'corrupt', dark: true }, { storageDenied: true, dark: true }]) {
    const b = browser(settings);
    assert.equal(b.root.dataset.theme, 'dark');
    b.window.reqQualityAppearance.set('light');
    assert.equal(b.root.dataset.theme, 'light');
    b.window.reqQualityAppearance.set('invalid');
    assert.equal(b.root.dataset.theme, 'light');
    b.storage('dark'); assert.equal(b.root.dataset.theme, 'dark');
    b.storage('invalid'); assert.equal(b.root.dataset.appearance, 'system');
    b.storage(null, null); assert.equal(b.root.dataset.appearance, 'system');
  }
});

test('appearance boot runs before the application and stylesheet requests', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  assert.ok(html.indexOf('/appearance.js') < html.indexOf('/src/main.jsx'));
  assert.ok(!html.includes('type="module" src="/appearance.js"'));
});

test('shared light/dark token text pairs meet AA contrast', () => {
  const css = readFileSync(new URL('./theme.css', import.meta.url), 'utf8');
  const palettes = [...css.matchAll(/(?:^:root|html\[data-theme="dark"\])\s*\{([^}]+)\}/gm)];
  const luminance = hex => {
    const v = hex.slice(1).match(/../g).map(n => parseInt(n, 16) / 255).map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
    return v[0] * .2126 + v[1] * .7152 + v[2] * .0722;
  };
  const base = {};
  for (const [, block] of palettes) {
    Object.assign(base, Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[\da-f]{6})/gi)].map(m => [m[1], m[2]])));
    for (const [fg, bg] of [['ink', 'surface'], ['muted', 'surface'], ['accent', 'surface'], ['on-accent', 'accent-strong'], ['success', 'success-tint'], ['warning', 'warning-tint'], ['danger', 'danger-tint']]) {
      const a = luminance(base[fg]), b = luminance(base[bg]);
      assert.ok((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 4.5, `${fg} on ${bg}: ${base[fg]}/${base[bg]}`);
    }
  }
  assert.equal(palettes.length, 2);
});
