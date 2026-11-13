import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";

import { join } from "node:path";

import { ROOT, siteSkip } from "./build-state.mjs";

const site = join(ROOT, "_eleventy_site");

test(
  "listing summaries render descriptions as plain text, not Markdown",
  { skip: siteSkip() },
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

test(
  "meta descriptions keep their apostrophes and quotes",
  { skip: siteSkip() },
  () => {
    // plainText used to delete every ' and ", so the published description
    // read "lacquisition" for "l'acquisition".
    const descriptions = readdirSync(join(site, "talks"))
      .filter((name) => name.endsWith(".html"))
      .map((name) => readFileSync(join(site, "talks", name), "utf-8"))
      .flatMap((html) => [
        ...html.matchAll(/<meta name="description" content="([^"]*)"/g),
      ])
      .map((m) => m[1]);

    assert.ok(descriptions.length > 0, "expected talk pages with descriptions");
    assert.ok(
      descriptions.some((d) => d.includes("l&#39;acquisition")),
      "the METABIODIVEX talk description lost its apostrophe",
    );
    for (const d of descriptions) {
      assert.doesNotMatch(d, /&amp;(?:#39|quot);/, `double-escaped: ${d}`);
    }
  },
);
