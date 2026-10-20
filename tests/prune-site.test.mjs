import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { pruneSiteToPdfs } from "../scripts/site/prune-site.mjs";

/** A throwaway `_site/` shaped like the one Quarto leaves behind. */
function makeSite() {
  const root = mkdtempSync(join(tmpdir(), "prune-site-"));
  writeFileSync(join(root, "cv.pdf"), "cv");
  writeFileSync(join(root, "cv-academic.pdf"), "cv-academic");
  writeFileSync(join(root, "index.html"), "stale html");
  writeFileSync(join(root, "search.json"), "{}");
  mkdirSync(join(root, "posts"));
  writeFileSync(join(root, "posts", "2026-01-20_chem_flow.pdf"), "post pdf");
  writeFileSync(join(root, "posts", "2026-01-20_chem_flow.html"), "post html");
  mkdirSync(join(root, "site_libs"));
  writeFileSync(join(root, "site_libs", "quarto.js"), "vendored");
  return root;
}

test("pruneSiteToPdfs keeps exactly the PDFs the pipeline consumes", () => {
  const root = makeSite();
  try {
    pruneSiteToPdfs(root);
    assert.deepEqual(readdirSync(root).sort(), [
      "cv-academic.pdf",
      "cv.pdf",
      "posts",
    ]);
    assert.deepEqual(readdirSync(join(root, "posts")), [
      "2026-01-20_chem_flow.pdf",
    ]);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("pruneSiteToPdfs reports how many top-level entries it removed", () => {
  const root = makeSite();
  try {
    // index.html, search.json, site_libs/, and posts/*.html -> 4.
    assert.equal(pruneSiteToPdfs(root), 4);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("pruneSiteToPdfs is a no-op when there is no _site directory", () => {
  assert.equal(pruneSiteToPdfs(join(tmpdir(), "definitely-not-here-12345")), 0);
});
