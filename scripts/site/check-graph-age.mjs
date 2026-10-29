/**
 * Report how far the knowledge graph has drifted from the working tree.
 *
 * `graphify update` stamps every file it indexed into
 * `graphify-out/manifest.json` with an `mtime` and a `seen` timestamp. If a
 * file's mtime has moved past `seen`, the graph has not been rebuilt since
 * that file changed, so anything the graph says about it may be wrong.
 *
 * This is a freshness report, not a hard failure: the graph covers the Python
 * layer well and the template/CSS/content layers not at all, so it is never
 * required to be perfect. It exits nonzero only when the graph is missing or
 * so stale that treating it as current would be misleading.
 *
 * Run: node scripts/site/check-graph-age.mjs            # human-readable report
 *      node scripts/site/check-graph-age.mjs --strict   # nonzero if any file is stale
 */
import { readFileSync, statSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MANIFEST = join(ROOT, "graphify-out", "manifest.json");

/** Fraction of indexed files that have changed since the graph was built. */
const STALE_RATIO = 0.5;

const strict = process.argv.includes("--strict");

if (!existsSync(MANIFEST)) {
  console.log(
    "  no graph (graphify-out/manifest.json absent).\n" +
      "  Build one with `bun run graph:update`, or ignore this file — the graph is optional.",
  );
  process.exit(0);
}

/** @returns {{total: number, stale: string[], missing: string[]}} */
function measureStaleness() {
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf-8"));
  const stale = [];
  const missing = [];
  let total = 0;

  for (const [file, entry] of Object.entries(manifest)) {
    total += 1;
    const path = join(ROOT, file);
    if (!existsSync(path)) {
      missing.push(file);
      continue;
    }
    if (statSync(path).mtimeMs / 1000 > entry.seen) stale.push(file);
  }
  return { total, stale, missing };
}

const { total, stale, missing } = measureStaleness();

if (total === 0) {
  console.log("  graph manifest is empty; nothing indexed.");
  process.exit(0);
}

const label = relative(ROOT, MANIFEST);
console.log(`  graph: ${total} indexed file(s) in ${label}`);
console.log(`  stale since the last build: ${stale.length}`);

if (stale.length) {
  for (const file of stale.slice(0, 5)) console.log(`    - ${file}`);
  if (stale.length > 5) console.log(`    … and ${stale.length - 5} more`);
  console.log("  Rebuild with `bun run graph:update`.");
}
if (missing.length) {
  console.log(`  indexed but no longer on disk: ${missing.length}`);
  for (const file of missing.slice(0, 5)) console.log(`    - ${file}`);
  if (missing.length > 5) console.log(`    … and ${missing.length - 5} more`);
}

const tooStale = stale.length / total >= STALE_RATIO;
if (tooStale) {
  const msg = `  graph is ${Math.round((stale.length / total) * 100)}% stale; ` +
    "treat graph answers as unreliable until it is rebuilt.";
  if (strict) {
    console.error(msg);
    process.exit(1);
  }
  console.log(msg);
}
