import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, copyFile, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { spawnSync } from 'node:child_process';

// Use the actual installed router with a local browser/history substitute.
const browser = new EventTarget();
const documentStub = new EventTarget();
documentStub.createElement = () => ({});
documentStub.querySelector = () => null;
documentStub.visibilityState = 'visible';
let currentUrl = new URL('http://localhost/');
const entries = [{ url: currentUrl.href, state: null }];
let position = 0;
let writes = 0;
const historyStub = {
  get state() { return entries[position].state; },
  get length() { return entries.length; },
  replaceState(state, _title, url) {
    writes++;
    currentUrl = new URL(url || currentUrl.href, currentUrl);
    entries[position] = { url: currentUrl.href, state };
  },
  pushState(state, _title, url) {
    writes++;
    currentUrl = new URL(url, currentUrl);
    entries.splice(++position, entries.length, { url: currentUrl.href, state });
  },
  go(delta) {
    position += delta;
    currentUrl = new URL(entries[position].url);
    const event = new Event('popstate');
    Object.defineProperty(event, 'state', { value: historyStub.state });
    browser.dispatchEvent(event);
  },
};
Object.defineProperty(browser, 'location', { get: () => currentUrl });
browser.history = historyStub;
browser.scrollX = 0;
browser.scrollY = 0;
globalThis.window = browser;
globalThis.document = documentStub;
Object.defineProperty(globalThis, 'location', { configurable: true, get: () => currentUrl });
globalThis.history = historyStub;
const { createWebHistory } = await import('vue-router');

test('hiding a page does not write history or reactivate a minimized Edge window', () => {
  const routerHistory = createWebHistory('/');
  const before = writes;
  documentStub.visibilityState = 'hidden';
  documentStub.dispatchEvent(new Event('visibilitychange'));
  assert.equal(writes, before);
  routerHistory.destroy();
});

test('push, replace, back and forward retain route state', () => {
  documentStub.visibilityState = 'visible';
  const routerHistory = createWebHistory('/');
  routerHistory.push('/first', { marker: 'first' });
  routerHistory.push('/second', { marker: 'second' });
  routerHistory.replace('/second-edited', { marker: 'edited' });
  assert.equal(routerHistory.location, '/second-edited');
  assert.equal(historyStub.state.marker, 'edited');
  const navigations = [];
  routerHistory.listen((to, from) => navigations.push({ to, from }));
  routerHistory.go(-1);
  assert.equal(routerHistory.location, '/first');
  assert.equal(historyStub.state.marker, 'first');
  routerHistory.go(1);
  assert.equal(routerHistory.location, '/second-edited');
  assert.equal(historyStub.state.marker, 'edited');
  assert.deepEqual(navigations, [
    { to: '/first', from: '/second-edited' },
    { to: '/second-edited', from: '/first' },
  ]);
  routerHistory.destroy();
});

test('pagehide persists scroll without losing state and destroy removes its handler', () => {
  const routerHistory = createWebHistory('/');
  routerHistory.replace('/saved', { marker: 'retain' });
  browser.scrollX = 12;
  browser.scrollY = 345;
  documentStub.visibilityState = 'visible';
  browser.dispatchEvent(new Event('pagehide'));
  assert.deepEqual(historyStub.state.scroll, { left: 12, top: 345 });
  assert.equal(historyStub.state.marker, 'retain');
  routerHistory.destroy();
  const before = writes;
  browser.dispatchEvent(new Event('pagehide'));
  assert.equal(writes, before);
});

for (const version of ['4.6.4', '4.6.99']) {
  test(`a changed router ${version} source is rejected without modifying files`, async () => {
    const fixture = await mkdtemp(join(tmpdir(), 'teamproject-router-patch-'));
    try {
      await mkdir(join(fixture, 'scripts'));
      const packageRoot = join(fixture, 'node_modules', 'vue-router');
      await mkdir(join(packageRoot, 'dist'), { recursive: true });
      const sourceFile = join(packageRoot, 'dist', 'vue-router.mjs');
      await writeFile(join(packageRoot, 'package.json'), JSON.stringify({ version }));
      await writeFile(sourceFile, 'unexpected dependency source');
      const script = join(fixture, 'scripts', 'patch-vue-router-edge.mjs');
      await copyFile(new URL('../scripts/patch-vue-router-edge.mjs', import.meta.url), script);
      const result = spawnSync(process.execPath, [script], { encoding: 'utf8' });
      assert.equal(result.status, 1);
      assert.match(result.stderr, version === '4.6.4' ? /Unexpected vue-router source/ : /Review the Edge history backport/);
      assert.equal(await readFile(sourceFile, 'utf8'), 'unexpected dependency source');
    } finally {
      const absoluteFixture = resolve(fixture);
      assert.ok(absoluteFixture.startsWith(resolve(tmpdir()) + sep));
      assert.ok(absoluteFixture.split(sep).at(-1).startsWith('teamproject-router-patch-'));
      await rm(absoluteFixture, { recursive: true, force: true });
    }
  });
}
