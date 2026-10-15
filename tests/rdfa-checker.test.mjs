import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const checker = join(here, '..', 'scripts', 'site', 'check-rdfa.mjs');

function run(files) {
  const dir = mkdtempSync(join(tmpdir(), 'rdfa-'));
  try {
    for (const [name, html] of Object.entries(files)) {
      const target = join(dir, name);
      mkdirSync(dirname(target), { recursive: true });
      writeFileSync(target, html);
    }
    try {
      const stdout = execFileSync(process.execPath, [checker, dir], { encoding: 'utf-8' });
      return { status: 0, stdout };
    } catch (error) {
      return { status: error.status, stdout: error.stdout };
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('absolute IRIs in RDFa attributes are not mistaken for prefixed terms', () => {
  const { status, stdout } = run({
    'a.html':
      '<!doctype html><html><body>' +
      '<div prefix="wd: http://www.wikidata.org/entity/">' +
      '<span typeof="https://schema.org/Person">Ada</span>' +
      '<a rel="https://schema.org/sameAs" href="/x">y</a>' +
      '</div></body></html>',
  });
  assert.equal(status, 0, `expected no problems, got:\n${stdout}`);
});

test('the IRI inside a prefix declaration is not parsed as a prefix name', () => {
  const { status, stdout } = run({
    'a.html':
      '<div prefix="wd: http://www.wikidata.org/entity/ wdno: http://www.wikidata.org/prop/novalue/">' +
      '<span about="wd:Q123">z</span></div>',
  });
  assert.equal(status, 0, `expected no problems, got:\n${stdout}`);
});

test('a genuinely undeclared prefix is still reported', () => {
  const { status, stdout } = run({
    'a.html': '<div prefix="wd: http://www.wikidata.org/entity/"><span property="cito:cites">x</span></div>',
  });
  assert.equal(status, 1, 'expected the checker to fail');
  assert.match(stdout, /uses undeclared prefix "cito:"/);
});
