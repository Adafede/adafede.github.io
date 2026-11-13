import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scripts = join(dirname(fileURLToPath(import.meta.url)), "..", "scripts", "site");

function run(checker, dir) {
  return spawnSync(process.execPath, [join(scripts, checker), dir], {
    encoding: "utf-8",
  });
}

for (const checker of ["check-links.mjs", "check-rdfa.mjs", "check-document.mjs"]) {
  test(`${checker} fails on a directory with no pages`, () => {
    const result = run(checker, mkdtempSync(join(tmpdir(), "empty-site-")));
    assert.equal(result.status, 2);
    assert.match(result.stderr, /no \.html files/);
  });

  test(`${checker} fails with a message when the directory is missing`, () => {
    const result = run(checker, join(tmpdir(), "no-such-site-dir-for-test"));
    assert.equal(result.status, 2);
    assert.match(result.stderr, /no such directory/);
    assert.doesNotMatch(result.stderr, /ENOENT/);
  });
}

test("check-links reports a malformed percent-escape as a dead link", () => {
  const dir = mkdtempSync(join(tmpdir(), "bad-escape-site-"));
  writeFileSync(
    join(dir, "index.html"),
    '<a href="/x%zz.html">x</a><a href="/index.html">home</a>',
  );
  const result = run("check-links.mjs", dir);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /1 dead internal link/);
  assert.match(result.stdout, /\/x%zz\.html/);
});
