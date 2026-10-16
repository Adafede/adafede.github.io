import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const site = join(here, "..", "_eleventy_site");
const built = existsSync(site);

test(
  "listing summaries render descriptions as plain text, not Markdown",
  { skip: !built },
  () => {
    // Descriptions are Markdown prose. Rendering them raw leaked literal
    // backticks and `*` emphasis markers into the visible summary.
    const html = readFileSync(join(site, "posts.html"), "utf-8");
    const summaries = [
      ...html.matchAll(/class="entry__summary">([^<]*)</g),
    ].map((m) => m[1]);

    assert.ok(
      summaries.length > 0,
      "expected at least one summary on posts.html",
    );

    for (const summary of summaries) {
      assert.ok(
        !summary.includes("`"),
        `markdown code marker leaked: ${summary}`,
      );
      assert.ok(
        !/\*\*\S/.test(summary),
        `markdown emphasis leaked: ${summary}`,
      );
      assert.ok(
        !/\[[^\]]*\]\([^)]*\)/.test(summary),
        `markdown link leaked: ${summary}`,
      );
    }
  },
);
