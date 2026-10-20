/**
 * Removes every generated build output.
 *
 * The four output directories are all gitignored and all rebuilt from tracked
 * sources, but they accumulate: Eleventy does not empty `_eleventy_site/`, so a
 * file that stops being generated (an inlined stylesheet, a deleted script, a
 * re-staged `_headers`) stays behind forever. None of that reaches Pages — the
 * CI build always starts from a clean checkout — but locally it makes the
 * output look like the source of truth when it is not.
 *
 * Run: npm run clean   (then `npm run build:all` to rebuild)
 */
import { rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

/**
 * Generated directories.
 *
 * `_site/` is Quarto's PDF output, `_eleventy_site/` is the built site,
 * `public/` is the staged passthrough and `build/` holds the minified
 * intermediate. All four are listed as "do not touch" in AGENTS.md.
 */
const OUTPUTS = ["_site", "_eleventy_site", "public", "build"];

let removed = 0;
for (const dir of OUTPUTS) {
  const target = join(ROOT, dir);
  try {
    rmSync(target, { recursive: true, force: true });
    removed++;
    console.log(`  - removed ${dir}/`);
  } catch (error) {
    console.error(`  ! could not remove ${dir}/: ${error.message}`);
    process.exitCode = 1;
  }
}

if (removed) console.log(`  + cleaned ${removed} output director${removed === 1 ? "y" : "ies"}`);
