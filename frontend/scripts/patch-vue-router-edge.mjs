// Backport https://github.com/vuejs/router/commit/17b58611 (MIT).
// Our browser build and Node ESM entry both use dist/vue-router.mjs.
import { readFile, writeFile } from 'node:fs/promises';

const root = new URL('../node_modules/vue-router/', import.meta.url);
const metadata = JSON.parse(await readFile(new URL('package.json', root), 'utf8'));
if (metadata.version !== '4.6.4') {
  throw new Error('Review the Edge history backport before changing vue-router 4.6.4');
}
const file = new URL('dist/vue-router.mjs', root);
const source = await readFile(file, 'utf8');
const before = [
  '\tfunction beforeUnloadListener() {',
  '\t\tif (document.visibilityState === "hidden") {',
  '\t\t\tconst { history: history$1 } = window;',
  '\t\t\tif (!history$1.state) return;',
  '\t\t\thistory$1.replaceState(assign({}, history$1.state, { scroll: computeScrollPosition() }), "");',
  '\t\t}',
  '\t}',
].join('\n');
const after = [
  '\tfunction beforeUnloadListener() {',
  '\t\tconst { history: history$1 } = window;',
  '\t\tif (!history$1.state) return;',
  '\t\thistory$1.replaceState(assign({}, history$1.state, { scroll: computeScrollPosition() }), "");',
  '\t}',
].join('\n');
const registration = '\tdocument.addEventListener("visibilitychange", beforeUnloadListener);\n';
const removal = '\t\tdocument.removeEventListener("visibilitychange", beforeUnloadListener);\n';
const once = (text, part) => text.split(part).length === 2;
if (source.includes(after) && !source.includes(registration) && !source.includes(removal)) {
  console.log('vue-router Edge history backport already applied');
} else {
  if (![before, registration, removal].every(part => once(source, part))) {
    throw new Error('Unexpected vue-router source; refusing to apply a partial Edge history backport');
  }
  await writeFile(file, source.replace(before, after).replace(registration, '').replace(removal, ''));
  console.log('Applied vue-router Edge history backport (upstream #2704)');
}
