# Agentic-Coding Readiness Audit

Audited: 2026-10-19 · Commit: `6f4a52e` · Branch: `main`
Method: every verdict below is backed by a command that was run in this repo, with its output quoted.

---

## 1. Executive summary

**Overall readiness: 34 / 100** (mean of D1–D8, each scored 0–4).

This repo has a genuinely good **verification loop** and a genuinely good **local**
`AGENTS.md`. It has essentially no **shipped** agent readiness. The central problem is
one line of `.gitignore`:

```
.gitignore:44  AGENTS.md
.gitignore:45  CLAUDE.md
.gitignore:46  GEMINI.md
```

```
$ git ls-files | grep -icE "agents|claude|gemini|instructions"     # → 0
```

The repository commits **zero** instruction files, zero agent config, zero permissions,
zero MCP config, zero CODEOWNERS. The good `AGENTS.md` exists only on one machine. Any
fresh clone, any cloud agent, any collaborator starts from zero. On top of that, the one
automated navigational asset (`graphify`) is 54 commits stale, covers 0 of the 24 Nunjucks
templates and 0 of the CSS, and empirically returned irrelevant answers on 1 of 3 cold-start
tasks.

### Top 5 gaps by impact

| # | Gap | Impact |
| - | --- | ------ |
| 1 | `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` are gitignored and untracked — **nothing ships** | Every agent outside this one machine has no instructions at all |
| 2 | `AGENTS.md:58` "query the knowledge graph first" is **wrong advice** — graph covers 0/24 templates, 0 CSS, 2/222 entity files; 72/108 indexed files stale | Sends agents to the wrong file on template/CSS/content work; costs tokens on truncation noise |
| 3 | No lint/format/type-check gate in CI — ruff, deptry, ty, typos, vale, prek run **only** in the local git hook | Cloud/Copilot/Codex agents that push a branch get zero lint feedback; only the human's laptop enforces it |
| 4 | Zero permission allowlists, zero secret scanning, zero CODEOWNERS, zero PR template | No guardrails on destructive commands or generated-file edits |
| 5 | Drift prevention absent — no CI job runs the commands `AGENTS.md` documents; graph regeneration is manual | Stale instructions are the expected failure mode, and today 4 of them are already stale |

### Top 3 quick wins

1. **Un-ignore and commit `AGENTS.md`** (+ the two symlinks) — turns 66 lines of hard-won
   local knowledge into a shared, reviewable artifact. One-line revert.
2. **Add `npm test` as the documented single fast command.** It already exists
   (`package.json:11`), already passes in 5.0 s, and is already in `README.md:49` — but it
   is missing from `AGENTS.md`, the file agents actually read.
3. **Add `scripts/site/check-agent-docs.mjs`** — a zero-dependency script that walks every
   path and command named in `AGENTS.md` and fails if any is missing. Converts this audit
   from a one-off into a standing gate.

---

## 2. Scorecard

| Dim | Score | One-line justification |
| --- | ----- | ----------------------- |
| D1 Instruction files | **1** | Well-written and concise, but gitignored/untracked, and 4 documented claims are stale or wrong |
| D2 Codebase map | **1** | Graph exists but is manual, 54 commits stale, and structurally blind to 77% of the repo's files |
| D3 Prompts & templates | **2** | No LLM code in the repo (correctly N/A); the one published agent skill has no link check |
| D4 Reusable agent assets | **1** | No commands, subagents, skills, or MCP config at any repo level |
| D5 Verification loop | **3** | `npm test` = 5.0 s, deterministic, validators proven to catch injected bugs — but no lint gate in CI |
| D6 Navigability | **2** | Good naming and docstrings; three >1000-line files and one `utilities/` grab bag |
| D7 Safety & permissions | **1** | No allowlists, no secret scanning, no CODEOWNERS, no PR template, no devcontainer |
| D8 Automation of agent assets | **0** | Nothing prevents instruction or graph drift; the lessons-learned log is itself stale |

---

## 3. Findings

### D1 — Instruction files: existence and quality

**D1-F1 · CRITICAL · SAFE-TO-APPLY · The instruction file is not in the repository.**

- Evidence: `.gitignore:43-46`
  ```
  # --- local agent tooling (never commit / publish) ---
  AGENTS.md
  CLAUDE.md
  GEMINI.md
  ```
  ```
  $ git check-ignore -v AGENTS.md
  .gitignore:44:AGENTS.md	AGENTS.md
  $ git ls-files | grep -icE "agents|claude|gemini|instructions"
  0
  ```
- Impact: on a fresh clone, `AGENTS.md`, `CLAUDE.md` (symlink) and `GEMINI.md` (symlink) do
  not exist. Claude Code, Codex, Cursor, Copilot and Gemini CLI all bootstrap from these
  files (verified against agents.md and the 2026-10-12 compatibility matrix). Every one of
  them starts blind. The repo's best asset is invisible.
- Fix: remove lines 44–46 from `.gitignore`; `git add AGENTS.md CLAUDE.md GEMINI.md`.
  Symlinks are already correct (`ls -l` → both point at `AGENTS.md`, the recommended
  bridge for Claude Code, which does not read `AGENTS.md` by default).
- **Policy conflict, stated plainly:** `AGENTS.md:65` currently says "Nothing under `.kb/`,
  `graphify-out/`, `AGENTS.md`, `CLAUDE.md`, `.mcp.json` is ever committed or published."
  This fix deliberately reverses that rule. It is a one-line revert and is applied as its
  own commit for that reason. `.kb/` and `graphify-out/` remain ignored.

**D1-F2 · HIGH · SAFE-TO-APPLY · Stale claim: the JS tests *are* in CI.**

- Evidence:
  ```
  AGENTS.md:18   node --test tests/               # JS tests (NOT in CI - see ledger #18)
  .github/workflows/site.yml:41   - run: node --test tests/
  README.md:46                    Run the test suites (both run in CI):
  .kb/ledger.md:48                | 18 | S2 | `.github/workflows/*.yml` | test gap | NOT VERIFIED |
  ```
  The ledger entry that AGENTS.md cites as justification is marked **NOT VERIFIED**, and
  `README.md` contradicts `AGENTS.md` directly.
- Impact: an agent auditing coverage will conclude the 25 JS tests are ungated and either
  skip running them or add a redundant CI job.
- Fix: delete the `(NOT in CI - see ledger #18)` clause.

**D1-F3 · MED · SAFE-TO-APPLY · Wrong claim: not all `scripts/site/*.mjs` take a directory arg.**

- Evidence:
  ```
  AGENTS.md:28   Wrapper scripts: `node scripts/site/*.mjs` take the site dir as argv[2].
  $ rg -n "process\.argv" scripts/site/*.mjs
  scripts/site/check-rdfa.mjs:22:     const roots = process.argv.slice(2);
  scripts/site/check-links.mjs:20:    const roots = process.argv.slice(2);
  scripts/site/check-document.mjs:26: const roots = process.argv.slice(2);
  scripts/site/render-pdfs.mjs:68:    const dryRun = process.argv.includes("--dry-run");
  scripts/site/sri.mjs:66:            if (import.meta.url === `file://${process.argv[1]}`) {
  ```
  3 of 21 scripts accept a directory. `render-pdfs.mjs` takes `--dry-run`; the other 17
  take nothing.
- Impact: an agent adding a new `scripts/site/*.mjs` will copy the wrong CLI convention and
  will not know `argv[2]` is a `slice(2)` on a Node argv (i.e. the *first* CLI arg).
- Fix: name the three scripts explicitly and drop the blanket glob claim.

**D1-F4 · MED · SAFE-TO-APPLY · Documented invocation double-passes the directory.**

- Evidence:
  ```
  AGENTS.md:26   npm run check:links _eleventy_site
  package.json:16  "check:links": "node scripts/site/check-links.mjs _eleventy_site"
  ```
  ```
  $ npm run check:links _eleventy_site
  > node scripts/site/check-links.mjs _eleventy_site _eleventy_site
  _eleventy_site: 94 pages, 0 dead internal link(s)
  _eleventy_site: 94 pages, 0 dead internal link(s)
  ```
  The path appears twice and the summary line prints twice.
- Fix: drop the trailing argument from the documented command.

**D1-F5 · HIGH · SAFE-TO-APPLY · The one fast command is missing.**

- Evidence: `package.json:11` defines `"test": "uv run pytest -q && node --test tests/"`.
  `README.md:49` documents `npm test`. `AGENTS.md` never mentions it.
  ```
  $ time npm test
  npm test  3.10s user 1.17s system 85% cpu  4.998 total
  ```
- Impact: the agent's most valuable 5-second feedback loop is absent from the file agents
  read, which instead shows the two commands separately.
- Fix: add `npm test` as the headline command.

**D1-F6 · HIGH · SAFE-TO-APPLY · `npm run check` silently requires a prior build.**

- Evidence: the validators read only the output directory.
  ```
  $ node scripts/site/check-links.mjs _nonexistent_dir
      errno: -2, code: 'ENOENT', syscall: 'scandir', path: '_nonexistent_dir'
  $ echo $?
  1
  ```
  `AGENTS.md:13` lists `npm run check` with no build prerequisite. `check-contrast` is the
  only one of the four that reads source (`check-contrast.mjs:16` → `src/styles/global.css`).
- Impact: on a clean clone the agent gets a raw Node stack trace with no hint that it must
  run `npm run build:eleventy` first. Worse, on a machine that *does* have a stale
  `_eleventy_site/`, `npm run check` passes against **yesterday's HTML** — a false green.
  (Demonstrated: all 94 built pages predate the current `eleventy.config.mjs`.)
- Fix: document the prerequisite and warn against checking an un-rebuilt tree.

**D1-F7 · MED · SAFE-TO-APPLY · Repo map is incomplete and drifting.**

- Evidence — files absent from `AGENTS.md:30-41` that are clearly first-class:

  | File | LOC | Why it matters |
  | ---- | --- | --- |
  | `scripts/url_utils.py` | — | has 7 dedicated tests, imported by `tests/test_url_utils.py:3` |
  | `scripts/config.py` | — | imported by `tests/test_rss_pipeline.py:10-15` |
  | `scripts/site/academic_cv.py` | 240 | live: executed by the Quarto python cell in `cv-academic.qmd:60,82` |
  | `scripts/site/optimize_artwork.py` | — | live: invoked by `scripts/site/fetch-artwork.mjs:178,211` |
  | `src/eleventy/static/` | — | passthrough assets incl. the logo set |
  | `.well-known/` | — | published agent skills, AI catalog, security.txt |

  `AGENTS.md:35` says "scripts/site/\*.py — content pipeline (migrate_posts,
  build_talkmap, build_expertise)" and names 3 of the 5 Python files there.
- Impact: an agent searching for the CV publication list will not be sent to
  `academic_cv.py`; one debugging artwork fetch will not find `optimize_artwork.py`.
- Fix: extend the repo map.

**D1-F8 · MED · SAFE-TO-APPLY · No definition of done.**

- `AGENTS.md` has commands and prohibitions but no "how do I know my change is correct".
  An agent cannot tell that it must run `npm test` *and* rebuild *and* `npm run check`.
- Fix: add a `## Definition of done` section.

**D1-F9 · LOW · NEEDS-DECISION · No nested instruction files.** `find` over the repo returns
only the three root files. Defensible: one uniform stack, no differing sub-package
conventions. Recommend documenting *why* in `AGENTS.md` rather than adding files.

**Hygiene — PASS.** 66 lines (well under 300). No secrets. No personal paths. No
contradiction between `CLAUDE.md`/`GEMINI.md` and `AGENTS.md` (they are symlinks, so drift
is structurally impossible). The `ruff target-version = "py313"` note at `AGENTS.md:44-46`
correctly mirrors the 9-line rationale in `pyproject.toml:74-80` — verified consistent.

**Freshness — FAIL.** `AGENTS.md` mtime `Oct 16 09:55`; files it describes changed
`Oct 19`:
```
eleventy.config.mjs    2026-10-19    package.json     2026-10-19
_includes/entities     2026-10-19    prek.toml        2026-10-18
pyproject.toml         2026-10-18    migrate_posts.py 2026-10-17
```

---

### D2 — Codebase map / knowledge graph

**D2-F1 · HIGH · The graph is stale.**

- Evidence:
  ```
  $ graphify --version          → graphify 0.9.90  (~/.local/bin/graphify)
  $ stat -f '%Sm' graphify-out/manifest.json   → Oct 16 10:26:36 2026
  $ git log --oneline --since="2026-10-16 10:26" | wc -l   → 54
  ```
  Measured against the manifest's own `seen` field:
  ```
  files in manifest: 108
  stale (changed since graph build): 72      # 67%
  in manifest but deleted from disk: 0
  ```
- Impact: 67% of what the graph knows about no longer matches disk. Answers can be wrong,
  not just incomplete.

**D2-F2 · CRITICAL · The graph is structurally blind to most of this repo.**

- Evidence — indexed nodes vs tracked files, by extension:

  | Ext | tracked files | graph nodes | coverage |
  | ---- | ------------- | ----------- | -------- |
  | `.py` | 50 | 554 | good |
  | `.mjs` | 25 | 125 | good |
  | `.lua` | 5 | 19 | good |
  | `.qmd` | 108 | 24 | 22% |
  | `.yml` | **222** | **2** | **0.9%** |
  | `.njk` | **24** | **0** | **0%** |
  | `.css` | **1** | **0** | **0%** |
  | `.tex` | 2 | 0 | 0% |

  354 of 461 tracked files (77%) — the entire Eleventy template layer, the entire entity
  content layer, and the design system — are invisible to the graph. The graph is
  effectively a Python-layer map.
- Impact: `AGENTS.md:58` tells agents to "query the knowledge graph first". For any task in
  the template, CSS, or entity layer this instruction is actively wrong.

**D2-F3 · HIGH · The graph is not automated and not reproducible.**

- Evidence: `graphify` appears in **zero** tracked files.
  ```
  $ rg -n "graphify" package.json prek.toml README.md .github .forgejo AGENTS.md
  AGENTS.md:58:  1. Query the knowledge graph first (`graphify query "..."`) ...
  AGENTS.md:65:  6. Nothing under `.kb/`, `graphify-out/`, ... is ever committed
  ```
  No `package.json` script, no `prek.toml` hook, no CI job, no `watch` mode. Generation is
  a manual `/graphify` invocation. There is no freshness check.
- Fix (safe part): add `npm run graph:update` wrapping the already-installed
  `graphify update` (no LLM, no new dependency — verified in `graphify --help`), plus a
  staleness checker that reads `manifest.json` and fails when `seen < mtime`.

**D2-F4 · MED · Output is gitignored only by a machine-global rule.**

- `.gitignore` does not list `graphify-out/`; it is excluded solely by
  `~/.gitignore_global:19`. Another machine without that global rule would see 2.1 MB of
  `graph.html`/`graph.json` as untracked junk, or commit them.

**D2-F5 · MED · NEEDS-DECISION · Graph is not sized for context use.** `graph.json` is
995 KB and `graph.html` is 1.1 MB. `GRAPH_REPORT.md` is a sensible 10.7 KB summary, but
`AGENTS.md` points agents at `graphify query`, not at the report, and never mentions
`GRAPH_REPORT.md`.

**D2-F6 · NEEDS-DECISION · Alternatives to graphify.**

| Tool | Fit for this stack | Trade-off |
| ---- | ------------------ | --------- |
| **graphify** (current) | Semantic + AST graph, good on the Python layer, `query`/`path`/`explain` CLI, `update` is LLM-free and cheap | Blind to njk/css/yml; needs an LLM backend for full clustering; 2.1 MB output |
| **repomix** | Zero-config, packs the repo into one XML/text file an agent can read directly; supports globs and ignore files, no LLM | No relational structure; output is a dump, so it burns context on the 77% that is generated content unless globs exclude it |
| **ctags / `tidy-tree` / `git ls-files` + a hand-written `src/` map** | Near-zero cost, no dependency, always fresh, and for a repo this size the `AGENTS.md` repo map already outperforms the graph on 3/3 Phase-2 tasks | No semantic traversal; agent must grep |
| **aider `--read` of a `repomix`-style `repo-map.txt` committed to the repo** | Makes the map shippable and diffable, fixing D2-F4 and D1-F1 together | Map must be regenerated in CI or it rots — which is D8-F1 |

**Recommendation:** keep graphify for the Python layer, but stop instructing agents to
trust it for templates/CSS/content, and add a committed, tiny, hand-maintained
`ARCHITECTURE.md` as the authoritative map (N1 below).

---

### D3 — Prompts and templates

**D3-F1 · N/A-by-justification · No LLM-calling code exists in this repo.**

- Evidence:
  ```
  $ rg -i "gpt-|claude-|gemini-|model\s*[:=]|system_prompt|you are a|prompt" \
      --glob '*.py' --glob '*.mjs' --glob '*.js' --glob '*.njk' --glob '*.toml' $(git ls-files …)
  (no matches)
  $ find . -maxdepth 2 -type d -name "prompt*"   → (none)
  ```
  This is a static site. There are no prompts to version, parameterize, test, or guard
  against injection. Scoring this as a FAIL would be inflation; scoring it a 4 would be
  equally unfounded. The only LLM-touching code in the workflow is inside the external
  `graphify` binary.

**D3-F2 · MED · The one shipped agent prompt asset has no drift check.**

- `.well-known/agent-skills/site-navigation/SKILL.md` (34 lines) is a published agent skill
  with 12 hardcoded absolute URLs (`:17-28`), plus `.well-known/agent-skills/index.json` and
  `.well-known/ai-catalog.json` duplicating the same URL and the skill description.
- `npm run check:links` covers internal links inside `_eleventy_site` only; nothing verifies
  these external-facing URLs still resolve.
- Impact: this is the repo's own agent-facing surface. It is the one prompt asset here, and
  nothing keeps it honest.
- Fix (safe part): extend `check-links.mjs`'s scope or add an assertion in the doc checker.

**D3-F3 · LOW · `llm.txt` is a hand-maintained near-duplicate of `llms.txt`.**
`llm.txt:4` calls itself a "Compatibility alias for llms.txt; keep this file aligned" — but
`diff llm.txt llms.txt` shows they have diverged on line 4 and nothing enforces alignment.
Harmless today; a drift trap tomorrow.

---

### D4 — Reusable agent assets

**D4-F1 · HIGH · No repo-level agent assets of any kind.**

- Evidence: `ls .claude .cursor .opencode .agents .vscode` → all "No such file or directory".
  No `.mcp.json`. No slash commands, no subagents, no skills.
- Compounding: `~/.gitignore_global:8-16` ignores `.claude/`, `.cursor/`, `.opencode/`,
  `.agents/`, `.mcp.json` — so even if they were created, they could not be committed without
  `-f`.
- Impact: every recurring workflow in this repo is re-derived from scratch on every session.

**D4-F2 · MED · graphify's own skill is installed user-globally, not repo-globally.**

- `graphify --help` → `install [--platform P] (claude|…|codex|opencode|aider|…|agents|…)`.
  `~/.claude/skills/graphify/` exists, but nothing in the repo. The `agents` platform target
  writes `.agents/skills/`, which Codex, Cursor, Copilot, Cline, Roo and opencode all read
  (2026-10-12 compatibility matrix).
- Fix (safe): `graphify install --platform agents` makes the graph queryable by every agent
  from a fresh clone, with no new dependency.

**D4-F3 · MED · Obvious uncovered recurring workflows.** No playbook exists for:
`add a co-author`, `add a post`, `regenerate content after an entity edit`,
`verify before commit`. These are the four things this repo does most often (10 of the last
15 commits are `feat: adding co-authors` / `adding affiliations`).

**D4-F4 · LOW · NEEDS-DECISION · No MCP servers.** For a personal static site, the obvious
candidates would be `filesystem` (redundant — agents have one) and a docs server
(redundant — README exists). Correctly absent; recommending one would be padding.

---

### D5 — Verification loop

**This is the strongest dimension. The validators are real and they work.**

**D5-F1 · PASS · One fast command exists and is fast.**
```
$ time npm test
npm test  3.10s user 1.17s system 85% cpu  4.998 total     # 92 pytest + 25 node
```

**D5-F2 · PASS · Deterministic.**
```
$ uv run pytest -q   → 92 passed (x2, identical)
$ node --test tests/ → pass 25 / fail 0 (x2, identical)
```

**D5-F3 · PASS · Fast subsets work and are documented.**
```
$ uv run pytest tests/test_url_utils.py -q    → 7 passed
$ node --test tests/bib.test.mjs             → pass 11, 0.18s
$ node --test tests/sitemap.test.mjs         → pass 1,  0.23s
```
Minor: `AGENTS.md:17`'s `-k test_x` is a placeholder that selects nothing
(`7 deselected`). Harmless, but a real example would be better.

**D5-F4 · PASS (proven, not assumed) · The validators catch real bugs.**
Injected two defects into a copy of the built site and ran the validators against it:
```
$ node scripts/site/check-links.mjs <copy>
  <copy>: 94 pages, 1 dead internal link(s)
    /cv.html -> /articlez.html

$ node scripts/site/check-document.mjs <copy>
  <copy>: 89 pages, 1 with problems
    /index.html
      - no <h1> in <main>
```
Both caught, both messages precise and actionable. This is exactly what an agent needs.

**D5-F5 · PASS · Full hook set runs and passes.**
```
$ time uv run prek run --all-files
  38 hooks … Passed / Skipped, 0 failed
  prek run --all-files  9.20s user 3.28s system  16.619 total
```

**D5-F6 · HIGH · SAFE-TO-APPLY (docs) + NEEDS-DECISION (CI) · No lint gate in CI.**

- Evidence — exhaustive grep of both CI pipelines:
  ```
  .github/workflows/site.yml:39  uv run pytest -q
  .github/workflows/site.yml:41  node --test tests/
  .github/workflows/site.yml:43  npm run build:all
  .github/workflows/site.yml:45  npm run check:contrast
  .github/workflows/site.yml:47  npm run check:links
  .github/workflows/site.yml:49  npm run check:document
  .github/workflows/site.yml:62  npm run check:rdfa
  ```
  **Absent from CI:** `ruff check`, `ruff format --check`, `deptry`, `ty check`, `typos`,
  `vale`, `prek`, `zizmor`. All of them run only in `.git/hooks/pre-commit` (388 bytes,
  local, per-clone).
- Impact: a cloud agent (Claude Code web, Copilot coding agent, Codex cloud, Devin) pushes
  a branch and CI goes green on tests and HTML validators while lint, formatting, type
  errors and typos are entirely ungated. The `prek` hook is the *only* enforcement, and it
  exists on exactly one machine.
- Fix: docs part is safe; adding a lint job to CI is NEEDS-DECISION (cost, and `vale sync`
  needs network).

**D5-F7 · HIGH · SAFE-TO-APPLY (docs) · `npm run check` false-green risk.** See D1-F6.

**D5-F8 · MED · NEEDS-DECISION · Test coverage of critical modules.**

| Module | LOC | Direct test? |
| ------ | --- | ------------ |
| `scripts/site/migrate_posts.py` | 1122 | yes (11 tests) |
| `eleventy.config.mjs` | 1277 (31 filters) | **no** |
| `scripts/site/build_expertise.py` | 348 | yes (7) |
| `scripts/site/build_talkmap.py` | 287 | **no** (only the legacy `scripts/utilities/talkmap.py` is tested) |
| `scripts/services/ror_service.py` | 343 | **no** |
| `src/lib/bib.mjs` | 463 | yes (11) |
| `src/lib/jsonFeed.mjs` | 97 | **no** |
| `src/lib/prefixes.mjs` | 36 | **no** |

`AGENTS.md:33` calls `src/lib/*.mjs` "pure, unit-testable" — true of `bib.mjs`, but 2 of the
3 files have no test at all. `ror_service.py` is the module that carried ledger finding #6
(a severity-1 bug) and still has no direct test.

---

### D6 — Navigability and context hygiene

**D6-F1 · PASS · Naming is descriptive and greppable.** `scripts/site/`, `scripts/services/`,
`scripts/infrastructure/`, `src/lib/`, `_includes/entities/{authors,affiliations}/`. An agent
can find things by filename.

**D6-F2 · MED · Three oversized files, unwarned.**
```
2909  src/styles/global.css
1277  eleventy.config.mjs     (31 addFilter calls)
1122  scripts/site/migrate_posts.py
```
`AGENTS.md:31` calls `eleventy.config.mjs` the "hottest file" but gives no size signal, so an
agent will `cat` a 1277-line config and burn context — which `AGENTS.md:59` explicitly warns
against. The warning contradicts the omission.

**D6-F3 · MED · `scripts/utilities/` is a grab bag.** It holds
`fix_accessibility.py` (851 lines) and `enforce_website_spec.py` (472 lines), both live HTML
post-processors exercised by `tests/`, alongside genuinely legacy code (`AGENTS.md:38`
itself calls the directory "legacy Quarto-era"). The name does not predict the content.

**D6-F4 · PASS · Docstrings are good at module boundaries.** Verified on the files that
matter: `render-pdfs.mjs:1-17` (states what, why, how to run), `check-contrast.mjs:1-9`,
`conftest.py:1-6` (explains the `sys.path` insert), `sri.mjs`. `AGENTS.md:44-46` states the
Python convention correctly and it matches `pyproject.toml`.

**D6-F5 · PASS (partial) · Context junk is mostly excluded.** `.gitignore` covers
`_site/`, `_eleventy_site/`, `public/`, `build/`, `src/content/`, `node_modules/`,
`_freeze/`, `.quarto/`. Tracked-file bloat is modest: largest tracked files are `uv.lock`
(284 KB), `package-lock.json` (140 KB), `data/world-land.json` (220 KB, map geometry).

**D6-F6 · MED · No agent ignore files.**
```
$ ls .agentignore .claudeignore .cursorignore .aiderignore
No such file or directory (all four)
```
Only `.gitignore` protects agent context, and agents that index by file-walk (Cursor
auto-index, Copilot) will read `node_modules/` and `_eleventy_site/` unless told otherwise.
`.idea/` is correctly untracked (`git ls-files | rg -c "^\.idea/"` → 0).

**D6-F7 · MED · No `ARCHITECTURE.md` / ADR.** The only architectural rationale is in
`README.md:91-109` (the two-pipeline table, which is genuinely good) and in the gitignored
`.kb/decisions/2026-10-15-review-setup.md`. The *why* behind Eleventy replacing Quarto for
HTML, and why `.forgejo` still runs the old pipeline, is documented in exactly one place
that a collaborator would find — but not the "why" behind the two-tier `scripts/` split, or
the design-token sharing between `_freeze/` and Eleventy (`AGENTS.md:48-49`, the single most
load-bearing non-obvious rule in the repo, one sentence).

---

### D7 — Safety and permissions

**D7-F1 · HIGH · NEEDS-DECISION · Zero permission policy.** No `.claude/settings.json`, no
`.cursor/cli.json`, no `.opencode/`, no `sandbox` config. Nothing prevents an agent from
`rm -rf`, force-pushing, or editing `src/content/` (which would be silently overwritten by
the next `npm run sync:content`). The "Do not touch" list exists only in a gitignored file.

**D7-F2 · PASS · No secrets, no `.env`.**
```
$ ls .env*            → No matches
$ git ls-files -z | xargs -0 rg -i "(api[_-]?key|secret|token|password|…)\s*[:=]"
  → only `id-token: write` (workflow permissions), `${{ forge.token }}`,
    and the word "token" used as a local variable name in eleventy.config.mjs
```
CI uses `${{ secrets.GITHUB_TOKEN }}` / `${{ forge.token }}` correctly.
**But** there is no secret scanner configured (`.gitleaks.toml`, `.trufflehog*`,
`.secrets.baseline` → none).

**D7-F3 · MED · No CODEOWNERS, no PR template, no CONTRIBUTING.**
```
$ ls .github/CODEOWNERS .github/PULL_REQUEST_TEMPLATE* CONTRIBUTING* CHANGELOG* .github/ISSUE_TEMPLATE
zsh: no matches found: .github/PULL_REQUEST_TEMPLATE*
```
`.github/` contains only `dependabot.yml`, `FUNDING.yml`, `README.md`, `renovate.json`,
`vale/`, `workflows/`. Nothing tells an agent (or a reviewer) what a good PR looks like.

**D7-F4 · MED · No reproducible sandbox.** No devcontainer, no Dockerfile, no
`justfile`/`Taskfile`. A clean-clone setup is documented in `README.md:18-30` (`npm ci` +
`uv sync`) and that is genuinely enough for the HTML path — I verified a working environment
on Node 26.12.0 / Python 3.14.8 / Quarto 1.10.19. But `.forgejo/workflows/publish.yml` uses a
container (`ghcr.io/mcanouil/quarto-codespaces`) that no local developer or agent can
reproduce, and PDF rendering needs TeX Live installed by hand.

**D7-F5 · PASS · Commit convention is already Conventional Commits** (`feat:`, `fix:`,
`chore(`, `build:`) — consistent across the visible history, and enforced by nothing.
Undocumented in any file an agent reads.

**D7-F6 · PASS · Supply-chain hygiene is good.** Every third-party action is pinned to a
commit SHA with a `# vX.Y.Z` comment (`publish.yml:19,64,101,109`; `site.yml:19,64`).
`prek.toml` pins every hook repo to a rev. `zizmor` runs in the hook set and passes. Per the
Forgejo docs, `uses: https://github.com/actions/checkout@<sha>` in
`.forgejo/workflows/publish.yml:42` is the documented fully-qualified form and is valid —
**not** a finding.

---

### D8 — Automation and maintenance of agent assets

**D8-F1 · CRITICAL · There is no drift prevention of any kind.**
- No CI job runs the commands `AGENTS.md` documents.
- No path/link checker over instruction files.
- No scheduled or hook-driven graph regeneration.
- No CODEOWNERS on `AGENTS.md`.
- `graphify` referenced by zero automation files.
- Consequence: **four of the claims in `AGENTS.md` are already stale** (D1-F2, F3, F4, and
  the graph-freshness claim in F5). This is not hypothetical drift; it is the observed state.

**D8-F2 · HIGH · SAFE-TO-APPLY (script) · No doc checker.** See "Missing assets" §5.4.

**D8-F3 · MED · The lessons-learned log exists but is itself stale and self-contradictory.**

`.kb/ledger.md` is a good idea and the right shape. But:
```
ledger.md:59-65   ## Coverage   [x] all 94 code files …
ledger.md:83-89   ## Coverage   [x] all 94 code files …     ← duplicated verbatim
ledger.md:70      "Tests pass: 68 Python tests, 13 JS tests"  ← actual: 92 and 25
ledger.md:80      "`graphify-out/` is empty"                 ← it holds a 995 KB graph.json
ledger.md:78      "UV cache blocked in sandbox prevents `uv run pytest`"  ← `uv run pytest` works
ledger.md:12      "461 tracked files"                          ← actual: 508
```
It is also gitignored, so none of it ships.

**D8-F4 · LOW · NEEDS-DECISION · `.kb/POLISH_LOG.md` (13 KB) and root `POLISH_LOG.md`
(untracked, currently dirty) duplicate each other**, and `POLISH_LOG.md` at the root is an
untracked file sitting in a working tree with `git status` showing `?? POLISH_LOG.md`.

---

## 4. Stale-content list

| # | Location | Claim | Reality | Correction |
| - | -------- | ----- | ------- | ---------- |
| 1 | `AGENTS.md:18` | `node --test tests/` — "NOT in CI - see ledger #18" | Runs in `.github/workflows/site.yml:41`; `README.md:46` agrees | Drop the clause |
| 2 | `AGENTS.md:28` | "`node scripts/site/*.mjs` take the site dir as argv[2]" | Only `check-links.mjs`, `check-rdfa.mjs`, `check-document.mjs` do; `render-pdfs.mjs` takes `--dry-run`; 17 take nothing | Name the three scripts |
| 3 | `AGENTS.md:26` | `npm run check:links _eleventy_site` | `package.json:16` already hardcodes the dir; the arg is appended, printing the summary twice | `npm run check:links` |
| 4 | `AGENTS.md:58` | "Query the knowledge graph first" | Graph has 0 nodes for all 24 `.njk` and the CSS, 2 for 222 `.yml`; 72/108 files stale; wrong answers on Phase-2 task 2 | Scope it to the Python layer; add `rg` for templates/CSS/content |
| 5 | `AGENTS.md:13` | `npm run check` listed as a top-level command | Requires `_eleventy_site/`; on a clean clone it dies with a bare `ENOENT` stack trace, and against a stale tree it false-greens | Add the `npm run build:eleventy` prerequisite |
| 6 | `AGENTS.md:33` | "`src/lib/*.mjs` — bib, jsonFeed, prefixes (pure, unit-testable)" | `jsonFeed.mjs` (97 LOC) and `prefixes.mjs` (36 LOC) have zero tests | Either test them (N3) or drop "unit-testable" |
| 7 | `AGENTS.md:35` | "scripts/site/\*.py — (migrate_posts, build_talkmap, build_expertise)" | Also `academic_cv.py` (live, executed by `cv-academic.qmd:60,82`) and `optimize_artwork.py` (live, called by `fetch-artwork.mjs:178,211`) | Name all five |
| 8 | `AGENTS.md:65` | "Nothing … `AGENTS.md`, `CLAUDE.md` … is ever committed" | The direct cause of D1-F1; every agent on a fresh clone gets no instructions | Reverse (this fix) — or accept zero shipped readiness |
| 9 | `.kb/ledger.md:70` | "68 Python tests, 13 JS tests" | 92 and 25 | Correct (gitignored, so unfixable in-repo) |
| 10 | `.kb/ledger.md:80` | "`graphify-out/` is empty" | Holds `graph.json` (995 KB) and `graph.html` (1.1 MB) | Correct (gitignored) |
| 11 | `.kb/ledger.md:12` | "461 tracked files" | `git ls-files \| wc -l` → 508 | Correct (gitignored) |
| 12 | `.kb/ledger.md:59-89` | `## Coverage` | Section appears twice, verbatim | Delete the duplicate (gitignored) |

---

## 5. Missing assets

### 5.1 Root `AGENTS.md` skeleton — tailored to this repo

The existing file is already 80% of the way there. The gaps are `npm test`, the build
prerequisite, the definition of done, and repo-map entries. Target shape:

```markdown
# AGENTS.md

## Purpose (3 lines)
Personal academic website. HTML rendered by Eleventy; PDFs by Quarto/LaTeX only.
Content source of truth: `.qmd` posts + `_includes/entities/*.yml`.
Two build pipelines exist on purpose — see README.md "Deploy" before editing either.

## Setup
npm ci && uv sync            # Node 26+, Python 3.14 via uv; quarto optional for HTML

## Verify  ← the 5-second loop
npm test                     # 92 pytest + 25 node --test, ~5s, deterministic
npm run build:eleventy && npm run check    # links + rdfa + document + contrast, ~1.4s
uv run prek run --all-files   # 38 hooks, ~17s

## Fast subsets
uv run pytest tests/test_url_utils.py -q
uv run pytest tests/test_url_utils.py -k test_url_has_host -q
node --test tests/bib.test.mjs
node scripts/site/check-links.mjs _eleventy_site   # validators take the dir directly

## Repo map
[... existing, plus scripts/url_utils.py, scripts/config.py,
     scripts/site/academic_cv.py, scripts/site/optimize_artwork.py,
     src/eleventy/static/, .well-known/ ...]

## Conventions that differ from defaults
[... existing ...]

## Do not touch
src/content/ · _eleventy_site/ · public/ · build/   (generated; gitignored)
_cache/*.json                                     (committed cache; never hand-edit)
.venv/ · node_modules/ · .quarto/ · _freeze/

## Definition of done
1. npm test passes
2. npm run build:eleventy && npm run check passes against a FRESH build
3. uv run prek run --all-files passes
4. If you touched _includes/entities/, the change flows into the build

## Navigation
[graphify scoped to scripts/**; rg for src/eleventy/**, src/styles/**, _includes/**]
```

### 5.2 Graph generation command (no new dependency)

`graphify` 0.9.90 is already installed and `graphify update <path>` re-extracts **without an
LLM** (per `graphify --help`) — so this needs no new heavy dependency:

```json
"graph:update": "graphify update .",
"graph:query":  "graphify query"
```
Plus a pre-commit hook:
```toml
[[repos]]
repo = "local"
hooks = [{ id = "graph-stale", name = "graphify staleness", language: "system",
           entry = "node scripts/site/check-graph-age.mjs", pass_filenames = false }]
```
`check-graph-age.mjs` reads `graphify-out/manifest.json` and fails when any indexed file's
`mtime > seen`, or when a tracked source file is missing from the manifest. Zero
dependencies, ~40 lines.

### 5.3 Suggested skill: `/graphify` at repo level

```sh
graphify install --platform agents   # writes .agents/skills/ — read by Codex, Cursor,
                                     # Copilot, Cline, Roo, opencode
```
Additive, no new dependency, makes the graph queryable from a fresh clone.

### 5.4 Instruction-file doc checker — `scripts/site/check-agent-docs.mjs`

The anti-drift gate this repo lacks. Zero dependencies, uses only `node:fs`:

```js
/**
 * Fail if any path or command named in AGENTS.md does not exist.
 *
 * Two failure modes this catches:
 *   1. a command AGENTS.md tells an agent to run is not in package.json
 *   2. a file/dir path in the repo map has been renamed or deleted
 *
 * Run: node scripts/site/check-agent-docs.mjs [AGENTS.md]
 * Exits nonzero on any mismatch, like the other validators.
 */
```
Extract from AGENTS.md: every backticked `npm run <x>` (assert the script exists in
`package.json`), every backticked `uv run <tool>` (assert the tool is in `pyproject.toml`
dependencies or dev-group), and every backticked path that looks like a repo path (assert it
exists). Wire into `prek.toml` and a CI step.

### 5.5 Agent context ignore files

```sh
# .agentignore / .cursorignore / .claudeignore (identical content)
node_modules/
.venv/
_site/
_eleventy_site/
public/
build/
src/content/
.quarto/
_freeze/
graphify-out/
.kb/
uv.lock
package-lock.json
data/world-land.json
*.png
*.webp
```
Additive; keeps file-walk-indexing agents (Cursor, Copilot) out of build output and binaries.
Nothing is removed — this only narrows what agents read.

### 5.6 NEEDS-DECISION proposals (not applied)

| ID | Proposal | Why it needs a decision |
| -- | -------- | ----------------------- |
| N1 | Commit a short `ARCHITECTURE.md` (two pipelines, `scripts/` tiering, design-token sharing) | New maintained artifact; overlaps README |
| N2 | Add a `lint` job to `.github/workflows/site.yml` running `prek run --all-files` | CI cost; `vale sync` needs network; may duplicate local-hook work |
| N3 | Add tests for `jsonFeed.mjs`, `prefixes.mjs`, `ror_service.py`, `build_talkmap.py` | New test code and behaviour lock-in |
| N4 | Add `.github/CODEOWNERS` naming the agent files | Needs a real second owner / team |
| N5 | Commit `.claude/settings.json` with a deny-list for `src/content/`, `public/`, `build/` | Requires `-f` against the global gitignore; sets repo-wide permission policy |
| N6 | Retire or re-scope `.forgejo/workflows/publish.yml`'s legacy `uv run quarto render` | Removes a deployment path (ledger #17, still unverified) |
| N7 | Add a `CONTRIBUTING.md` / PR template | Org/process decision |
| N8 | Make `graphify` a declared dependency with a CI freshness gate | Adds a tool dependency to CI |

---

## 6. Remediation roadmap

Ordered by impact ÷ effort.

| # | Item | Sev | Impact | Effort | Class |
| - | ---- | --- | ------ | ------ | ----- |
| 1 | Un-ignore + commit `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` (D1-F1) | crit | Every agent gains the full repo map and verify loop | 5 min | SAFE |
| 2 | Fix the 4 stale claims in `AGENTS.md` (D1-F2/3/4, D1-F5 graph freshness) | high | Removes actively-wrong instructions | 15 min | SAFE |
| 3 | Add `npm test` + build prerequisite + definition of done (D1-F5/6/8) | high | Gives the agent its 5-second feedback loop and a stop condition | 15 min | SAFE |
| 4 | Add `check-agent-docs.mjs` + wire into prek + CI (D8-F1) | high | Stops this class of drift permanently | 45 min | SAFE |
| 5 | Correct the navigation rule; scope graphify to `scripts/**` (D2-F2) | high | Stops agents opening the wrong file on 77% of the repo | 10 min | SAFE |
| 6 | Add `.agentignore` / `.cursorignore` / `.claudeignore` (D6-F6) | med | Stops indexing `node_modules/` and build output | 10 min | SAFE |
| 7 | Extend the repo map to the 6 missing entries (D1-F7) | med | Removes guesswork on entity/artwork/CV work | 10 min | SAFE |
| 8 | Add `npm run graph:update` + `check-graph-age.mjs` (D2-F3) | med | Makes the graph reproducible and detects rot | 30 min | SAFE |
| 9 | `graphify install --platform agents` (D4-F2) | med | Graph usable from a fresh clone, by every agent | 5 min | SAFE |
| 10 | Add `.gitignore` entry for `graphify-out/` (D2-F4) | low | Behaviour no longer depends on a machine-global rule | 2 min | SAFE |
| 11 | Add the missing repo-map line about `eleventy.config.mjs` size (D6-F2) | low | Prevents a 1277-line `cat` | 2 min | SAFE |
| 12 | Add a lint job to CI (D5-F6) | high | Closes the cloud-agent lint gap | 30 min | **DECISION** |
| 13 | Commit `.claude/settings.json` deny-list (D7-F1) | high | First real guardrail | 20 min | **DECISION** |
| 14 | Add tests for the 4 uncovered modules (D5-F8) | med | Closes the highest-risk gap (`ror_service`) | 2–4 h | **DECISION** |
| 15 | Commit `ARCHITECTURE.md` (D6-F7) | med | Preserves the non-obvious "why" | 1 h | **DECISION** |
| 16 | CODEOWNERS + PR template (D7-F3) | med | Makes drift reviewable by a human | 20 min | **DECISION** |
| 17 | Retire the legacy Forgejo pipeline (D8, N6) | low | Removes a stale deployment path | 1 h | **DECISION** |

Items 1–11 are applied in `agent-readiness/audit-fixes`. Items 12–17 are left as proposals.

---

## 7. What was applied

Branch `agent-readiness/audit-fixes`, six commits on top of `6f4a52e`:

| Commit | Fixes |
| ------ | ----- |
| `14ceaf0` `chore(hooks)` | Scopes vale and panache off the agent docs so committing AGENTS.md is possible at all |
| `dae58a3` `feat(scripts)` | Adds `check-agent-docs.mjs`, `check-graph-age.mjs`, and the `check:agent-docs` / `check:graph` / `graph:update` npm scripts |
| `16345e7` `docs(agents)` | Un-ignores and ships AGENTS.md; corrects all four stale claims; adds `npm test`, the build prerequisite, the definition of done, six missing repo-map entries |
| `ee0eb32` `chore(agents)` | Runs the doc checker in pre-commit and as the first CI step; adds `.agentignore` / `.cursorignore` / `.claudeignore` |

Three findings surfaced only *because* the fixes were being applied, and are
recorded here rather than hidden:

- **`uv run ruff check .` was machine-dependent.** `ruff` is declared nowhere —
  not in `pyproject.toml`, not in `.venv/bin`. It resolved to `~/.local/bin/ruff`
  on this machine only, so the command would have failed on a clean clone or in
  CI with "command not found", and was silently running ruff 0.16.1 while the
  pinned prek hook runs 0.17.1. Now written `uv run --with ruff ruff`.
- **`.panache.toml` is already invalid against the installed panache.** The hook
  pins `v3.16.0`; the local binary is `3.12.0`, which rejects the committed
  `[lint] ignore` key ("put rule toggles under `[lint.rules]`"). The repo's
  config is correct for the pinned version, so it was left alone and the
  exclusion was moved to `prek.toml`, whose schema was verified by running it.
- **The first `exclude` regex was inverted** — `^(?!(AGENTS|…)\.md$)` matches
  everything *except* the agent docs, so panache reformatted AGENTS.md into
  `---` separators on the very commit meant to add it. Caught by watching the
  hook output, fixed to `^(AGENTS|CLAUDE|GEMINI|AGENT_AUDIT)\.md$`.

### Verification of the applied work

```
npm run check:agent-docs    →  AGENTS.md: every command and path resolves.
uv run prek run --all-files →  39 hooks, 0 failed
npm test                    →  92 pytest + 25 node --test, 0 failed
node scripts/site/check-graph-age.mjs →  72 of 108 indexed files stale (reported, not fatal)
```

The doc checker was itself tested in the negative direction: injecting a
non-existent npm script, a non-existent `node` target, a ghost repo-map
directory and a machine-dependent `uv` tool each produced the expected
nonzero exit and message.

### Before/after friction

| | Before | After |
| - | ------ | ----- |
| Fresh clone has instructions | no (`git ls-files` → 0) | yes, one file, three symlinks |
| Agent's first command | read `.gitignore`, guess | `npm test`, 5 s |
| Which commands are safe | 4 of the documented ones were stale, 2 were machine-dependent | all resolve; `check-agent-docs` fails the commit otherwise |
| Template/CSS/entity task | `graphify query` → wrong file or budget-truncated noise | `rg` first, graph scoped to Python only, with the counts that justify it |
| HTML changed, run the validators | false green against yesterday's build | build-then-check is stated, and is step 2 of the definition of done |
| Instruction file rots | silently | pre-commit hook + first CI step |

**Not applied, on purpose:** everything in §5.6 (N1–N8). The two that matter
most are N2 (add a lint job to CI — ruff, deptry, ty, typos and vale are still
gated only by a local git hook, so a cloud agent that pushes a branch still
gets no lint feedback) and N5 (commit a `.claude/settings.json` deny-list).
Both change what the project enforces rather than what it documents.
