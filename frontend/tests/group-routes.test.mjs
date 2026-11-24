import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const routerSource = await readFile(
  join(here, '..', 'src', 'router', 'index.ts'),
  'utf8'
);

test('group detail route is registered and imported', () => {
  assert.match(
    routerSource,
    /import GroupDetail from "\.\.\/views\/GroupDetail\.vue"/,
    'GroupDetail view should be imported'
  );
  assert.match(routerSource, /path:\s*"groups\/:id"/, 'groups/:id path should be registered');
  assert.match(routerSource, /name:\s*"group-detail"/, 'route should be named group-detail');
});

test('group detail route lives under the protected workspace layout', () => {
  const layoutIdx = routerSource.indexOf('WorkspaceLayout');
  const routeIdx = routerSource.indexOf('groups/:id');
  assert.notEqual(layoutIdx, -1);
  assert.notEqual(routeIdx, -1);
  assert.ok(
    routeIdx > layoutIdx,
    'group detail route should be declared within the workspace layout children block'
  );
});

test('group detail route is deep-linkable (uses history mode, not hash)', () => {
  assert.match(routerSource, /createWebHistory\(/, 'router should use web history for deep links');
});
