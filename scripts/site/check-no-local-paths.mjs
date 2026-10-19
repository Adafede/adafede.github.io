/**
 * Fail if any tracked file contains an absolute path into a user's home
 * directory.
 *
 * These leak the author's local username, break on every other machine, and
 * usually mean a command was pasted from a shell prompt rather than written
 * for the repo. Three platforms, one rule:
 *
 *   /Users/<name>/…      macOS
 *   C:\Users\<name>\…    Windows
 *   /home/<name>/…       Linux
 *
 * Deliberately narrow, and verified to produce zero matches across the whole
 * tracked tree before it was added. `localhost`, `127.0.0.1` and
 * `example.com/home/x` are all allowed: the first two are how the dev server
 * is addressed, and the third is a URL path, not a filesystem path.
 *
 * Run: node scripts/site/check-no-local-paths.mjs
 * Exits nonzero on any hit.
 */
import { readFileSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const PATTERNS = [
  { name: "macOS home", re: /\/Users\/[A-Za-z0-9._-]+/g },
  { name: "Windows home", re: /[A-Za-z]:\\+Users\\+[A-Za-z0-9._-]+/g },
  // The lookbehind keeps a URL path like example.com/home/john/ out of scope.
  { name: "Linux home", re: /(?<![\w.])(\/home\/[A-Za-z0-9._-]+\/)/g },
];

/** `git ls-files -z` so paths with spaces survive the round trip. */
const files = execFileSync("git", ["ls-files", "-z"], { cwd: ROOT, encoding: "utf-8" })
  .split("\0")
  .filter(Boolean);

const findings = [];
let scanned = 0;

for (const file of files) {
  const path = join(ROOT, file);
  let stat;
  try {
    stat = statSync(path);
  } catch {
    continue;
  }
  if (!stat.isFile() || stat.size > 4_000_000) continue;

  let buffer;
  try {
    buffer = readFileSync(path);
  } catch {
    continue;
  }
  // A NUL in the first kilobyte means binary: lockfiles, caches, images.
  if (buffer.subarray(0, 1024).includes(0)) continue;
  const text = buffer.toString("utf-8");
  scanned += 1;
  for (const { name, re } of PATTERNS) {
    for (const match of text.matchAll(re)) {
      const line = text.slice(0, match.index).split("\n").length;
      findings.push({ file, line, kind: name, text: match[0] });
    }
  }
}

if (findings.length === 0) {
  console.log(`  local paths: ${scanned} tracked file(s) scanned, none found.`);
  process.exit(0);
}

console.log(`  local paths: ${findings.length} absolute home path(s) in tracked files`);
for (const f of findings) {
  console.log(`    - ${f.file}:${f.line}  [${f.kind}]  ${f.text}`);
}
console.log("  Replace with a repo-relative path, an env var, or `~`.");
process.exit(1);
