import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { join, relative } from 'node:path';

import { htmlFiles } from '../scripts/site/html.mjs';

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'htmlfiles-'));
  mkdirSync(join(root, 'talks', 'deep'), { recursive: true });
  mkdirSync(join(root, '.well-known'), { recursive: true });
  for (const name of [
    'index.html',
    '404.html',
    'talks/2019-01-01_SEEFELD.html',
    'talks/deep/nested.html',
    '.well-known/security.txt',
    'styles.css',
    'talks/notes.txt',
  ]) {
    writeFileSync(join(root, name), '');
  }
  return root;
}

test('finds every .html file at any depth and nothing else', (t) => {
  const root = fixture();
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const found = htmlFiles(root).map((p) => relative(root, p)).sort();

  assert.deepEqual(found, [
    '404.html',
    'index.html',
    join('talks', '2019-01-01_SEEFELD.html'),
    join('talks', 'deep', 'nested.html'),
  ]);
});
