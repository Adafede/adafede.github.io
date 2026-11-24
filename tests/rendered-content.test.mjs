import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";

import { join } from "node:path";

import { obfuscateMailto } from "../src/lib/email.mjs";
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

test(
  "built homepage ships zero scripts, no-JS analytics pixel, pruned RDFa prefixes, and CSS optimizations",
  { skip: siteSkip() },
  () => {
    const indexHtml = readFileSync(join(site, "index.html"), "utf-8");
    const privacyHtml = readFileSync(join(site, "privacy.html"), "utf-8");

    assert.doesNotMatch(indexHtml, /<script\b/i);
    assert.match(
      indexHtml,
      /<meta http-equiv="Content-Security-Policy" content="[^"]*script-src 'none'/,
    );
    assert.ok(
      indexHtml.includes(
        'src="https://queue.simpleanalyticscdn.com/noscript.gif?hostname=adafede.github.io&amp;path=%2F"',
      ),
      "expected no-JS analytics pixel with hostname and root path",
    );
    assert.match(
      indexHtml,
      /<img\b[^>]*\bclass="analytics-pixel"[^>]*>/,
    );
    const pixelTag = indexHtml.match(/<img\b[^>]*\bclass="analytics-pixel"[^>]*>/)?.[0] ?? "";
    assert.match(pixelTag, /\bwidth="1"/);
    assert.match(pixelTag, /\bheight="1"/);
    assert.match(pixelTag, /\balt=""/);
    assert.doesNotMatch(
      indexHtml,
      /<noscript>[\s\S]*?noscript\.gif[\s\S]*?<\/noscript>/i,
    );

    const indexPrefix = indexHtml.match(/<html\b[^>]*\bprefix="([^"]*)"/)?.[1] ?? "";
    const declaredKeys = [...indexPrefix.matchAll(/([\w-]+):\s*\S+/g)].map(
      (m) => m[1],
    );
    assert.deepEqual(declaredKeys, ["wd", "wdt", "schema"]);

    const privacyHtmlTag = privacyHtml.match(/<html\b[^>]*>/)?.[0] ?? "";
    assert.doesNotMatch(privacyHtmlTag, /\bprefix=/);

    const style = indexHtml.match(/<style>([\s\S]*?)<\/style>/)?.[1] ?? "";
    assert.ok(style.length > 0, "expected inlined stylesheet on index.html");
    assert.doesNotMatch(style, /optimizelegibility/i);
    assert.doesNotMatch(style, /text-wrap:\s*pretty/i);
    assert.match(style, /\.analytics-pixel\{/);
    assert.match(
      style,
      /@media\s*\(width\s*<=\s*48rem\)\{[\s\S]*?\.site-header\{[^}]*backdrop-filter:\s*none/,
    );

    const headersText = readFileSync(join(ROOT, "_headers"), "utf-8");
    const cspLine =
      headersText
        .split("\n")
        .find((line) => line.trimStart().startsWith("Content-Security-Policy:")) ??
      "";
    assert.match(cspLine, /script-src 'none'/);
    assert.doesNotMatch(cspLine, /simpleanalytics/i);

    const nestedPostHtml = readFileSync(
      join(site, "posts", "2026-01-20_chem_flow.html"),
      "utf-8",
    );
    for (const [label, html, expectedPath] of [
      ["privacy", privacyHtml, "%2Fprivacy.html"],
      ["post", nestedPostHtml, "%2Fposts%2F2026-01-20_chem_flow.html"],
    ]) {
      assert.doesNotMatch(
        html,
        /scripts\.simpleanalyticscdn\.com|latest\.js|<script\b/i,
        `${label}: expected zero scripts and no Simple Analytics JS`,
      );
      assert.ok(
        html.includes(
          `src="https://queue.simpleanalyticscdn.com/noscript.gif?hostname=adafede.github.io&amp;path=${expectedPath}"`,
        ),
        `${label}: expected analytics pixel with path ${expectedPath}`,
      );
      assert.ok(
        !html.includes("&amp;amp;"),
        `${label}: found double-escaped &amp;amp;`,
      );
      const tag =
        html.match(/<img\b[^>]*\bclass="analytics-pixel"[^>]*>/)?.[0] ?? "";
      assert.match(tag, /\bwidth="1"/);
      assert.match(tag, /\bheight="1"/);
      assert.match(tag, /\balt=""/);
      assert.doesNotMatch(tag, /\bloading="lazy"/);
      assert.doesNotMatch(tag, /\bcrossorigin\b/);
      assert.doesNotMatch(html, /connect-src[^"]*simpleanalytics/i);
    }
  },
);

test(
  "built contact pages obfuscate email without leaking plaintext or unused CSS",
  { skip: siteSkip() },
  () => {
    const address = "rutz@imsb.biol.ethz.ch";
    const encodedMailto = obfuscateMailto(address);
    const indexHtml = readFileSync(join(site, "index.html"), "utf-8");
    const privacyHtml = readFileSync(join(site, "privacy.html"), "utf-8");
    const cvHtml = readFileSync(join(site, "cv.html"), "utf-8");

    for (const [name, html] of [
      ["index.html", indexHtml],
      ["privacy.html", privacyHtml],
      ["cv.html", cvHtml],
    ]) {
      assert.doesNotMatch(
        html,
        /mailto:/i,
        `${name}: must not contain literal mailto: scheme`,
      );
      assert.ok(
        !html.toLowerCase().includes(address),
        `${name}: must not contain plaintext email address`,
      );
    }

    assert.ok(
      indexHtml.includes(`href="${encodedMailto}"`),
      "index.html: expected entity-encoded mailto href",
    );
    assert.ok(
      privacyHtml.includes(`href="${encodedMailto}"`),
      "privacy.html: expected entity-encoded mailto href",
    );
    assert.ok(
      !cvHtml.includes(`href="${encodedMailto}"`),
      "cv.html: email must remain unlinked",
    );

    for (const [name, html] of [
      ["privacy.html", privacyHtml],
      ["cv.html", cvHtml],
    ]) {
      const style = html.match(/<style>([\s\S]*?)<\/style>/)?.[1] ?? "";
      assert.ok(
        style.includes(".contact-decoy{display:none}"),
        `${name}: expected .contact-decoy{display:none} in inlined <style>`,
      );
      assert.ok(
        html.includes('class="contact-decoy"'),
        `${name}: expected class="contact-decoy" in body`,
      );
    }

    const indexStyle = indexHtml.match(/<style>([\s\S]*?)<\/style>/)?.[1] ?? "";
    assert.ok(
      !indexStyle.includes(".contact-decoy"),
      "index.html: must not inline unused .contact-decoy CSS",
    );
  },
);
