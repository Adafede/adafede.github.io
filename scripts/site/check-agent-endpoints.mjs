/**
 * Check the endpoints this site publishes *for other people's agents*.
 *
 * `.well-known/agent-skills/`, `.well-known/ai-catalog.json`, `llm.txt`,
 * `llms.txt` and `llms-full.txt` are read by agents visiting the deployed
 * site, not by anyone working in this repo. They hardcode absolute URLs to
 * pages that a rename or a restructure can silently break, and
 * `check-links` only walks links inside the built HTML — it never looks at
 * these files. So they rot in plain sight.
 *
 * Three things are checked:
 *   1. every https://adafede.github.io/... URL in them resolves to a built file
 *   2. llm.txt stays a faithful alias of the canonical llms.txt
 *   3. ai-catalog.json, agent-skills/index.json and the SKILL.md agree on
 *      their mutual URLs and on the skill's id and name
 *
 * Run: node scripts/site/check-agent-endpoints.mjs            # strict
 *      node scripts/site/check-agent-endpoints.mjs --if-built # skip if unbuilt
 *
 * `--if-built` exists because pre-commit cannot assume a build has happened.
 * `npm run lint` runs this hook over the tree, and in CI it runs before
 * `build:all`, so a strict check there fails on a fresh clone for no reason.
 * The pre-commit hook passes `--if-built`; the CI step, which runs *after*
 * `build:all`, stays strict and still fails if the build never happened.
 *
 * Exits nonzero on any mismatch, like the other validators in this directory.
 */
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const args = process.argv.slice(2);
const ifBuilt = args.includes("--if-built");
const dirArg = args.find((a) => !a.startsWith("--"));
const SITE = join(ROOT, dirArg ?? "_eleventy_site");
const HOST = "https://adafede.github.io/";

const problems = [];

const read = (path) => readFileSync(join(ROOT, path), "utf-8");
const readJson = (path) => JSON.parse(read(path));

/* ----------------------------------------------- 1. published URLs resolve --- */

const SOURCES = [
  "llm.txt",
  "llms.txt",
  "llms-full.txt",
  ".well-known/ai-catalog.json",
  ".well-known/ard.json",
  ".well-known/agent-skills/index.json",
  ".well-known/agent-skills/site-navigation/SKILL.md",
];

/** Map a site-absolute URL onto the path it serves. */
function toBuiltPath(url) {
  const path = url.startsWith(HOST) ? url.slice(HOST.length) : url.replace(/^\//, "");
  return path === "" || path.endsWith("/") ? join(path, "index.html") : path;
}

if (!existsSync(SITE)) {
  const msg = `${SITE}: not built. Run \`npm run build:eleventy\` first.`;
  if (ifBuilt) {
    console.log(`  ${msg} Skipped (--if-built).`);
    process.exit(0);
  }
  console.error(msg);
  process.exit(1);
}

let checked = 0;
for (const source of SOURCES) {
  if (!existsSync(join(ROOT, source))) {
    problems.push(`${source}: missing`);
    continue;
  }
  // Stop at whitespace and at any punctuation that can trail a URL in markdown
  // or JSON: a closing paren, bracket, comma, or backtick from an inline-code
  // span. Built from a RegExp so the backtick needs no template-literal escape.
  const URL_IN_SOURCE = new RegExp(HOST + "[^\\s\"'<>)\\]`,]+", "g");
  const urls = [...read(source).matchAll(URL_IN_SOURCE)].map((m) =>
    m[0].replace(/[.,;:]+$/, ""),
  );
  for (const url of new Set(urls)) {
    checked += 1;
    if (!existsSync(join(SITE, toBuiltPath(url)))) {
      problems.push(`${source} advertises ${url} — not in the build`);
    }
  }
}

/* ------------------------------------------------- 2. llm.txt is an alias --- */

const canonical = read("llms.txt").split("\n");
const alias = read("llm.txt").split("\n");
// Line 4 is the one-line description each file uses; everything else must match.
const drift = canonical.filter((line, i) => line !== alias[i] && i !== 3);
if (drift.length) {
  problems.push(
    "llm.txt has drifted from llms.txt (it is declared an alias at llm.txt:4); " +
      `differing line(s): ${drift.length}`,
  );
}

/* --------------------------------------------- 3. the skill files agree --- */

const skill = readJson(".well-known/agent-skills/index.json").skills[0];
const catalog = readJson(".well-known/ai-catalog.json").entries[0];
const skillMd = read(".well-known/agent-skills/site-navigation/SKILL.md");

const skillUrl = `${HOST}.well-known/agent-skills/site-navigation/SKILL.md`;
for (const [label, url] of [
  ["agent-skills/index.json", skill.url],
  ["ai-catalog.json", catalog.url],
]) {
  if (url !== skillUrl) problems.push(`${label} points at ${url}, expected ${skillUrl}`);
}
if (!skillMd.includes(`name: ${skill.name}`)) {
  problems.push(`SKILL.md front matter does not carry the indexed name "${skill.name}"`);
}
if (!catalog.identifier.endsWith(`:${skill.id}`)) {
  problems.push(`ai-catalog.json identifier does not end with the indexed skill id "${skill.id}"`);
}

/* ----------------------------------------------------------------- report --- */

if (problems.length === 0) {
  console.log(`  agent endpoints: ${checked} advertised URL(s) resolve; llm.txt aligned; skill files agree.`);
  process.exit(0);
}
console.log(`  agent endpoints: ${problems.length} problem(s)`);
for (const problem of problems) console.log(`    - ${problem}`);
process.exit(1);
