import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, view] = await Promise.all([
  readFile(new URL('../src/pages/RateioPage.ts', import.meta.url), 'utf8'),
  readFile(new URL('../src/pages/rateio/RateioFormularioView.ts', import.meta.url), 'utf8')
]);

assert.match(view, /refresh:\s*\(\)\s*=>\s*void/);
assert.match(view, /return \{ element, selectPlant, refresh: render \}/);
assert.match(view, /rateio-plant-list/);
assert.match(view, /rateio-plant-row/);
assert.match(page, /formulario\.refresh\(\)/);
console.log('rateio formulario refresh check: ok');
