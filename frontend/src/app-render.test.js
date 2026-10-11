import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join, resolve, sep } from 'node:path';
import React from 'react';
import { renderToString } from 'react-dom/server';

test('public pages render synchronously and protected routes remain gated', async () => {
  // Compile JSX locally; this check does not open a browser or call the real API.
  const directory = await mkdtemp(new URL('../.render-test-', import.meta.url));
  try {
    const output = await build({ entryPoints: [fileURLToPath(new URL('./App.jsx', import.meta.url))], bundle: true,
      write: false, platform: 'node', format: 'esm', packages: 'external', loader: { '.css': 'empty' } });
    const filename = pathToFileURL(join(directory, 'App.mjs'));
    await writeFile(filename, output.outputFiles[0].contents);
    const { default: App } = await import(filename.href);
    globalThis.fetch = () => { throw new Error('Render must not wait on the API'); };
    for (const [hash, expected] of [['#home', 'Bring clarity to requirements'], ['#login', 'login-email'], ['#dashboard', 'Loading your secure workspace'], ['#requirements', 'Loading your secure workspace'], ['#admin', 'Loading your secure workspace']]) {
      globalThis.window = { location: { hash, pathname: '/', search: '' } };
      const html = renderToString(React.createElement(App));
      assert.ok(html.includes(expected), hash);
      assert.ok(!html.includes('Checking your session'), hash);
      if (!['#home', '#login'].includes(hash)) assert.ok(!html.includes('Export CSV'), hash);
    }
    globalThis.window.location.hash = '#home';
    const homepage = renderToString(React.createElement(App));
    assert.ok(homepage.includes('SQA Admin'));
    assert.ok(homepage.includes('does not execute tests'));
    assert.ok(!homepage.includes('verified quality'));
    const steps = ['Requirement Input', 'Hybrid Analysis', 'Refinement', 'Acceptance Criteria', 'Risk / Priority', 'Test Scenarios', 'Traceability', 'SQA Review', 'Dashboard / Reports'];
    const workflow = homepage.slice(homepage.indexOf('<ol class="workflow-steps"'));
    let position = -1;
    for (const step of steps) {
      const next = workflow.indexOf(`<span class="workflow-step-label">${step}</span>`);
      assert.ok(next > position, step);
      position = next;
    }
  } finally {
    assert.ok(resolve(directory).startsWith(resolve(dirname(fileURLToPath(import.meta.url)), '..') + sep));
    await rm(directory, { recursive: true, force: true });
  }
});

test('primary palette maintains WCAG AA text contrast', () => {
  const luminance = hex => {
    const channels = hex.match(/\w\w/g).map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  };
  for (const [foreground, background] of [['ffffff', '0f172a'], ['ffffff', '0f766e'], ['1e293b', 'ffffff'], ['475569', 'f8fafc']]) {
    const a = luminance(foreground), b = luminance(background);
    assert.ok((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 4.5);
  }
});
