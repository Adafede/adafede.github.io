/**
 * Fail if AGENTS.md names a command or a path that does not exist.
 *
 * Instruction files rot silently: nobody notices a stale command until an
 * agent runs it, gets a confusing error, and guesses. This closes that loop by
 * extracting every executable reference out of the instruction file and
 * checking it against the things that actually define them:
 *
 *   - `npm run <name>`  -> must be a script in package.json
 *   - `uv run <tool>`   -> must be a declared dependency or dependency group
 *   - `node <path>`     -> must exist on disk
 *   - backticked paths  -> must exist on disk, when they look like repo paths
 *
 * Deliberately dependency-free (node:fs only) so it can run in pre-commit and
 * in CI without a build step.
 *
 * Run: node scripts/site/check-agent-docs.mjs             # AGENTS.md
 *      node scripts/site/check-agent-docs.mjs README.md   # another file
 * Exits nonzero on any mismatch, like the other validators in this directory.
 */
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const target = process.argv[2] ?? "AGENTS.md";
const doc = join(ROOT, target);

if (!existsSync(doc)) {
  console.error(`${target}: no such file`);
  process.exit(1);
}

const text = readFileSync(doc, "utf-8");

const problems = [];

/* ---------------------------------------------------------------- npm run --- */

const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf-8"));
const scripts = pkg.scripts ?? {};
const npmNames = new Set();

for (const match of text.matchAll(/npm run ([\w:-]+)/g)) npmNames.add(match[1]);
for (const name of [...npmNames].sort()) {
  if (!(name in scripts)) {
    problems.push(`\`npm run ${name}\` — no such script in package.json`);
  }
}

/* ----------------------------------------------------------------- uv run --- */

const pyproject = readFileSync(join(ROOT, "pyproject.toml"), "utf-8");
const declared = new Set([
  ...pyproject.matchAll(/^\s*"([A-Za-z0-9._-]+)[\s<>=]/gm),
  ...pyproject.matchAll(/^\s*"([A-Za-z0-9._-]+)",?$/gm),
].map((m) => m[1].toLowerCase()));

// `uv run --with <tool> <cmd>` installs the tool on the fly, so it resolves
// anywhere and needs no declaration. Only bare `uv run <tool>` has to come
// from the project env — a tool that is merely on the author's PATH makes the
// instruction work on one machine and nowhere else, which is exactly the class
// of drift this script exists to catch.
const uvNames = new Set();
for (const match of text.matchAll(/uv run (?!--with )([a-z][\w-]*)/g)) {
  uvNames.add(match[1]);
}
for (const name of [...uvNames].sort()) {
  if (name === "python" || name === "python3") continue;
  const installed = declared.has(name) || existsSync(join(ROOT, ".venv", "bin", name));
  if (!installed) {
    problems.push(
      `\`uv run ${name}\` — not a declared dependency; it only works if ` +
        `${name} happens to be on PATH. Use \`uv run --with ${name} ${name}\`.`,
    );
  }
}

/* ------------------------------------------------------------ node <path> --- */

// Scanned across the whole document, not just fenced blocks: `node <file>` is
// unambiguous wherever it appears, including in prose.
for (const match of text.matchAll(/node ([\w./-]+\.(?:mjs|js|json))/g)) {
  if (!existsSync(join(ROOT, match[1]))) {
    problems.push(`\`node ${match[1]}\` — no such file`);
  }
}

/* ------------------------------------------------- backticked repo paths --- */

const IGNORED = /[<>*?|(){}]/;
const seenPaths = new Set();
for (const match of text.matchAll(/`([\w./@-]+\/[\w./@-]+)`/g)) {
  const path = match[1];
  if (IGNORED.test(path) || path.includes("…") || seenPaths.has(path)) continue;
  seenPaths.add(path);
  // Skip anything that is clearly not a filesystem path.
  if (!/\.[a-z]{1,5}$/.test(path) && !path.endsWith("/")) continue;
  if (!existsSync(join(ROOT, path))) {
    problems.push(`\`${path}\` — referenced in the map, but not on disk`);
  }
}

/* ----------------------------------------------------------------- report --- */

if (problems.length === 0) {
  console.log(`  ${target}: every command and path resolves.`);
  process.exit(0);
}

console.log(`  ${target}: ${problems.length} unresolved reference(s)`);
for (const problem of problems) console.log(`    - ${problem}`);
process.exit(1);
